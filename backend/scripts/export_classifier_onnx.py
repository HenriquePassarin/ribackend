"""Exporta o checkpoint do classificador (``best.pt``) para ONNX.

Usado quando o treino terminou mas a exportação falhou ou quando se quer
reexportar com outra entrada, sem retreinar:

    cd backend
    .venv/Scripts/python.exe scripts/export_classifier_onnx.py \
        --checkpoint runs/classifier/baseline-mobilenetv2/best.pt \
        --labels runs/classifier/baseline-mobilenetv2/labels.txt \
        --out models/fruits-mobilenetv2-baseline.onnx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_CHECKPOINT = Path("runs") / "classifier" / "baseline-mobilenetv2" / "best.pt"
DEFAULT_LABELS = Path("runs") / "classifier" / "baseline-mobilenetv2" / "labels.txt"
DEFAULT_OUT = Path("models") / "fruits-mobilenetv2-baseline.onnx"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exporta o classificador treinado para ONNX.")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--imgsz", type=int, default=224)
    args = parser.parse_args(argv)

    if not args.checkpoint.is_file():
        print(f"checkpoint não encontrado: {args.checkpoint}", file=sys.stderr)
        return 2
    if not args.labels.is_file():
        print(f"labels não encontrado: {args.labels}", file=sys.stderr)
        return 2

    try:
        import torch
        import torch.nn as nn
        from torchvision import models
    except ImportError:
        print("torch/torchvision não instalados. Rode:", file=sys.stderr)
        print("  .venv/Scripts/python.exe -m pip install torch torchvision", file=sys.stderr)
        return 2

    classes = [line.strip() for line in args.labels.read_text(encoding="utf-8").splitlines() if line.strip()]
    model = models.mobilenet_v2(weights=None)
    model.classifier[1] = nn.Linear(model.last_channel, len(classes))
    model.load_state_dict(torch.load(args.checkpoint, map_location="cpu", weights_only=True))
    model.eval()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    dummy = torch.randn(1, 3, args.imgsz, args.imgsz)
    export_kwargs = dict(
        input_names=["input"],
        output_names=["logits"],
        opset_version=12,
        do_constant_folding=True,
    )
    try:
        torch.onnx.export(model, dummy, str(args.out), dynamo=False, **export_kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, str(args.out), **export_kwargs)

    labels_out = args.out.with_suffix(".labels.txt")
    labels_out.write_text("\n".join(classes) + "\n", encoding="utf-8")

    print(f"ONNX exportado: {args.out} ({args.out.stat().st_size / 1e6:.1f} MB)")
    print(f"Rótulos: {labels_out} ({len(classes)} classes)")
    print("\nConfiguração sugerida no backend/.env:")
    print(f"MODEL_PATH={args.out.as_posix()}")
    print(f"MODEL_LABELS_PATH={labels_out.as_posix()}")
    print(f"MODEL_INPUT_SIZE={args.imgsz}")
    print("MODEL_INPUT_SCALE=0.00392156862745098")
    print("MODEL_INPUT_MEAN=0.485,0.456,0.406")
    print("MODEL_INPUT_STD=0.229,0.224,0.225")
    print("MODEL_SWAP_RB=true")
    print("MODEL_OUTPUT_SOFTMAX=true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
