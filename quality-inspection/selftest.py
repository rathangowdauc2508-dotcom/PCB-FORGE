"""One-shot check of the running inspection API. Run from quality-inspection:
   .\.venv\Scripts\python.exe selftest.py
Paste the whole output back."""
import base64, json, time
from pathlib import Path
import requests

B = "http://127.0.0.1:8001"

def step(name, fn):
    t = time.time()
    try:
        out = fn()
        print(f"[OK   {time.time()-t:5.1f}s] {name}: {out}")
        return True
    except Exception as e:
        print(f"[FAIL {time.time()-t:5.1f}s] {name}: {str(e)[:400]}")
        return False

def get(path):
    r = requests.get(B + path, timeout=30); r.raise_for_status(); return r.json()

def post(path, body, timeout=120):
    r = requests.post(B + path, json=body, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()

img = base64.b64encode(Path("data/assets/tested_board.png").read_bytes()).decode()

step("health", lambda: {k: v for k, v in get("/health").items() if k != "time_utc"})
step("detector-status", lambda: get("/analysis/detector-status"))
def photo():
    r = post("/analysis/detect-defects", {"image": {"mime_type": "image/png", "base64_data": img}})
    return f"{r['model_name']} | {r['model_weights']} | {len(r['detections'])} boxes | {r['inference_ms']} ms"
step("single photo inspection", photo)
def full():
    spec = Path("data/specs/deeppcb_demo_spec_v1.md").read_text(encoding="utf-8")
    r = post("/orchestrate", {"input": {
        "error_log": "I2C bus errors, SDA stuck low after power-up.",
        "spec_excerpt": spec[:3000],
        "design_image": {"mime_type": "image/png", "base64_data": base64.b64encode(Path("data/assets/template_board.png").read_bytes()).decode()},
        "tested_image": {"mime_type": "image/png", "base64_data": img}}}, timeout=240)
    return "pipeline finished"
step("5-agent pipeline", full)
