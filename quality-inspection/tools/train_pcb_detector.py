"""Train PCB Forge's six-class detector from random initialization and labeled data."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUALITY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = QUALITY_ROOT / "data" / "pcb-defects" / "dataset.yaml"
CLASS_NAMES = ["missing_hole", "mouse_bite", "open_circuit", "short", "spur", "spurious_copper"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("Install quality-inspection/requirements-yolo.txt before training.") from exc
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not read dataset YAML: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("Dataset YAML must contain a mapping with path, train, val, and names.")
    return value


def validate_dataset(config_path: Path) -> tuple[Path, set[int]]:
    if not config_path.is_file():
        raise ValueError(f"Dataset configuration not found: {config_path}")
    config = _load_yaml(config_path)
    names = config.get("names")
    if isinstance(names, dict):
        names = [names[key] for key in sorted(names, key=lambda value: int(value))]
    if names != CLASS_NAMES:
        raise ValueError("Dataset class names/order must match dataset.yaml: " + ", ".join(CLASS_NAMES))

    dataset_root = Path(config.get("path", "."))
    if not dataset_root.is_absolute():
        dataset_root = (config_path.parent / dataset_root).resolve()
    seen_train_classes: set[int] = set()
    for split in ("train", "val"):
        image_dir = dataset_root / "images" / split
        label_dir = dataset_root / "labels" / split
        if not image_dir.is_dir() or not label_dir.is_dir():
            raise ValueError(f"Create both dataset folders: {image_dir} and {label_dir}")
        images = sorted(path for path in image_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
        if not images:
            raise ValueError(f"No images found in {image_dir}")
        for image in images:
            label = label_dir / image.relative_to(image_dir).with_suffix(".txt")
            if not label.is_file():
                raise ValueError(f"Missing label file for {image.name}: {label}")
            for line_number, raw_line in enumerate(label.read_text(encoding="utf-8").splitlines(), start=1):
                if not raw_line.strip():
                    continue
                parts = raw_line.split()
                if len(parts) != 5:
                    raise ValueError(f"{label}:{line_number}: expected class_id center_x center_y width height")
                try:
                    class_id = int(parts[0])
                    coords = [float(item) for item in parts[1:]]
                except ValueError as exc:
                    raise ValueError(f"{label}:{line_number}: labels must contain numeric YOLO values") from exc
                if not 0 <= class_id < len(CLASS_NAMES):
                    raise ValueError(f"{label}:{line_number}: class_id must be between 0 and 5")
                cx, cy, width, height = coords
                if not (0 <= cx <= 1 and 0 <= cy <= 1 and 0 < width <= 1 and 0 < height <= 1):
                    raise ValueError(f"{label}:{line_number}: normalized box values must be within 0..1")
                if split == "train":
                    seen_train_classes.add(class_id)

    missing_classes = sorted(set(range(len(CLASS_NAMES))) - seen_train_classes)
    if missing_classes:
        labels = ", ".join(CLASS_NAMES[index] for index in missing_classes)
        print(f"Warning: training labels contain no examples for: {labels}", file=sys.stderr)
    return dataset_root, seen_train_classes


def train(args: argparse.Namespace) -> Path:
    config_path = Path(args.data).expanduser().resolve()
    validate_dataset(config_path)
    if Path(args.architecture).suffix.lower() != ".yaml":
        raise ValueError("Use a YOLO architecture .yaml file so the detector starts from random weights, not a pretrained .pt model.")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError("Install the training package first: python -m pip install -r requirements-yolo.txt") from exc

    # A YAML architecture creates random initialization. No .pt/pretrained checkpoint is loaded.
    model = YOLO(args.architecture)
    result = model.train(
        data=str(config_path),
        epochs=args.epochs,
        imgsz=args.image_size,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        pretrained=False,
        seed=args.seed,
        project=str(QUALITY_ROOT / "runs"),
        name=args.run_name,
        exist_ok=False,
        save=True,
    )
    save_dir = getattr(result, "save_dir", None) or getattr(getattr(model, "trainer", None), "save_dir", None)
    if save_dir is None:
        raise RuntimeError("Training finished but Ultralytics did not report its output folder.")
    run_dir = Path(save_dir)
    best_weights = run_dir / "weights" / "best.pt"
    if not best_weights.is_file():
        raise RuntimeError(f"Training finished without a best checkpoint at {best_weights}")

    model_dir = QUALITY_ROOT / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    app_weights = model_dir / "best.pt"
    app_weights.write_bytes(best_weights.read_bytes())
    digest = hashlib.sha256(app_weights.read_bytes()).hexdigest()
    best_model = YOLO(str(best_weights))
    validation = best_model.val(data=str(config_path), split="val", imgsz=args.image_size, device=args.device)
    validation_metrics = {
        str(key): float(value)
        for key, value in getattr(validation, "results_dict", {}).items()
        if isinstance(value, (int, float))
    }
    metadata = {
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": args.architecture,
        "initialization": "random; pretrained weights disabled",
        "dataset_yaml": str(config_path),
        "classes": CLASS_NAMES,
        "epochs_requested": args.epochs,
        "image_size": args.image_size,
        "batch": args.batch,
        "seed": args.seed,
        "run_directory": str(run_dir),
        "weights_sha256": digest,
        "validation_metrics": validation_metrics,
    }
    (model_dir / "training-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (run_dir / "pcbforge-training-report.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return app_weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="YOLO dataset YAML")
    parser.add_argument("--architecture", default="yolov8n.yaml", help="YOLOv8 architecture YAML (random initialization)")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default=None, help="Leave empty for automatic selection, or use cpu / 0")
    parser.add_argument("--workers", type=int, default=0, help="0 is safest on Windows")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-name", default="pcbforge-from-scratch")
    return parser.parse_args()


if __name__ == "__main__":
    options = parse_args()
    try:
        weights_path = train(options)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"Training stopped: {error}") from error
    print(f"Training complete. PCB Forge will now use: {weights_path}")
