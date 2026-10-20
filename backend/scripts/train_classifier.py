"""Treina um classificador de frutas nos recortes do dataset e exporta ONNX.

Treino de **classificação** (uma fruta por recorte), pensado para rodar em CPU e
para ser consumido pelo adaptador atual da API
(``app/vision/opencv_classifier.py``): um ONNX que recebe ``1x3x224x224`` e
devolve um vetor de 9 classes.

Pré-requisitos:

    cd backend
    .venv/Scripts/python.exe -m pip install torch torchvision
    .venv/Scripts/python.exe scripts/prepare_dataset.py --zip "<zip do Roboflow>"
    .venv/Scripts/python.exe scripts/prepare_classifier_crops.py

Execução:

    .venv/Scripts/python.exe scripts/train_classifier.py --epochs 8

Saídas em ``runs/classifier/<run>/`` (ignorado pelo git): ``best.pt``,
``metrics.json``, ``metrics.md``, ``history.csv`` e, com ``--export-onnx``, o
modelo em ``models/``. O script imprime as variáveis de ambiente sugeridas.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CROPS = Path("datasets") / "fruits-by-yolo-v1-crops"
DEFAULT_ONNX = Path("models") / "fruits-mobilenetv2-baseline.onnx"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Treina o classificador de frutas (MobileNetV2).")
    parser.add_argument("--data", type=Path, default=DEFAULT_CROPS, help="pasta com train/val/test")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--workers", type=int, default=0, help="0 é o mais seguro no Windows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--no-class-weights", action="store_true", help="desativa pesos por classe")
    parser.add_argument(
        "--freeze-backbone",
        action="store_true",
        help="treina só a cabeça de classificação (muito mais rápido em CPU)",
    )
    parser.add_argument("--export-onnx", dest="export_onnx", action="store_true", default=True)
    parser.add_argument("--no-export", dest="export_onnx", action="store_false")
    parser.add_argument("--onnx-out", type=Path, default=DEFAULT_ONNX)
    return parser.parse_args(argv)


def compute_metrics(confusion: list[list[int]], classes: list[str]) -> dict[str, object]:
    """Acurácia, precisão/recall/F1 por classe e macro/média ponderada."""
    total = sum(sum(row) for row in confusion)
    correct = sum(confusion[i][i] for i in range(len(classes)))
    per_class = {}
    for index, name in enumerate(classes):
        tp = confusion[index][index]
        predicted = sum(confusion[row][index] for row in range(len(classes)))
        support = sum(confusion[index])
        precision = tp / predicted if predicted else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    evaluated = [name for name in classes if per_class[name]["support"] > 0]
    macro = {
        key: round(sum(per_class[name][key] for name in evaluated) / len(evaluated), 4)
        if evaluated
        else 0.0
        for key in ("precision", "recall", "f1")
    }
    weighted = {
        key: round(
            sum(per_class[name][key] * per_class[name]["support"] for name in evaluated) / total,
            4,
        )
        if total
        else 0.0
        for key in ("precision", "recall", "f1")
    }
    return {
        "accuracy": round(correct / total, 4) if total else 0.0,
        "macro": macro,
        "weighted": weighted,
        "per_class": per_class,
        "confusion": confusion,
        "total": total,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        import torch
        import torch.nn as nn
        from PIL import Image
        from torch.utils.data import DataLoader, Dataset
        from torchvision import models, transforms
    except ImportError:
        print("torch/torchvision não instalados. Rode:", file=sys.stderr)
        print("  .venv/Scripts/python.exe -m pip install torch torchvision", file=sys.stderr)
        return 2

    for split in ("train", "val", "test"):
        if not (args.data / split).is_dir():
            print(f"split ausente: {args.data / split}", file=sys.stderr)
            print("Rode antes: scripts/prepare_classifier_crops.py", file=sys.stderr)
            return 2

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(os.cpu_count() or 4)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_tf = transforms.Compose(
        [
            transforms.RandomResizedCrop(args.imgsz, scale=(0.6, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    eval_tf = transforms.Compose(
        [
            transforms.Resize(int(args.imgsz * 1.14)),
            transforms.CenterCrop(args.imgsz),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    classes = [
        line.strip()
        for line in (args.data / "classes.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ] if (args.data / "classes.txt").is_file() else sorted(
        path.name for path in (args.data / "train").iterdir() if path.is_dir()
    )

    class CropDataset(Dataset):  # type: ignore[misc]
        """Recortes por pasta de classe, aceitando classes sem amostras."""

        def __init__(self, root: Path, transform: object) -> None:
            self.samples: list[tuple[Path, int]] = []
            self.transform = transform
            for index, name in enumerate(classes):
                class_dir = root / name
                if not class_dir.is_dir():
                    continue
                for path in sorted(class_dir.iterdir()):
                    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                        self.samples.append((path, index))

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, index: int):
            path, label = self.samples[index]
            with Image.open(path) as image:
                return self.transform(image.convert("RGB")), label

    train_ds = CropDataset(args.data / "train", train_tf)
    val_ds = CropDataset(args.data / "val", eval_tf)
    test_ds = CropDataset(args.data / "test", eval_tf)

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=args.workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=args.workers)
    test_loader = DataLoader(test_ds, batch_size=args.batch, shuffle=False, num_workers=args.workers)

    model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.IMAGENET1K_V1)
    model.classifier[1] = nn.Linear(model.last_channel, len(classes))
    model.to(device)

    if args.freeze_backbone:
        for parameter in model.features.parameters():
            parameter.requires_grad = False

    weights = None
    if not args.no_class_weights:
        counts = [0] * len(classes)
        for _, label in train_ds.samples:
            counts[label] += 1
        total = sum(counts)
        weights = torch.tensor(
            [total / (len(classes) * count) if count else 0.0 for count in counts],
            dtype=torch.float32,
            device=device,
        )

    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=args.lr,
        weight_decay=1e-4,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(args.epochs, 1))

    run_name = args.run_name or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = Path("runs") / "classifier" / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "labels.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")

    history: list[dict[str, float]] = []
    best_f1 = -1.0
    best_path = run_dir / "best.pt"

    def evaluate(loader) -> tuple[float, float, float]:
        model.eval()
        confusion = [[0] * len(classes) for _ in classes]
        loss_sum = 0.0
        with torch.no_grad():
            for images, labels in loader:
                images, labels = images.to(device), labels.to(device)
                logits = model(images)
                loss_sum += float(criterion(logits, labels)) * labels.size(0)
                predictions = logits.argmax(dim=1)
                for truth, predicted in zip(labels.tolist(), predictions.tolist(), strict=True):
                    confusion[truth][predicted] += 1
        total = sum(sum(row) for row in confusion)
        correct = sum(confusion[i][i] for i in range(len(classes)))
        accuracy = correct / total if total else 0.0
        metrics = compute_metrics(confusion, classes)
        return loss_sum / max(total, 1), accuracy, metrics["macro"]["f1"]  # type: ignore[index,return-value]

    print(f"Classes ({len(classes)}): {', '.join(classes)}")
    print(f"Treino: {len(train_ds)} | validação: {len(val_ds)} | teste: {len(test_ds)} | dispositivo: {device}")

    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        if args.freeze_backbone:
            # Mantém BatchNorm congelado junto com as features.
            model.features.eval()
        running = 0.0
        seen = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            running += float(loss.detach()) * labels.size(0)
            seen += labels.size(0)
        scheduler.step()

        val_loss, val_acc, val_f1 = evaluate(val_loader)
        elapsed = time.perf_counter() - started
        history.append(
            {
                "epoch": epoch,
                "train_loss": round(running / max(seen, 1), 4),
                "val_loss": round(val_loss, 4),
                "val_accuracy": round(val_acc, 4),
                "val_macro_f1": round(val_f1, 4),
                "seconds": round(elapsed, 1),
            }
        )
        marker = ""
        if val_f1 > best_f1:
            best_f1 = val_f1
            torch.save(model.state_dict(), best_path)
            marker = "  <- melhor"
        print(
            f"época {epoch:02d}/{args.epochs}: treino_loss={running / max(seen, 1):.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} val_f1_macro={val_f1:.4f} "
            f"({elapsed:.0f}s){marker}"
        )

    with (run_dir / "history.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(history[0].keys()))
        writer.writeheader()
        writer.writerows(history)

    model.load_state_dict(torch.load(best_path, map_location=device))
    model.to(device)
    test_loss, test_acc, _ = evaluate(test_loader)
    model.eval()
    confusion = [[0] * len(classes) for _ in classes]
    with torch.no_grad():
        for images, labels in test_loader:
            predictions = model(images.to(device)).argmax(dim=1)
            for truth, predicted in zip(labels.tolist(), predictions.tolist(), strict=True):
                confusion[truth][predicted] += 1
    metrics = compute_metrics(confusion, classes)

    result = {
        "run": run_name,
        "dataset": str(args.data),
        "classes": classes,
        "epochs": args.epochs,
        "batch": args.batch,
        "lr": args.lr,
        "imgsz": args.imgsz,
        "class_weights": weights.tolist() if weights is not None else None,
        "freeze_backbone": args.freeze_backbone,
        "best_val_macro_f1": round(best_f1, 4),
        "test": {"loss": round(test_loss, 4), "accuracy": test_acc, **metrics},
        "history": history,
    }
    (run_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        f"# Baseline — {run_name}",
        "",
        f"- Dataset: `{args.data}` ({len(train_ds)} treino / {len(val_ds)} validação / {len(test_ds)} teste)",
        f"- Modelo: MobileNetV2 (ImageNet) ajustado para {len(classes)} classes",
        f"- Épocas: {args.epochs} | lote: {args.batch} | lr: {args.lr} | entrada: {args.imgsz}px",
        "",
        f"**Teste:** acurácia **{metrics['accuracy']:.2%}**, F1 macro **{metrics['macro']['f1']:.4f}**, "
        f"F1 ponderado **{metrics['weighted']['f1']:.4f}** ({metrics['total']} recortes).",
        "",
        "| Classe | Precisão | Recall | F1 | Suporte |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name in classes:
        row = metrics["per_class"][name]  # type: ignore[index]
        lines.append(
            f"| {name} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1']:.3f} | {row['support']} |"
        )
    (run_dir / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\nTeste: acurácia={metrics['accuracy']:.4f} F1_macro={metrics['macro']['f1']:.4f}")
    for name in classes:
        row = metrics["per_class"][name]  # type: ignore[index]
        print(
            f"  {name:12s} precisão={row['precision']:.3f} recall={row['recall']:.3f} "
            f"f1={row['f1']:.3f} suporte={row['support']}"
        )
    print(f"Peso: {best_path}")

    if args.export_onnx:
        args.onnx_out.parent.mkdir(parents=True, exist_ok=True)
        dummy = torch.randn(1, 3, args.imgsz, args.imgsz, device=device)
        export_kwargs = dict(
            input_names=["input"],
            output_names=["logits"],
            opset_version=12,
            do_constant_folding=True,
        )
        try:
            try:
                torch.onnx.export(model, dummy, str(args.onnx_out), dynamo=False, **export_kwargs)
            except TypeError:
                torch.onnx.export(model, dummy, str(args.onnx_out), **export_kwargs)
        except Exception as exc:  # noqa: BLE001 - falha de dependência/exportação
            print(f"Falha ao exportar ONNX: {exc}", file=sys.stderr)
            print(
                "Instale o pacote necessário (pip install onnx) e rode "
                "scripts/export_classifier_onnx.py para exportar sem retreinar.",
                file=sys.stderr,
            )
            return 1
        labels_out = args.onnx_out.with_suffix(".labels.txt")
        labels_out.write_text("\n".join(classes) + "\n", encoding="utf-8")
        print(f"ONNX: {args.onnx_out}")
        print(f"Rótulos: {labels_out}")
        print("\nConfiguração sugerida no backend/.env:")
        print(f"MODEL_PATH={args.onnx_out.as_posix()}")
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
