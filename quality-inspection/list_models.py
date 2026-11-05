"""Shows exactly which models your key can call, and which accept an image.
Run from quality-inspection:  .\.venv\Scripts\python.exe list_models.py
"""
import re, sys
from pathlib import Path
from google import genai
from google.genai import types
from app.config import get_settings
from app.image_utils import normalize_for_gemma

keys = get_settings().gemini_api_keys
if not keys:
    sys.exit("No key in .env")
client = genai.Client(api_key=keys[0])
names = []
for m in client.models.list():
    n = (m.name or "").replace("models/", "")
    acts = list(getattr(m, "supported_actions", []) or [])
    if "generateContent" in acts and re.match(r"(gemini|gemma)", n):
        names.append(n)
print("Models this key can list:")
for n in sorted(names):
    print("  ", n)
jpg, mime = normalize_for_gemma(Path("data/assets/tested_board.png").read_bytes(), "image/png")
cands = [n for n in names if re.fullmatch(r"gemini-\d+(\.\d+)?-flash(-lite)?", n) or n == "gemini-flash-latest"]
print("\nImage test:")
for n in sorted(cands, reverse=True):
    try:
        r = client.models.generate_content(model=n, contents=["Say OK", types.Part.from_bytes(data=jpg, mime_type=mime)], config={"max_output_tokens": 64})
        print("  OK  ", n)
    except Exception as e:
        print("  FAIL", n, "->", str(e)[:110])
