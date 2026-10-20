"""Configuração central da aplicação.

Todas as configurações são lidas de variáveis de ambiente (e opcionalmente de um
arquivo ``.env``). Nenhum segredo deve ser embutido no código.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]
VisionProvider = Literal["opencv", "stub", "disabled"]
SoftmaxMode = Literal["auto", "true", "false"]


def _parse_triplet(value: str, variable: str) -> tuple[float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 3:
        raise ValueError(f"{variable} deve conter três valores separados por vírgula")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


class Settings(BaseSettings):
    """Configurações da aplicação, validadas na inicialização."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Aplicação
    app_env: AppEnv = "development"
    app_name: str = "fruit-recognition-api"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"

    # Persistência
    database_url: str = "sqlite:///./fruits.db"
    # Conveniência de protótipo: cria as tabelas na inicialização.
    # Em produção, prefira migrações versionadas e desative esta opção.
    auto_create_schema: bool = True
    db_echo: bool = False

    # Upload de imagens
    max_image_size_mb: int = Field(default=10, ge=1, le=200)
    inference_timeout_seconds: float = Field(default=10.0, gt=0, le=300)

    # Política de reconhecimento
    min_recognition_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    # Decisão pendente de produto: enquanto a política não for definida,
    # o padrão seguro é exigir confirmação humana mesmo acima do limiar.
    always_require_confirmation: bool = True

    # Visão computacional
    # opencv = modelo ONNX real (cv2.dnn); stub = SIMULADO; disabled = indisponível.
    vision_provider: VisionProvider = "stub"
    allow_stub_in_production: bool = False
    # Caminho do modelo (ONNX). Obrigatório quando VISION_PROVIDER=opencv.
    model_path: str | None = None
    # Arquivo com um rótulo por linha, na ordem dos índices de saída do modelo.
    model_labels_path: str | None = None
    # Identificação livre da versão; quando vazia, é derivada do nome + hash do arquivo.
    model_version: str | None = None
    model_input_size: int = Field(default=224, ge=32, le=1024)
    # 1/255 para modelos que esperam entrada em [0,1]; 1.0 para entrada em [0,255].
    model_input_scale: float = Field(default=1.0 / 255.0, gt=0.0, le=255.0)
    # Normalização aplicada ao blob já escalado: (blob - mean) / std, por canal.
    # Os valores usam a ordem de canais resultante de MODEL_SWAP_RB.
    model_input_mean: str = "0,0,0"
    model_input_std: str = "1,1,1"
    model_swap_rb: bool = False
    # auto: aplica softmax quando a saída não parece uma distribuição de probabilidades.
    model_output_softmax: SoftmaxMode = "auto"

    # HTTP
    cors_origins: str = ""
    fruits_default_limit: int = Field(default=20, ge=1, le=200)
    fruits_max_limit: int = Field(default=100, ge=1, le=500)

    @property
    def max_image_size_bytes(self) -> int:
        return self.max_image_size_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        """Origens de CORS, separadas por vírgula. Vazio significa nenhuma origem."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @field_validator("model_path", "model_version", "model_labels_path", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("model_input_mean")
    @classmethod
    def _validate_mean(cls, value: str) -> str:
        for number in _parse_triplet(value, "MODEL_INPUT_MEAN"):
            if not 0.0 <= number <= 255.0:
                raise ValueError("cada valor de MODEL_INPUT_MEAN deve estar entre 0 e 255")
        return value

    @field_validator("model_input_std")
    @classmethod
    def _validate_std(cls, value: str) -> str:
        for number in _parse_triplet(value, "MODEL_INPUT_STD"):
            if not 0.0 < number <= 255.0:
                raise ValueError("cada valor de MODEL_INPUT_STD deve ser maior que zero")
        return value

    @property
    def model_input_mean_tuple(self) -> tuple[float, float, float]:
        return _parse_triplet(self.model_input_mean, "MODEL_INPUT_MEAN")

    @property
    def model_input_std_tuple(self) -> tuple[float, float, float]:
        return _parse_triplet(self.model_input_std, "MODEL_INPUT_STD")

    @model_validator(mode="after")
    def _validate_consistency(self) -> "Settings":
        if self.vision_provider == "stub" and self.app_env == "production" and not self.allow_stub_in_production:
            raise ValueError(
                "Configuração inválida: VISION_PROVIDER=stub não pode ser usado em produção "
                "(APP_ENV=production). O adaptador simulado não realiza reconhecimento real. "
                "Defina uma implementação real de visão computacional; se o ambiente for isolado "
                "e explicitamente de testes, defina ALLOW_STUB_IN_PRODUCTION=true e documente a exceção."
            )
        if self.vision_provider == "opencv":
            if not self.model_path:
                raise ValueError(
                    "Configuração inválida: MODEL_PATH é obrigatório quando VISION_PROVIDER=opencv."
                )
            if not Path(self.model_path).is_file():
                raise ValueError(
                    "Configuração inválida: MODEL_PATH não aponta para um arquivo existente "
                    "(caminhos são relativos ao diretório de execução do processo; "
                    "use scripts/fetch_model.py para baixar um modelo verificado)."
                )
            if not self.model_labels_path:
                raise ValueError(
                    "Configuração inválida: MODEL_LABELS_PATH é obrigatório quando VISION_PROVIDER=opencv."
                )
            if not Path(self.model_labels_path).is_file():
                raise ValueError(
                    "Configuração inválida: MODEL_LABELS_PATH não aponta para um arquivo existente."
                )
        if self.fruits_default_limit > self.fruits_max_limit:
            raise ValueError(
                "Configuração inválida: FRUITS_DEFAULT_LIMIT não pode ser maior que FRUITS_MAX_LIMIT."
            )
        if not self.api_v1_prefix.startswith("/"):
            raise ValueError("Configuração inválida: API_V1_PREFIX deve começar com '/'.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Retorna as configurações da aplicação (cacheado por processo).

    Em testes, sobrescreva a dependência ``get_settings`` do FastAPI em vez de
    mutar o cache.
    """
    return Settings()
