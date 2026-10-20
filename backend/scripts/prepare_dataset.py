"""Extrai e valida um dataset YOLO exportado do Roboflow.

O script não treina nada: apenas descompacta o ZIP em ``datasets/<nome>``,
conserta os caminhos do ``data.yaml`` (exportações do Roboflow costumam vir com
``../train/images``, que não funciona quando o YAML está na raiz) e confere as
anotações antes de qualquer treino.

Exemplo:

    cd backend
    .venv/Scripts/python.exe scripts/prepare_dataset.py \
        --zip "$HOME/Downloads/Fruits by YOLO.v1-fruits-detection.yolo26.zip"

Saída:
* ``datasets/fruits-by-yolo-v1/data.yaml``   — caminhos normalizados;
* ``datasets/fruits-by-yolo-v1/classes.txt`` — um nome de classe por linha;
* ``datasets/fruits-by-yolo-v1/dataset_report.json`` — contagens e problemas.

O diretório ``datasets/`` é ignorado pelo git (dataset não versionado).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLITS = ("train", "valid", "test")
CLASS_ID_RE = re.compile(r"^nc:\s*(\d+)\s*$", re.MULTILINE)
NAMES_RE = re.compile(r"^names:\s*(.+)$", re.MULTILINE)
SPLIT_RE = re.compile(r"^(train|val|test):\s*(\S+)\s*$", re.MULTILINE)

DEFAULT_DEST = Path("datasets") / "fruits-by-yolo-v1"


def safe_extract(archive: zipfile.ZipFile, dest: Path) -> None:
    """Extrai sem permitir caminhos que escapem do diretório de destino."""
    root = dest.resolve()
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if root not in target.parents and target != root:
            raise SystemExit(f"Entrada suspeita no ZIP (fora do destino): {member.filename}")
    archive.extractall(root)


def parse_names(text: str) -> list[str]:
    """Lê a lista ``names`` do data.yaml (formato lista ou dicionário)."""
    match = NAMES_RE.search(text)
    if match is None:
        raise SystemExit("data.yaml sem a chave 'names'.")

    raw = match.group(1).strip()
    if raw.startswith("["):
        names = ast.literal_eval(raw)
    else:
        # Formato dicionário: "names:\n  0: Apple\n  1: Banana"
        block = text[match.end() :]
        pairs = re.findall(r"^\s*(\d+):\s*['\"]?([^'\"\n]+?)['\"]?\s*$", block, re.MULTILINE)
        if not pairs:
            raise SystemExit("Não foi possível interpretar a chave 'names' do data.yaml.")
        names = [name for _, name in sorted(pairs, key=lambda item: int(item[0]))]

    labels = [str(name).strip() for name in names]
    if not labels or any(not label for label in labels):
        raise SystemExit("data.yaml com nomes de classe vazios.")
    return labels


def resolve_split_dir(yaml_dir: Path, value: str) -> Path:
    """Resolve o caminho de um split, tolerando o ``../`` das exportações."""
    parts = [part for part in value.replace("\\", "/").split("/") if part not in ("", ".")]
    while parts and parts[0] == "..":
        parts = parts[1:]
    candidate = yaml_dir.joinpath(*parts)
    if candidate.is_dir():
        return candidate
    # Exportações aninhadas: o YAML pode estar um nível acima das pastas.
    for parent in (yaml_dir, yaml_dir.parent):
        candidate = parent.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    raise SystemExit(f"Pasta do split não encontrada: {value}")


def classify_line(fields: list[str]) -> str | None:
    """Classifica uma linha YOLO como 'box', 'polygon' ou inválida (None).

    Roboflow exporta ``class cx cy w h`` para detecção simples e
    ``class x1 y1 x2 y2 ...`` (polígono) quando as anotações são segmentação.
    """
    if len(fields) == 5:
        return "box"
    if len(fields) >= 7 and len(fields) % 2 == 1:
        return "polygon"
    return None


def validate_split(images_dir: Path, num_classes: int) -> tuple[dict[str, object], list[str]]:
    """Confere imagens/rótulos de um split e devolve contagens e problemas."""
    labels_dir = images_dir.parent / "labels"
    images = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    labels = sorted(labels_dir.glob("*.txt")) if labels_dir.is_dir() else []
    image_stems = {p.stem for p in images}
    label_stems = {p.stem for p in labels}

    problems: list[str] = []
    empty_labels = 0
    boxes = 0
    polygons = 0
    out_of_range = 0
    bad_lines = 0

    for path in labels:
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            empty_labels += 1
            continue
        for line in lines:
            fields = line.split()
            kind = classify_line(fields)
            if kind is None:
                bad_lines += 1
                continue
            try:
                class_id = int(fields[0])
                coords = [float(value) for value in fields[1:]]
            except ValueError:
                bad_lines += 1
                continue
            if not 0 <= class_id < num_classes:
                problems.append(f"{path.relative_to(path.parents[1])}: classe inválida {class_id}")
                continue
            if any(not 0.0 <= value <= 1.0 for value in coords):
                out_of_range += 1
                continue
            if kind == "box" and (coords[2] <= 0.0 or coords[3] <= 0.0):
                out_of_range += 1
                continue
            if kind == "box":
                boxes += 1
            else:
                polygons += 1

    if not images:
        problems.append(f"{images_dir}: nenhuma imagem encontrada")
    missing = sorted(image_stems - label_stems)
    orphan = sorted(label_stems - image_stems)
    if missing:
        problems.append(f"{len(missing)} imagem(ns) sem rótulo (ex.: {missing[0]})")
    if orphan:
        problems.append(f"{len(orphan)} rótulo(s) sem imagem (ex.: {orphan[0]})")
    if bad_lines:
        problems.append(f"{labels_dir}: {bad_lines} linha(s) malformada(s)")
    if out_of_range:
        problems.append(f"{labels_dir}: {out_of_range} anotação(ões) fora de [0,1]")

    if boxes and polygons:
        annotation_format = "mista"
    elif polygons:
        annotation_format = "segmentation"
    elif boxes:
        annotation_format = "detection"
    else:
        annotation_format = "vazia"

    summary = {
        "images": len(images),
        "labels": len(labels),
        "instances": boxes + polygons,
        "boxes": boxes,
        "polygons": polygons,
        "annotation_format": annotation_format,
        "images_without_label": len(missing),
        "labels_without_image": len(orphan),
        "empty_labels": empty_labels,
        "out_of_range_annotations": out_of_range,
        "malformed_lines": bad_lines,
    }
    return summary, problems


def scan_formats(dataset_dir: Path) -> tuple[int, int]:
    """Conta anotações no formato caixa e no formato polígono."""
    boxes = 0
    polygons = 0
    for split in SPLITS:
        labels_dir = dataset_dir / split / "labels"
        if not labels_dir.is_dir():
            continue
        for path in labels_dir.glob("*.txt"):
            for line in path.read_text(encoding="utf-8").splitlines():
                kind = classify_line(line.split())
                if kind == "box":
                    boxes += 1
                elif kind == "polygon":
                    polygons += 1
    return boxes, polygons


def convert_boxes_to_polygons(dataset_dir: Path) -> int:
    """Converte anotações ``cx cy w h`` em retângulos de 4 pontos.

    Um arquivo de rótulos de segmentação não aceita linhas de caixa junto com
    polígonos; a conversão preserva a área anotada sem perda relevante.
    """
    converted = 0
    for split in SPLITS:
        labels_dir = dataset_dir / split / "labels"
        if not labels_dir.is_dir():
            continue
        for path in labels_dir.glob("*.txt"):
            lines = path.read_text(encoding="utf-8").splitlines()
            output: list[str] = []
            changed = False
            for line in lines:
                fields = line.split()
                if classify_line(fields) == "box":
                    class_id = int(fields[0])
                    cx, cy, width, height = (float(value) for value in fields[1:])
                    x1 = min(max(cx - width / 2, 0.0), 1.0)
                    y1 = min(max(cy - height / 2, 0.0), 1.0)
                    x2 = min(max(cx + width / 2, 0.0), 1.0)
                    y2 = min(max(cy + height / 2, 0.0), 1.0)
                    output.append(
                        f"{class_id} {x1:.7f} {y1:.7f} {x2:.7f} {y1:.7f} "
                        f"{x2:.7f} {y2:.7f} {x1:.7f} {y2:.7f}"
                    )
                    changed = True
                    converted += 1
                else:
                    output.append(line)
            if changed:
                path.write_text("\n".join(output) + "\n", encoding="utf-8")
    return converted


def class_counts(dataset_dir: Path, names: list[str]) -> Counter[str]:
    """Conta caixas por classe em todos os splits."""
    counts: Counter[str] = Counter()
    for split in SPLITS:
        labels_dir = dataset_dir / split / "labels"
        if not labels_dir.is_dir():
            continue
        for path in labels_dir.glob("*.txt"):
            for line in path.read_text(encoding="utf-8").splitlines():
                fields = line.split()
                if classify_line(fields) is None or not fields[0].isdigit():
                    continue
                index = int(fields[0])
                if 0 <= index < len(names):
                    counts[names[index]] += 1
    return counts


def write_normalized_yaml(path: Path, names: list[str]) -> None:
    """Reescreve o data.yaml com caminhos relativos à pasta do YAML."""
    lines = [
        "# Normalizado por scripts/prepare_dataset.py (caminhos relativos ao YAML).",
        "train: train/images",
        "val: valid/images",
        "test: test/images",
        "",
        f"nc: {len(names)}",
        "names: [" + ", ".join(repr(name) for name in names) + "]",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare(zip_path: Path, dest: Path, force: bool) -> int:
    if not zip_path.is_file():
        raise SystemExit(f"ZIP não encontrado: {zip_path}")
    if dest.exists():
        if not force:
            raise SystemExit(f"Destino já existe: {dest}. Use --force para reextrair.")
        for child in dest.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        safe_extract(archive, dest)

    yaml_candidates = sorted(dest.rglob("data.yaml"), key=lambda p: len(p.parts))
    if not yaml_candidates:
        raise SystemExit("data.yaml não encontrado dentro do ZIP.")
    yaml_path = yaml_candidates[0]
    text = yaml_path.read_text(encoding="utf-8")

    nc_match = CLASS_ID_RE.search(text)
    names = parse_names(text)
    nc = int(nc_match.group(1)) if nc_match else len(names)
    if nc != len(names):
        raise SystemExit(f"data.yaml inconsistente: nc={nc} mas {len(names)} nomes.")

    splits_found = {key: value for key, value in SPLIT_RE.findall(text)}
    dataset_dir = yaml_path.parent

    report: dict[str, object] = {
        "source_zip": zip_path.name,
        "dataset_dir": str(dataset_dir),
        "classes": names,
        "source_yaml": str(yaml_path),
        "splits": {},
        "problems": [],
    }
    problems: list[str] = []

    box_lines, polygon_lines = scan_formats(dataset_dir)
    converted = 0
    if box_lines and polygon_lines:
        # Rótulos de segmentação não podem misturar caixas com polígonos.
        converted = convert_boxes_to_polygons(dataset_dir)
        report["converted_boxes_to_polygons"] = converted

    for split in SPLITS:
        key = "val" if split == "valid" else split
        if key not in splits_found:
            problems.append(f"{split}: split ausente no data.yaml")
            continue
        images_dir = resolve_split_dir(dataset_dir, splits_found[key])
        summary, split_problems = validate_split(images_dir, nc)
        report["splits"][split] = summary  # type: ignore[index]
        problems.extend(split_problems)

    counts = class_counts(dataset_dir, names)
    report["boxes_per_class"] = dict(counts)
    empty_classes = [name for name in names if counts[name] == 0]
    if empty_classes:
        problems.append("classes sem nenhuma caixa: " + ", ".join(empty_classes))

    write_normalized_yaml(yaml_path if yaml_path.parent == dataset_dir else dataset_dir / "data.yaml", names)
    (dataset_dir / "classes.txt").write_text("\n".join(names) + "\n", encoding="utf-8")

    formats = {str(s["annotation_format"]) for s in report["splits"].values()}  # type: ignore[union-attr]
    report["annotation_format"] = formats.pop() if len(formats) == 1 else "mista"

    report["problems"] = problems
    report_path = dataset_dir / "dataset_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total_images = sum(int(s["images"]) for s in report["splits"].values())  # type: ignore[union-attr]
    total_instances = sum(int(s["instances"]) for s in report["splits"].values())  # type: ignore[union-attr]
    total_polygons = sum(int(s["polygons"]) for s in report["splits"].values())  # type: ignore[union-attr]
    total_boxes = sum(int(s["boxes"]) for s in report["splits"].values())  # type: ignore[union-attr]
    print(f"Dataset extraído em: {dataset_dir}")
    print(f"Classes ({nc}): {', '.join(names)}")
    print(
        f"Imagens: {total_images} | instâncias: {total_instances} "
        f"(caixas: {total_boxes}, polígonos: {total_polygons})"
    )
    print(f"Formato das anotações: {report['annotation_format']}")
    if converted:
        print(f"Anotações de caixa convertidas para polígono: {converted}")
    for split, summary in report["splits"].items():  # type: ignore[union-attr]
        print(
            f"  {split:5s} imagens={summary['images']:4d} instâncias={summary['instances']:5d} "
            f"forma={summary['annotation_format']:12s} "
            f"sem_rótulo={summary['images_without_label']} vazios={summary['empty_labels']}"
        )
    print("Caixas por classe:")
    for name, value in counts.most_common():
        print(f"  {name:14s} {value}")
    print(f"data.yaml normalizado: {dataset_dir / 'data.yaml'}")
    print(f"relatório: {report_path}")

    if problems:
        print("\nPROBLEMAS ENCONTRADOS:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nValidação concluída sem problemas.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extrai e valida um dataset YOLO do Roboflow.")
    parser.add_argument("--zip", required=True, type=Path, help="arquivo ZIP exportado do Roboflow")
    parser.add_argument(
        "--dest",
        type=Path,
        default=DEFAULT_DEST,
        help=f"diretório de destino (padrão: {DEFAULT_DEST})",
    )
    parser.add_argument("--force", action="store_true", help="reextrai mesmo se o destino existir")
    args = parser.parse_args(argv)

    return prepare(args.zip.expanduser(), args.dest, args.force)


if __name__ == "__main__":
    sys.exit(main())
