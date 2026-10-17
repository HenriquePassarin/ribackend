"""Ponto de entrada da aplicação FastAPI."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api.router import build_api_router
from app.api.routes import health as health_routes
from app.core.config import Settings, get_settings
from app.core.database import init_schema
from app.core.errors import AppError
from app.core.logging import configure_logging, set_request_id

logger = logging.getLogger(__name__)

OPENAPI_DESCRIPTION = """
API para auxiliar o atendente de caixa a identificar frutas e variedades comerciais.

Princípios:
* O modelo visual **não** define preço nem código comercial: ambos vêm do cadastro.
* Uma previsão **não** é uma confirmação; a confiança informada não garante acerto.
* O atendente pode confirmar ou corrigir a sugestão.
* Sem correspondência no cadastro, a resposta traz `fruit: null` e o status `no_catalog_match`.
* Imagens não são armazenadas por padrão.

Códigos de erro (`error.code`):
* `VALIDATION_ERROR` – dados de entrada inválidos (422).
* `INVALID_IMAGE` – conteúdo não é uma imagem válida (400).
* `EMPTY_IMAGE` – arquivo vazio (400).
* `IMAGE_TOO_LARGE` – imagem acima de `MAX_IMAGE_SIZE_MB` (413).
* `UNSUPPORTED_MEDIA_TYPE` – formato não suportado pelo adaptador (415).
* `FRUIT_NOT_FOUND` / `RECOGNITION_NOT_FOUND` – recurso inexistente (404).
* `FRUIT_INACTIVE` – fruta inativa não pode ser confirmada (400).
* `DUPLICATE_FRUIT` – código comercial ou rótulo já cadastrado (409).
* `INVALID_STATE` – transição de estado não permitida, por exemplo tentativa já finalizada (400).
* `MODEL_UNAVAILABLE` – modelo/dependência indisponível (503).
* `INFERENCE_TIMEOUT` – inferência excedeu o tempo limite (504).
* `INTERNAL_ERROR` – erro inesperado, sem detalhes internos (500).
"""

OPENAPI_TAGS: list[dict[str, str]] = [
    {
        "name": "health",
        "description": (
            "Disponibilidade da aplicação. Não expõe segredos, versões de bibliotecas nem "
            "estado do banco de dados."
        ),
    },
    {
        "name": "fruits",
        "description": (
            "Cadastro comercial consultado pela API. Código e preço vêm daqui — nunca da "
            "previsão visual. O campo `vision_label` é o vínculo explícito entre a classe do "
            "modelo e a fruta cadastrada."
        ),
    },
    {
        "name": "recognitions",
        "description": (
            "Reconhecimento de imagem e confirmação humana. A confiança do modelo não é "
            "garantia de acerto: `recognized` ainda pode exigir confirmação, e a fruta "
            "sugerida só é usada após `POST /recognitions/{recognition_id}/confirm`. "
            "Imagens não são armazenadas."
        ),
    },
]

SWAGGER_UI_PARAMETERS: dict[str, object] = {
    "displayRequestDuration": True,
    "filter": True,
    "docExpansion": "list",
    "defaultModelsExpandDepth": 1,
    "operationsSorter": "method",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Atribui um identificador de correlação e registra acesso básico."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
        finally:
            set_request_id(None)
        duration_ms = (perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s em %.1f ms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response


def _error_response(status_code: int, code: str, message: str, details: object = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


_HTTP_EXCEPTION_DEFAULTS: dict[int, tuple[str, str]] = {
    404: ("NOT_FOUND", "Recurso não encontrado."),
    405: ("METHOD_NOT_ALLOWED", "Método não permitido para este recurso."),
}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.info("Erro tratado code=%s status=%s path=%s", exc.code, exc.status_code, request.url.path)
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Detalhes limitados a loc/msg/type: sem ecoar valores internos nem stack trace.
        details = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        logger.info("Falha de validação path=%s erros=%s", request.url.path, len(details))
        return _error_response(
            422, "VALIDATION_ERROR", "Os dados enviados são inválidos.", details
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_EXCEPTION_DEFAULTS.get(
            exc.status_code, (f"HTTP_{exc.status_code}", "Requisição não pôde ser processada.")
        )
        return _error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Log completo apenas no servidor; a resposta nunca revela detalhes internos.
        logger.exception("Erro inesperado path=%s", request.url.path)
        return _error_response(500, "INTERNAL_ERROR", "Erro interno.")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "Iniciando %s v%s (env=%s, vision_provider=%s)",
            settings.app_name,
            __version__,
            settings.app_env,
            settings.vision_provider,
        )
        if settings.vision_provider == "stub":
            logger.warning(
                "VISION_PROVIDER=stub: o reconhecimento está SIMULADO. Nenhum modelo real está "
                "em uso e os resultados não representam reconhecimento visual."
            )
        if settings.auto_create_schema:
            try:
                init_schema(settings)
            except Exception as exc:  # noqa: BLE001 - mensagem clara para configuração incorreta
                raise RuntimeError(
                    "Não foi possível inicializar o banco de dados com DATABASE_URL configurada. "
                    "Verifique a configuração ou desative AUTO_CREATE_SCHEMA e aplique migrações."
                ) from exc
        yield
        logger.info("Encerrando %s", settings.app_name)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=OPENAPI_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestContextMiddleware)
    origins = settings.cors_origin_list
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
    else:
        logger.info("CORS desabilitado: nenhuma origem configurada em CORS_ORIGINS.")

    app.include_router(health_routes.router)
    app.include_router(build_api_router(settings))
    register_exception_handlers(app)
    return app


app = create_app()
