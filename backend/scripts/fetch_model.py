"""Baixa e verifica um modelo ONNX para uso com VISION_PROVIDER=opencv.

O script não treina nada: apenas baixa artefatos já publicados, confere o
SHA-256 e mostra as variáveis de ambiente necessárias. Use ``--list`` para ver os
modelos registrados e ``--url/--sha256`` para adicionar um modelo próprio
(por exemplo, um classificador treinado no seu dataset de hortifruti).

Uso:
    python scripts/fetch_model.py --list
    python scripts/fetch_model.py --model mobilenetv2-7
    python scripts/fetch_model.py --name meu-modelo --url https://... --sha256 <hash> \
        --labels-url https://... --labels-sha256 <hash>
"""

from __future__ import annotations

import argparse
import hashlib
import ssl
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

ILSVRC_LABELS_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/dnn/"
    "classification_classes_ILSVRC2012.txt"
)
ILSVRC_LABELS_SHA256 = "4eb3da435cf544e4a6f390f62c84cb9c9bb68cf8b14e97f8a063452382e5efd2"

USER_AGENT = "fruit-recognition-api/0.1 (fetch_model.py)"

REGISTRY: dict[str, dict[str, object]] = {
    "mobilenetv2-7": {
        "description": (
            "MobileNetV2 do ONNX Model Zoo, treinado no ImageNet-1k (1000 classes). "
            "REFERÊNCIA TÉCNICA: serve para validar a integração OpenCV/ONNX e medir latência, "
            "mas NÃO atende ao requisito de variedades comerciais e NÃO cobre várias frutas de "
            "hortifruti (sem uva, manga, tomate, melão, pera ou kiwi)."
        ),
        "url": (
            "https://github.com/onnx/models/raw/main/validated/vision/classification/"
            "mobilenet/model/mobilenetv2-7.onnx"
        ),
        "sha256": "c1c513582d56afceff8516c73804e484c81c6a830712ab6d682253f4a3cd042f",
        "labels_url": ILSVRC_LABELS_URL,
        "labels_sha256": ILSVRC_LABELS_SHA256,
        "env": {
            "VISION_PROVIDER": "opencv",
            "MODEL_INPUT_SIZE": "224",
            "MODEL_INPUT_SCALE": "0.00392156862745098",
            "MODEL_INPUT_MEAN": "0.485,0.456,0.406",
            "MODEL_INPUT_STD": "0.229,0.224,0.225",
            "MODEL_SWAP_RB": "true",
            "MODEL_OUTPUT_SOFTMAX": "auto",
        },
        "notes": (
            "Exige RGB com normalização ImageNet (mean/std); o trecho de .env impresso já "
            "configura isso. Verificado localmente (1 imagem por classe, sem métrica de acurácia): "
            "banana, limão, laranja, morango e Granny Smith classificados corretamente com "
            "confiança alta; maçã vermelha -> 'pomegranate' (o ImageNet não possui classe de maçã "
            "vermelha). Latência medida nesta máquina: ~39 ms de média por inferência "
            "(224x224, CPU) - não é a latência do hardware alvo."
        ),
    }
}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(url: str, destination: Path, expected_sha256: str | None) -> None:
    if destination.is_file() and expected_sha256:
        current = sha256_of(destination)
        if current == expected_sha256:
            print(f"[ok] já existe e o hash confere: {destination}")
            return

    print(f"[..] baixando {url}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, context=_ssl_context(), timeout=120) as response:
        data = response.read()

    if expected_sha256 and hashlib.sha256(data).hexdigest() != expected_sha256:
        raise SystemExit(
            f"[erro] hash diferente do esperado para {url}; download descartado."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print(f"[ok] {destination} ({len(data)} bytes, sha256={hashlib.sha256(data).hexdigest()})")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def print_env_snippet(model_file: Path, labels_file: Path, env: dict[str, str]) -> None:
    print("\nConfiguração sugerida no .env:")
    print(f"VISION_PROVIDER={env.get('VISION_PROVIDER', 'opencv')}")
    print(f"MODEL_PATH={model_file.relative_to(MODELS_DIR.parent).as_posix()}")
    print(f"MODEL_LABELS_PATH={labels_file.relative_to(MODELS_DIR.parent).as_posix()}")
    for key, value in env.items():
        if key != "VISION_PROVIDER":
            print(f"{key}={value}")
    print(
        "\nPróximos passos: cadastrar frutas com vision_label igual ao rótulo da classe do "
        "modelo e validar a confiança em um dataset representativo do seu mercado antes de "
        "confiar no limiar MIN_RECOGNITION_CONFIDENCE."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Baixa e verifica um modelo ONNX.")
    parser.add_argument("--list", action="store_true", help="lista os modelos registrados")
    parser.add_argument("--model", choices=sorted(REGISTRY), help="nome de um modelo registrado")
    parser.add_argument("--name", help="nome do arquivo do modelo ao usar --url")
    parser.add_argument("--url", help="URL do arquivo .onnx")
    parser.add_argument("--sha256", help="SHA-256 esperado do .onnx")
    parser.add_argument("--labels-url", help="URL do arquivo de rótulos")
    parser.add_argument("--labels-sha256", help="SHA-256 esperado dos rótulos")
    parser.add_argument(
        "--skip-labels", action="store_true", help="não baixar rótulos (use com --url)"
    )
    args = parser.parse_args(argv)

    if args.list or not (args.model or args.url):
        print("Modelos registrados:")
        for name, entry in REGISTRY.items():
            print(f"  - {name}: {entry['description']}")
            print(f"      {entry['notes']}")
        if not (args.model or args.url):
            print("\nInforme --model <nome> ou --url/--sha256/--name para baixar.")
        return 0

    if args.model:
        entry = REGISTRY[args.model]
        model_file = MODELS_DIR / f"{args.model}.onnx"
        labels_file = MODELS_DIR / "ilsvrc2012_labels.txt"
        download(str(entry["url"]), model_file, str(entry["sha256"]))  # type: ignore[arg-type]
        download(str(entry["labels_url"]), labels_file, str(entry["labels_sha256"]))  # type: ignore[arg-type]
        env = dict(entry["env"])  # type: ignore[arg-type]
        print(f"\n{entry['description']}\n{entry['notes']}")
        print_env_snippet(model_file, labels_file, env)
        return 0

    if not args.name or not args.sha256:
        raise SystemExit("[erro] --url exige --name e --sha256 para verificação de integridade.")
    model_file = MODELS_DIR / f"{args.name}.onnx"
    download(args.url, model_file, args.sha256)
    if args.labels_url and not args.skip_labels:
        labels_file = MODELS_DIR / f"{args.name}_labels.txt"
        download(args.labels_url, labels_file, args.labels_sha256)
    else:
        labels_file = MODELS_DIR / "seus_rotulos.txt"
        print(f"[aviso] crie {labels_file} com um rótulo por linha, na ordem das classes do modelo.")
    print_env_snippet(model_file, labels_file, {})
    return 0


if __name__ == "__main__":
    sys.exit(main())
