"""Finds exactly why Gemma returns 400 on images. Run from quality-inspection\ :
   .\.venv\Scripts\python.exe diag_image.py
"""
import inspect, sys
from pathlib import Path
from google import genai
from google.genai import types
from app.config import get_settings
from app import gemini_client
from app.image_utils import normalize_for_gemma

print("gemini_client.py loaded from:", gemini_client.__file__)
print("fix applied (normalize_for_gemma wired in):", "normalize_for_gemma" in inspect.getsource(gemini_client))
keys = get_settings().gemini_api_keys
if not keys:
    sys.exit("No key found in .env")
client = genai.Client(api_key=keys[0])
raw = Path("data/assets/tested_board.png").read_bytes()
jpg, jmime = normalize_for_gemma(raw, "image/png")
Q = 'Reply with ONLY this JSON: {"ok": true}'
models = ["gemma-4-31b-it", "gemma-4-26b-a4b-it", "gemini-2.5-flash", "gemini-3-flash-preview"]
variants = {
    "text only": [Q],
    "raw PNG": [Q, types.Part.from_bytes(data=raw, mime_type="image/png")],
    "normalized JPEG": [Q, types.Part.from_bytes(data=jpg, mime_type=jmime)],
}
for m in models:
    for name, contents in variants.items():
        try:
            r = client.models.generate_content(model=m, contents=contents, config={"max_output_tokens": 256})
            print(f"OK    {m:26} {name:16} -> {(r.text or '')[:50]!r}")
        except Exception as e:
            print(f"FAIL  {m:26} {name:16} -> {str(e)[:140]}")
