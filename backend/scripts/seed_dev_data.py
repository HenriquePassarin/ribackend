"""Carga de dados de exemplo para desenvolvimento local.

ATENÇÃO: todos os nomes, códigos, preços e rótulos abaixo são FICTÍCIOS. Os
preços são gravados como 0,00 de propósito, para deixar explícito que nenhum
preço comercial foi inventado. Não representam o cadastro de nenhum mercado e
não devem ser usados como referência.

Os rótulos (`vision_label`) são escolhidos de acordo com o provedor de visão
ativo, porque eles precisam casar exatamente com a classe prevista:

* ``VISION_PROVIDER=stub``   — rótulos do adaptador SIMULADO (não há modelo real).
* ``VISION_PROVIDER=opencv`` — rótulos reais do modelo ONNX configurado
  (aqui, MobileNetV2/ImageNet, que identifica espécies e uma variedade de maçã:
  ``Granny Smith``).

Uso:
    python scripts/seed_dev_data.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.database import get_session_factory, init_schema  # noqa: E402
from app.models.fruit import Fruit  # noqa: E402
from app.repositories.fruit_repository import FruitRepository  # noqa: E402

ZERO_PRICE = Decimal("0.00")  # preço-fantasia: nenhum preço real é inventado


def _example(name: str, code: str, vision_label: str) -> dict[str, object]:
    return {"name": f"{name} (exemplo)", "code": code, "vision_label": vision_label}


# Rótulos do adaptador SIMULADO (development_stub.DEFAULT_STUB_LABELS).
STUB_EXAMPLES: tuple[dict[str, object], ...] = (
    _example("Maçã Gala", "01234", "apple_gala"),
    _example("Maçã Fuji", "05678", "apple_fuji"),
    _example("Laranja Pera", "09012", "orange_pera"),
    _example("Banana Prata", "00002", "banana_prata"),
)

# Rótulos reais do modelo de referência (ImageNet-1k). Os nomes precisam ser
# exatamente iguais aos do arquivo MODEL_LABELS_PATH.
OPENCV_EXAMPLES: tuple[dict[str, object], ...] = (
    _example("Maçã Granny Smith", "01234", "Granny Smith"),
    _example("Banana Prata", "00002", "banana"),
    _example("Laranja Pera", "09012", "orange"),
    _example("Limão Taiti", "07777", "lemon"),
    _example("Morango", "08888", "strawberry"),
    _example("Romã", "09999", "pomegranate"),
    _example("Figo", "01111", "fig"),
)


def examples_for(settings: Settings) -> tuple[tuple[dict[str, object], ...], str]:
    if settings.vision_provider == "opencv":
        return (
            OPENCV_EXAMPLES,
            "Rótulos reais do modelo ONNX (espécies do ImageNet). O modelo NÃO distingue "
            "variedades comerciais além de 'Granny Smith', e a confiança tende a ser baixa: "
            "a sugestão sempre deve ser confirmada pelo atendente.",
        )
    if settings.vision_provider == "disabled":
        return (
            STUB_EXAMPLES,
            "VISION_PROVIDER=disabled: o serviço de visão está indisponível e responderá 503. "
            "Cadastro criado apenas para exercitar as rotas de frutas.",
        )
    return (
        STUB_EXAMPLES,
        "Rótulos do adaptador SIMULADO (VISION_PROVIDER=stub). Não há reconhecimento real "
        "em uso; as previsões são apenas simuladas.",
    )


def main() -> int:
    settings = get_settings()
    init_schema(settings)
    session = get_session_factory(settings)()
    repository = FruitRepository(session)
    examples, note = examples_for(settings)

    created = 0
    skipped = 0
    for item in examples:
        code = str(item["code"])
        if repository.get_by_code(code) is not None:
            skipped += 1
            continue
        repository.add(
            Fruit(
                name=str(item["name"]),
                code=code,
                price_per_kg=ZERO_PRICE,
                unit="kg",
                active=True,
                vision_label=str(item["vision_label"]),
            )
        )
        created += 1

    print(f"Frutas de exemplo criadas: {created} (ignoradas por já existirem: {skipped}).")
    print(f"Provedor de visão: {settings.vision_provider}.")
    print(f"AVISO: {note}")
    print("AVISO: preços gravados como 0,00 (dados fictícios; nenhum preço real foi inventado).")
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
