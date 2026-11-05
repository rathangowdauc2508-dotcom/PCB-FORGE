# PCB Forge evaluation guide

PCB Forge includes a repeatable demo for presenting the workflow and a separate DeepPCB benchmark runner for measuring defect localization. Do not treat a successful demo run as an accuracy score.

## Run the benchmark

1. Configure a working `GEMINI_API_KEY` in `quality-inspection/.env`.
2. Obtain the DeepPCB dataset separately and place it at `quality-inspection/data/external/DeepPCB` (or pass its directory with `--deeppcb-root`). Follow the dataset's license and terms.
3. From the `quality-inspection` directory, activate its virtual environment and run:

   ```powershell
   python tools/benchmark_deeppcb_orchestration.py --max-cases 6 --per-class 1
   ```

The runner writes JSON and Markdown summaries under `quality-inspection/data/benchmarks`. Reports include localization and class-aware precision, recall, F1 at IoU 0.33, trace completion, model, and latency. Keep the report with the model name, date, case count, and exact command when sharing results.

## Evaluate new physical boards

For each board, save the design image, tested-board image, observed test result, relevant specification, and a manually reviewed defect label and bounding box. Keep those labels separate from Gemma's output. Compare model findings with the human-reviewed labels and report false positives and missed defects as well as correct findings. Include boards with no known defects so the system's tendency to over-report can be measured.

The built-in example is a product demo case, not a representative test set. Report its results separately from benchmark or real-hardware evaluation.
