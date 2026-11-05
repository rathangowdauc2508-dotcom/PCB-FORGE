# PCB Forge

PCB Forge is a local PCB engineering workspace with two parts:

- **PCB Manufacturing**: KiCad board parsing, geometry-based DFM checks, BOM and supplier planning, project history, and export packages.
- **PCB Inspection**: upload a board image and run YOLOv8 defect localization when the compatible trained model is installed.

Manufacturing estimates are planning estimates. Saving a request does not charge a payment method or submit an order to a factory. A clean inspection result is not a quality certification.

## Run on Windows

### 1. Install prerequisites

Install Python 3.11 and Node.js 22.12 or newer. Extract this ZIP, open the extracted `pcb-ecosystem` folder in VS Code, and open a PowerShell terminal at that folder.

### 2. Set up dependencies once

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\setup.ps1"
```

The setup script creates local Python environments, installs the backend packages, installs both frontend packages, and creates local `.env` files from examples if needed. Add your own Gemini API key to `quality-inspection\.env`; never share that file.

### 3. Start the app

Open two PowerShell terminals in the project root.

Terminal 1:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start-backend.ps1"
```

Terminal 2:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start-frontend.ps1"
```

Open **http://localhost:3000** for manufacturing or **http://localhost:5173** for inspection. Keep both terminals open while using PCB Forge.

## PCB defect model requirement

PCB Forge trains its own YOLOv8 model from random initialization on your labeled images; it does not use the linked reference project's trained weights. The included sample photos are not labeled and cannot train a detector as-is.

To prepare and train your model, follow [the training guide](quality-inspection/docs/TRAIN_PCB_MODEL.md). Install the YOLO training package:

```powershell
.\quality-inspection\.venv\Scripts\python.exe -m pip install -r .\quality-inspection\requirements-yolo.txt
```

After training, the script saves `quality-inspection\models\best.pt`. Restart the inspection backend. Until then, the inspection page reports that the detector is not ready rather than fabricating detections.

Gemini-powered features also require a valid key in `quality-inspection\.env`. The deterministic manufacturing parser and DFM checks do not depend on Gemini.
