"""Casos de uso de reconhecimento e confirmação.

Estratégia de execução da inferência: o adaptador de visão tem interface
síncrona (``predict``) e pode ser bloqueante. Por isso a chamada é executada em
thread separada com ``anyio.to_thread.run_sync`` e limitada por
``INFERENCE_TIMEOUT_SECONDS`` via ``anyio.fail_after``, evitando bloquear o event
loop do FastAPI. Limitação conhecida: um timeout não interrompe o thread já em
execução; o thread é apenas abandonado. Um modelo real que suporte cancelamento
deve expor uma interface assíncrona própria.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

import anyio

from app.core.config import Settings
from app.core.errors import (
    AppError,
    EmptyImageError,
    FruitInactiveError,
    FruitNotFoundError,
    ImageTooLargeError,
    InferenceTimeoutError,
    InvalidImageError,
    InvalidStateError,
    ModelUnavailableError,
    RecognitionNotFoundError,
    UnsupportedMediaTypeError,
)
from app.core.images import DECLARED_MIME_TYPES, SUPPORTED_FORMATS, sniff_format
from app.models.fruit import Fruit, utcnow
from app.models.recognition import CONFIRMABLE_STATUSES, FINAL_STATUSES, Recognition, RecognitionStatus
from app.repositories.fruit_repository import FruitRepository
from app.repositories.recognition_repository import RecognitionRepository
from app.vision.base import FruitRecognizer, Prediction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecognitionOutcome:
    """Resultado do caso de uso de reconhecimento."""

    recognition: Recognition
    fruit: Fruit | None
    confirmation_required: bool


class RecognitionService:
    def __init__(
        self,
        *,
        fruit_repository: FruitRepository,
        recognition_repository: RecognitionRepository,
        recognizer: FruitRecognizer,
        settings: Settings,
    ) -> None:
        self.fruits = fruit_repository
        self.recognitions = recognition_repository
        self.recognizer = recognizer
        self.settings = settings

    # ---------------------------------------------------------------- uploads

    @property
    def supported_formats(self) -> frozenset[str]:
        """Formatos aceitos pelo adaptador.

        Um adaptador que implemente apenas o contrato mínimo da especificação
        (``predict``) continua funcionando: nesse caso usamos os formatos
        suportados por padrão.
        """
        declared = getattr(self.recognizer, "supported_formats", None)
        if not declared:
            return SUPPORTED_FORMATS
        return frozenset(declared)

    def _normalize_declared_type(self, content_type: str | None) -> str | None:
        if not content_type:
            return None
        return content_type.split(";")[0].strip().lower() or None

    def validate_upload(self, *, content_type: str | None, data: bytes) -> str:
        """Valida o upload e devolve o formato real detectado.

        Não confia em extensão nem em Content-Type: inspeciona a assinatura real
        do arquivo.
        """
        declared = self._normalize_declared_type(content_type)
        if declared is not None and declared not in DECLARED_MIME_TYPES:
            raise UnsupportedMediaTypeError(details={"received_content_type": declared})

        if not data:
            raise EmptyImageError()

        if len(data) > self.settings.max_image_size_bytes:
            raise ImageTooLargeError(details={"max_image_size_mb": self.settings.max_image_size_mb})

        detected = sniff_format(data)
        if detected is None:
            raise InvalidImageError()

        supported = self.supported_formats
        if detected not in supported:
            raise UnsupportedMediaTypeError(
                details={"detected_format": detected, "supported_formats": sorted(supported)}
            )
        return detected

    # ------------------------------------------------------------- inferência

    async def _run_inference(self, image_bytes: bytes) -> Prediction:
        timeout = self.settings.inference_timeout_seconds
        try:
            with anyio.fail_after(timeout):
                # abandon_on_cancel=True permite que o timeout descarte o resultado
                # sem esperar o fim do thread bloqueante.
                return await anyio.to_thread.run_sync(
                    self.recognizer.predict, image_bytes, abandon_on_cancel=True
                )
        except TimeoutError as exc:
            raise InferenceTimeoutError(details={"timeout_seconds": timeout}) from exc

    async def recognize(
        self,
        *,
        content_type: str | None,
        data: bytes,
        filename: str | None = None,
    ) -> RecognitionOutcome:
        detected_format = self.validate_upload(content_type=content_type, data=data)
        logger.info(
            "Reconhecimento solicitado formato=%s bytes=%s arquivo=%s",
            detected_format,
            len(data),
            # Nome do arquivo é apenas referência de log; a imagem não é persistida.
            (filename or "-")[:80],
        )

        started = perf_counter()
        try:
            prediction = await self._run_inference(data)
        except (ModelUnavailableError, InferenceTimeoutError) as exc:
            # A causa técnica (que pode conter caminhos internos do modelo) fica
            # apenas no log; o cliente recebe a mensagem padronizada.
            logger.warning("Adaptador de visão indisponível ou lento: %s", exc)
            self._record_failure(reason=exc.code, model_version=self._current_model_version())
            raise type(exc)() from exc
        except Exception as exc:  # noqa: BLE001 - falha inesperada do adaptador
            logger.exception("Falha inesperada no adaptador de visão computacional")
            self._record_failure(reason="unexpected_error", model_version=self._current_model_version())
            raise AppError() from exc

        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "Inferência concluída em %.1f ms label=%s confianca=%s simulada=%s versao_modelo=%s",
            duration_ms,
            prediction.label,
            prediction.confidence,
            getattr(self.recognizer, "is_simulated", False),
            prediction.model_version,
        )
        return self._apply_policy(prediction)

    def _current_model_version(self) -> str | None:
        return getattr(self.recognizer, "model_version", None) or self.settings.model_version

    def _record_failure(self, *, reason: str, model_version: str | None) -> None:
        """Persiste a tentativa com status ``failed`` para auditoria.

        Não inclui detalhes internos na resposta HTTP; serve apenas para
        rastrear indisponibilidade/timeout do modelo.
        """
        try:
            self.recognitions.add(
                Recognition(
                    predicted_label=None,
                    confidence=None,
                    matched_fruit_id=None,
                    status=RecognitionStatus.FAILED.value,
                    model_version=model_version,
                )
            )
        except Exception:  # noqa: BLE001 - auditoria não deve derrubar a resposta
            logger.exception("Não foi possível registrar a tentativa com falha (motivo=%s)", reason)

    # ---------------------------------------------------------------- política

    def _apply_policy(self, prediction: Prediction) -> RecognitionOutcome:
        """Determina o status e a necessidade de confirmação humana.

        O status ``recognized`` indica apenas que a confiança ficou acima do
        limiar configurado; não é prova de acerto.
        """
        confidence = prediction.confidence
        matched: Fruit | None = None

        if not prediction.label:
            # O modelo não encontrou um rótulo aceitável.
            status = RecognitionStatus.UNRECOGNIZED
            confirmation_required = True
        else:
            candidate = self.fruits.get_by_vision_label(prediction.label)
            if candidate is None or not candidate.active:
                # Sem correspondência selecionável no cadastro: não inventamos
                # nome, código ou preço, e frutas inativas não podem ser usadas.
                status = RecognitionStatus.NO_CATALOG_MATCH
                confirmation_required = True
            else:
                matched = candidate
                confident = confidence is not None and confidence >= self.settings.min_recognition_confidence
                if confident:
                    status = RecognitionStatus.RECOGNIZED
                    confirmation_required = self.settings.always_require_confirmation
                else:
                    status = RecognitionStatus.CONFIRMATION_REQUIRED
                    confirmation_required = True

        recognition = Recognition(
            predicted_label=prediction.label,
            confidence=confidence,
            matched_fruit_id=matched.id if matched else None,
            status=status.value,
            model_version=prediction.model_version,
        )
        self.recognitions.add(recognition)
        logger.info(
            "Tentativa %s registrada status=%s fruta_sugerida=%s confirmação_obrigatoria=%s",
            recognition.id,
            recognition.status,
            recognition.matched_fruit_id,
            confirmation_required,
        )
        return RecognitionOutcome(
            recognition=recognition,
            fruit=matched,
            confirmation_required=confirmation_required,
        )

    # ----------------------------------------------------------- confirmação

    def confirm(self, *, recognition_id: str, fruit_id: int) -> tuple[Recognition, Fruit]:
        recognition = self.recognitions.get(recognition_id)
        if recognition is None:
            raise RecognitionNotFoundError(details={"recognition_id": recognition_id})

        if recognition.status in {status.value for status in FINAL_STATUSES}:
            raise InvalidStateError(
                message="Esta tentativa já foi finalizada e não pode ser confirmada novamente.",
                details={"status": recognition.status},
            )
        if recognition.status not in {status.value for status in CONFIRMABLE_STATUSES}:
            raise InvalidStateError(details={"status": recognition.status})

        fruit = self.fruits.get(fruit_id)
        if fruit is None:
            raise FruitNotFoundError(details={"fruit_id": fruit_id})
        if not fruit.active:
            raise FruitInactiveError(details={"fruit_id": fruit.id})

        # Confirmação não altera cadastro nem preço da fruta.
        status = (
            RecognitionStatus.CONFIRMED
            if recognition.matched_fruit_id == fruit.id
            else RecognitionStatus.CORRECTED
        )
        recognition.confirmed_fruit_id = fruit.id
        recognition.status = status.value
        recognition.confirmed_at = utcnow()
        self.recognitions.commit()

        logger.info(
            "Tentativa %s finalizada status=%s fruta=%s (sugerida=%s)",
            recognition.id,
            recognition.status,
            fruit.id,
            recognition.matched_fruit_id,
        )
        return recognition, fruit
