# Train PCB Forge's own PCB detector

PCB Forge does not have trained weights yet. This workflow creates its own six-class YOLOv8 model from **random initialization**: it loads the `yolov8n.yaml` architecture, explicitly disables pretrained weights, trains only on the labeled images in your dataset, validates the result, and copies the resulting `best.pt` to `quality-inspection/models/best.pt`. It does not use another project's trained `.pt` file.

## 1. Get labeled images (no camera photos required to start)

For a reproducible starter run, use the public [DeepPCB dataset](https://github.com/tangsanli5201/DeepPCB). Its source README restricts use to research purposes. From the project root, download it and convert its annotations:

```powershell
git clone --depth 1 https://github.com/tangsanli5201/DeepPCB.git .\quality-inspection\data\external\DeepPCB
Set-Location .\quality-inspection
.\.venv\Scripts\python.exe .\tools\convert_deeppcb.py --source .\data\external\DeepPCB
```

The converter creates `data/pcb-defects` in YOLO format with group-separated train/validation sets and the dataset's held-out test set. It maps DeepPCB's `pin-hole` label to PCB Forge's `missing_hole`; check `data/pcb-defects/SOURCE_ATTRIBUTION.txt` before presenting results. These benchmark images are not a substitute for testing on your own boards.

For your own model to reflect your hardware, collect varied photos and label them too. Split by physical board/prototype so near-identical photos cannot leak across splits. Use the six class names and exact class-ID order in [`data/pcb-defects/dataset.yaml`](../data/pcb-defects/dataset.yaml).

Add varied photos of real boards, both defect-free and defective. Label every visible target defect with a bounding box and export in YOLO detection format. Create separate train, validation, and test splits by physical board/prototype so near-identical photos cannot leak across splits. Use the six class names and exact class-ID order in [`data/pcb-defects/dataset.yaml`](../data/pcb-defects/dataset.yaml).

The existing `real-data/CAD.png`, `defect-1.png`, and `defect-2.png` have no paired box labels. They cannot be used for supervised object detection until you annotate them. Do not invent labels or report them as model accuracy evidence.

Dataset folders and annotation format are described in [`data/pcb-defects/README.md`](../data/pcb-defects/README.md). Each image needs a matching `.txt` file; use an empty file for a verified defect-free image.

## 2. Install the training package (once)

From the project root:

```powershell
.\quality-inspection\.venv\Scripts\python.exe -m pip install -r .\quality-inspection\requirements-yolo.txt
```

## 3. Train and validate

```powershell
Set-Location .\quality-inspection
.\.venv\Scripts\python.exe .\tools\train_pcb_detector.py --epochs 100 --image-size 640 --batch 8
```

The default architecture is `yolov8n.yaml`, initialized from scratch. Training automatically uses an available supported GPU; otherwise it uses the CPU, which may take a long time. To choose explicitly, add `--device 0` for CUDA GPU 0 or `--device cpu`.

The script checks image/label pairs, class IDs, and normalized boxes before training. It writes the run logs, validation plots, and a machine-readable report under `quality-inspection/runs/`; it also writes `quality-inspection/models/training-metadata.json` and installs the selected checkpoint as `quality-inspection/models/best.pt`. Inspect the validation metrics and predictions before presenting accuracy claims. A trained model is not automatically accurate or production-certified.

Restart the inspection API after training. PCB Forge's inspection page then loads this trained checkpoint and shows its detected boxes and confidence scores. Keep the dataset, run artifacts, and weights backed up; they are local and intentionally excluded from the shareable source ZIP.

For a quick smoke run only, use `--epochs 1 --image-size 320 --batch 4`. This confirms the pipeline executes; it is not enough to claim useful model performance. Allow the full run to finish and report measured held-out test metrics, not training-set scores.

## What can honestly be claimed

Before training completes: “PCB Forge includes a reproducible from-scratch training pipeline; we are training on the research-use DeepPCB benchmark and will validate on physical boards.” After training: state the exact dataset size/split, run date, model checkpoint hash, measured held-out test metrics, and limitations from `training-metadata.json` and the run report. Never claim a training run or accuracy that was not recorded.
