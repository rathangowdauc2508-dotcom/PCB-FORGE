"""Convert the research-use DeepPCB annotations into PCB Forge's YOLO dataset layout."""
from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

from train_pcb_detector import CLASS_NAMES

# DeepPCB IDs: 1 open, 2 short, 3 mousebite, 4 spur, 5 copper, 6 pin-hole.
DEEPPPCB_TO_FORGE = {1: 2, 2: 3, 3: 1, 4: 4, 5: 5, 6: 0}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _rows(list_file: Path) -> list[tuple[Path, Path]]:
    rows = []
    for number, line in enumerate(list_file.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 2:
            raise ValueError(f"{list_file}:{number}: expected image path and annotation path")
        rows.append((Path(fields[0]), Path(fields[1])))
    return rows


def _convert_label(annotation: Path, image: Path, output: Path) -> int:
    from PIL import Image

    width, height = Image.open(image).size
    lines = []
    for number, line in enumerate(annotation.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = [part.strip() for part in line.split(",")]
        if len(fields) != 5:
            raise ValueError(f"{annotation}:{number}: expected x1,y1,x2,y2,class_id")
        try:
            x1, y1, x2, y2 = (float(value) for value in fields[:4])
            source_id = int(fields[4])
            target_id = DEEPPPCB_TO_FORGE[source_id]
        except (ValueError, KeyError) as exc:
            raise ValueError(f"{annotation}:{number}: invalid DeepPCB box or class") from exc
        if x2 <= x1 or y2 <= y1 or x1 < 0 or y1 < 0 or x2 > width or y2 > height:
            raise ValueError(f"{annotation}:{number}: box lies outside the source image")
        cx, cy = (x1 + x2) / (2 * width), (y1 + y2) / (2 * height)
        box_w, box_h = (x2 - x1) / width, (y2 - y1) / height
        lines.append(f"{target_id} {cx:.6f} {cy:.6f} {box_w:.6f} {box_h:.6f}")
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def convert(source: Path, output: Path, val_fraction: float, seed: int) -> tuple[int, int, int]:
    pcb_data = source / "PCBData" if (source / "PCBData").is_dir() else source
    trainval_file, test_file = pcb_data / "trainval.txt", pcb_data / "test.txt"
    if not trainval_file.is_file() or not test_file.is_file():
        raise ValueError("Select the extracted DeepPCB repository folder containing PCBData/trainval.txt and PCBData/test.txt")
    trainval, test = _rows(trainval_file), _rows(test_file)
    groups = sorted({image.parts[0] for image, _ in trainval})
    if len(groups) < 2:
        raise ValueError("DeepPCB trainval list must contain at least two board groups for a group-wise validation split")
    rng = random.Random(seed)
    rng.shuffle(groups)
    val_count = max(1, round(len(groups) * val_fraction))
    val_groups = set(groups[:val_count])
    splits = {
        "train": [(image, label) for image, label in trainval if image.parts[0] not in val_groups],
        "val": [(image, label) for image, label in trainval if image.parts[0] in val_groups],
        "test": test,
    }
    counts = {}
    for split, pairs in splits.items():
        for relative_image, relative_label in pairs:
            image, annotation = pcb_data / relative_image, pcb_data / relative_label
            if not image.is_file() or not annotation.is_file():
                raise ValueError(f"DeepPCB file missing: {image if not image.is_file() else annotation}")
            safe_name = "__".join(relative_image.with_suffix("").parts)
            output_image = output / "images" / split / f"{safe_name}{image.suffix.lower()}"
            output_label = output / "labels" / split / f"{safe_name}.txt"
            output_image.parent.mkdir(parents=True, exist_ok=True)
            output_label.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, output_image)
            _convert_label(annotation, image, output_label)
        counts[split] = len(pairs)

    yaml = ["path: .", "train: images/train", "val: images/val", "test: images/test", "", "names:"]
    yaml.extend(f"  - {name}" for name in CLASS_NAMES)
    (output / "dataset.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    attribution = (
        "Dataset: DeepPCB, https://github.com/tangsanli5201/DeepPCB\n"
        "The source README limits use to research purposes.\n"
        "DeepPCB class IDs were mapped: open→open_circuit, short→short, mousebite→mouse_bite, "
        "spur→spur, copper→spurious_copper, pin-hole→missing_hole.\n"
        f"Group-wise validation split seed: {seed}; train/val/test images: "
        f"{counts['train']}/{counts['val']}/{counts['test']}.\n"
        "This converted dataset is not evidence of accuracy on unrelated assembled PCB photos.\n"
    )
    (output / "SOURCE_ATTRIBUTION.txt").write_text(attribution, encoding="utf-8")
    return counts["train"], counts["val"], counts["test"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Extracted DeepPCB repo root or its PCBData directory")
    parser.add_argument("--output", default=str(Path(__file__).resolve().parents[1] / "data" / "pcb-defects"))
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0.05 <= args.val_fraction <= 0.4:
        raise SystemExit("--val-fraction must be between 0.05 and 0.4")
    try:
        counts = convert(Path(args.source).expanduser().resolve(), Path(args.output).expanduser().resolve(), args.val_fraction, args.seed)
    except (OSError, ValueError) as error:
        raise SystemExit(f"Conversion stopped: {error}") from error
    print(f"Converted PCB Forge dataset: train={counts[0]}, val={counts[1]}, test={counts[2]}")
    print("Research-use data only. Inspect SOURCE_ATTRIBUTION.txt and test on your own boards.")


if __name__ == "__main__":
    main()
