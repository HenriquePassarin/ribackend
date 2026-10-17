"""Erros padronizados da aplicação.

Cada erro carrega o status HTTP, um código estável para o cliente e uma mensagem
segura (sem dados internos, caminhos, stack trace ou segredos).
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Erro de aplicação com contrato HTTP padronizado."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"
    message: str = "Erro interno."

    def __init__(self, message: str | None = None, details: Any = None) -> None:
        self.message = message or self.message
        self.details = details
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class ValidationFailureError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Os dados enviados são inválidos."


class InvalidImageError(AppError):
    status_code = 400
    code = "INVALID_IMAGE"
    message = "O arquivo enviado não é uma imagem válida."


class EmptyImageError(AppError):
    status_code = 400
    code = "EMPTY_IMAGE"
    message = "O arquivo enviado está vazio."


class ImageTooLargeError(AppError):
    status_code = 413
    code = "IMAGE_TOO_LARGE"
    message = "A imagem enviada excede o tamanho máximo permitido."


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"
    message = "Tipo de arquivo não suportado."


class FruitNotFoundError(AppError):
    status_code = 404
    code = "FRUIT_NOT_FOUND"
    message = "Fruta não encontrada."


class RecognitionNotFoundError(AppError):
    status_code = 404
    code = "RECOGNITION_NOT_FOUND"
    message = "Tentativa de reconhecimento não encontrada."


class FruitInactiveError(AppError):
    status_code = 400
    code = "FRUIT_INACTIVE"
    message = "A fruta selecionada está inativa e não pode ser confirmada."


class DuplicateFruitError(AppError):
    status_code = 409
    code = "DUPLICATE_FRUIT"
    message = "Já existe uma fruta com o mesmo código comercial."


class InvalidStateError(AppError):
    status_code = 400
    code = "INVALID_STATE"
    message = "Operação incompatível com o estado atual do recurso."


class ModelUnavailableError(AppError):
    status_code = 503
    code = "MODEL_UNAVAILABLE"
    message = "O serviço de reconhecimento está indisponível no momento."


class InferenceTimeoutError(AppError):
    status_code = 504
    code = "INFERENCE_TIMEOUT"
    message = "O reconhecimento excedeu o tempo limite."
