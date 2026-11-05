# PCB Forge trained weights

`best.pt` is created by PCB Forge's own training script. It is intentionally absent until you supply correctly labeled PCB images and train the detector. The training command saves the selected checkpoint here automatically. It uses a YOLOv8n architecture initialized from random weights; it does not download or load another project's trained checkpoint.

Classes, labels, dataset layout, and the training command are documented in `data/pcb-defects/README.md` and `docs/TRAIN_PCB_MODEL.md`. For a custom location, set `PCB_DEFECT_MODEL_PATH` in `quality-inspection/.env`.
