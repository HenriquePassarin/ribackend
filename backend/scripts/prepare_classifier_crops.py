"""Gera recortes (crops) rotulados a partir dos polígonos do dataset YOLO.

Cada anotação do dataset vira uma imagem de treino para **classificação**: o
recorte da região anotada (com uma pequena margem) é salvo em
``datasets/fruits-by-yolo-v1-crops/<split>/<classe>/``.

Isso permite treinar um classificador (compatível com o adaptador
``app/vision/opencv_classifier.py``) sem depender de treino de detecção, que é
muito mais caro em CPU.

Uso:

    cd backend
    .venv/Scripts/python.exe scripts/prepare_classifier_crops.py

Saída padrão: ``datasets/fruits-by-yolo-v1-crops/`` (ignorado pelo git) com
``train/``, ``val/`` e ``test/`` no formato ``ImageFolder`` do torchvision, além
de ``crops_report.json``.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

DEFAULT_DATASET = Path("datasets") / "fruits-by-yolo-v1"
DEFAULT_DEST = Path("datasets") / "fruits-by-yolo-v1-crops"
SPLITS = (("train", "train"), ("valid", "val"), ("test", "test"))
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_polygons(label_path: Path) -> list[tuple[int, np.ndarray]]:
    """Devolve (classe, pontos Nx2) de um arquivo de rótulos YOLO."""
    objects: list[tuple[int, np.ndarray]] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 7 or len(fields) % 2 == 0:
            continue
        try:
            class_id = int(fields[0])
            coords = np.asarray([float(value) for value in fields[1:]], dtype=np.float32)
        except ValueError:
            continue
        objects.append((class_id, coords.reshape(-1, 2)))
    return objects


def crop_objects(
    image: np.ndarray, points: np.ndarray, padding: float
) -> tuple[np.ndarray, np.ndarray]:
    """Recorta a caixa envolvente do polígono, com margem proporcional."""
    height, width = image.shape[:2]
    x1, y1 = points.min(axis=0)
    x2, y2 = points.max(axis=0)
    box_w, box_h = x2 - x1, y2 - y1
    margin = padding * max(box_w, box_h)

    left = int(np.clip((x1 - margin) * width, 0, width - 1))
    top = int(np.clip((y1 - margin) * height, 0, height - 1))
    right = int(np.clip((x2 + margin) * width, left + 1, width))
    bottom = int(np.clip((y2 + margin) * height, top + 1, height))
    return image[top:bottom, left:right], np.array([left, top, right, bottom])


def prepare(dataset: Path, dest: Path, size: int, padding: float, quality: int, force: bool) -> int:
    yaml_path = dataset / "data.yaml"
    if not yaml_path.is_file():
        print(f"data.yaml não encontrado em {dataset}. Rode scripts/prepare_dataset.py.", file=sys.stderr)
        return 2

    classes_path = dataset / "classes.txt"
    if not classes_path.is_file():
        print(f"classes.txt não encontrado em {dataset}.", file=sys.stderr)
        return 2
    classes = [line.strip() for line in classes_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    if dest.exists() and any(dest.iterdir()):
        if not force:
            print(f"Destino já existe: {dest}. Use --force para regenerar.", file=sys.stderr)
            return 2
        import shutil

        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")

    report: dict[str, object] = {"classes": classes, "splits": {}, "problems": []}
    problems: list[str] = []

    for source, target in SPLITS:
        images_dir = dataset / source / "images"
        labels_dir = dataset / source / "labels"
        if not images_dir.is_dir():
            problems.append(f"split ausente: {source}")
            continue

        counts: Counter[str] = Counter()
        skipped_without_label = 0
        images_with_objects = 0
        images = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)

        for image_path in images:
            label_path = labels_dir / f"{image_path.stem}.txt"
            objects = parse_polygons(label_path) if label_path.is_file() else []
            if not objects:
                skipped_without_label += 1
                continue
            image = cv2.imread(str(image_path))
            if image is None:
                problems.append(f"imagem ilegível: {image_path.name}")
                continue
            images_with_objects += 1
            for index, (class_id, points) in enumerate(objects):
                if not 0 <= class_id < len(classes):
                    problems.append(f"{label_path.name}: classe inválida {class_id}")
                    continue
                crop, _ = crop_objects(image, points, padding)
                if crop.size == 0:
                    continue
                crop = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
                class_dir = dest / target / classes[class_id]
                class_dir.mkdir(parents=True, exist_ok=True)
                output = class_dir / f"{image_path.stem}_{index:03d}.jpg"
                cv2.imwrite(str(output), crop, [cv2.IMWRITE_JPEG_QUALITY, quality])
                counts[classes[class_id]] += 1

        # Mantém todas as classes em todos os splits, mesmo sem amostras, para que
        # o ImageFolder do torchvision use o mesmo mapeamento de índices.
        for name in classes:
            (dest / target / name).mkdir(parents=True, exist_ok=True)

        report["splits"][target] = {  # type: ignore[index]
            "images_scanned": len(images),
            "images_with_objects": images_with_objects,
            "images_without_annotation": skipped_without_label,
            "crops": dict(counts),
            "total_crops": sum(counts.values()),
        }

    report["problems"] = problems
    report_path = dest / "crops_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(int(s["total_crops"]) for s in report["splits"].values())  # type: ignore[union-attr]
    print(f"Recortes gerados em: {dest} ({size}x{size}, margem {padding:.0%})")
    print(f"Total de recortes: {total}")
    for split, summary in report["splits"].items():  # type: ignore[union-attr]
        print(
            f"  {split:5s} imagens={summary['images_scanned']:4d} "
            f"com_objetos={summary['images_with_objects']:4d} "
            f"recortes={summary['total_crops']:5d}"
        )
    print("Recortes por classe:")
    for name in classes:
        values = {split: int(s["crops"].get(name, 0)) for split, s in report["splits"].items()}  # type: ignore[union-attr]
        print(
            f"  {name:12s} treino={values['train']:4d} validação={values['val']:3d} teste={values['test']:3d}"
        )
    if problems:
        print("\nPROBLEMAS:")
        for problem in problems[:20]:
            print(f"  - {problem}")
        return 1
    print("\nRecortes gerados sem problemas.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera recortes rotulados para classificação.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    parser.add_argument("--size", type=int, default=256, help="lado do recorte salvo (px)")
    parser.add_argument("--padding", type=float, default=0.12, help="margem em torno da caixa")
    parser.add_argument("--quality", type=int, default=92, help="qualidade JPEG")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return prepare(args.dataset, args.dest, args.size, args.padding, args.quality, args.force)


if __name__ == "__main__":
    sys.exit(main())
