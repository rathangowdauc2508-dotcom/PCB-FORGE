# PCB Forge's training dataset

This is where **your own labeled PCB images** go. The folders are intentionally empty; the sample photos elsewhere in PCB Forge are not a labeled training set.

Create these folders and fill them with images plus YOLO detection labels:

```text
pcb-defects/
├── dataset.yaml
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

For every `images/<split>/board_01.jpg`, add `labels/<split>/board_01.txt`. Each labeled object is one line:

```text
class_id center_x center_y width height
```

Coordinates are normalized from 0 to 1. Empty label files mean the image was inspected and has no target defects. Do not omit normal/defect-free boards; they help the detector learn what not to flag. Use the class IDs and order in `dataset.yaml` exactly:

| ID | Class |
|---:|---|
| 0 | missing_hole |
| 1 | mouse_bite |
| 2 | open_circuit |
| 3 | short |
| 4 | spur |
| 5 | spurious_copper |

Annotate boxes around the visible defect, not around the whole PCB. Keep all photos of the same physical board/prototype in only one split to avoid leakage between training, validation, and test. Include different boards, lighting, camera angles, backgrounds, and defect-free examples. Check labels before training; inaccurate labels teach inaccurate detections.

The current `quality-inspection/real-data` images have no paired box annotations, so the training script correctly refuses to treat them as labeled examples.
