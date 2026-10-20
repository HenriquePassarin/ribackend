"""Treina o modelo de frutas no dataset preparado e exporta ONNX (opcional).

Este script NÃO roda no fluxo da aplicação: é uma ferramenta de treino, executada
manualmente. Ele depende de ``ultralytics``, que não é dependência do projeto
instalado por padrão (é pesado e só faz sentido para quem for treinar):

    cd backend
    .venv/Scripts/python.exe -m pip install ultralytics
    .venv/Scripts/python.exe scripts/prepare_dataset.py --zip "<zip do Roboflow>"
    .venv/Scripts/python.exe scripts/train_yolo.py --epochs 50

O dataset preparado é de **segmentação** (polígonos), por isso o padrão é
``yolo11n-seg.pt`` (tarefa ``segment``). Também dá para treinar detecção pura
usando ``--model yolo11n.pt`` depois de converter os rótulos para caixas.

Sobre a integração: o adaptador atual (``app/vision/opencv_classifier.py``) espera
um ONNX que devolva **um vetor de classes** por imagem. Um modelo YOLO exportado
devolve caixas/máscaras por objeto, então usá-lo na API exige um adaptador de
detecção (pegar a detecção de maior confiança e mapear o nome da classe para
``vision_label``). Este script só treina e exporta o artefato.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_DATA = Path("datasets") / "fruits-by-yolo-v1" / "data.yaml"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Treina o modelo de frutas (YOLO).")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="data.yaml preparado")
    parser.add_argument("--model", default="yolo11n-seg.pt", help="pesos iniciais (ex.: yolo11n-seg.pt)")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8, help="lote; em CPU, use um valor pequeno")
    parser.add_argument("--device", default=None, help="cpu, 0, ... (padrão: automático)")
    parser.add_argument("--project", default="runs/fruits", help="pasta de saída do treino")
    parser.add_argument("--name", default="fruits-by-yolo-v1")
    parser.add_argument("--export-onnx", action="store_true", help="exporta o melhor peso para ONNX")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.data.is_file():
        print(f"data.yaml não encontrado: {args.data}", file=sys.stderr)
        print("Rode antes: python scripts/prepare_dataset.py --zip <arquivo.zip>", file=sys.stderr)
        return 2

    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics não instalado. Rode:", file=sys.stderr)
        print("  .venv/Scripts/python.exe -m pip install ultralytics", file=sys.stderr)
        return 2

    if args.device is None:
        import torch

        device = 0 if torch.cuda.is_available() else "cpu"
        print(f"Dispositivo: {device} (torch.cuda.is_available={torch.cuda.is_available()})")
    else:
        device = args.device

    if device == "cpu":
        print(
            "AVISO: treino em CPU. O dataset tem ~2,9 mil imagens em 640x640; "
            "espere horas por dezenas de épocas. Para um teste rápido use "
            "--epochs 3 --imgsz 320 --batch 4."
        )

    model = YOLO(args.model)
    results = model.train(
        data=str(args.data),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        project=args.project,
        name=args.name,
        exist_ok=True,
    )

    best = Path(results.save_dir) / "weights" / "best.pt"
    print(f"Melhor peso: {best}")
    print(f"Métricas: {Path(results.save_dir) / 'results.csv'}")

    if args.export_onnx:
        exported = YOLO(str(best)).export(format="onnx", opset=12, imgsz=args.imgsz)
        print(f"ONNX exportado: {exported}")
        print(
            "Lembrete: o adaptador atual espera um classificador (vetor de classes); "
            "este ONNX é de detecção/segmentação e precisa de um adaptador próprio."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
