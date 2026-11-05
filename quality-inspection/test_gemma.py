import sys, json
from google import genai

key = sys.argv[1] if len(sys.argv) > 1 else input("Paste Gemini API key: ").strip()
client = genai.Client(api_key=key)
MODEL = "gemma-4-31b-it"
Q = 'Reply with ONLY this JSON object and nothing else: {"ok": true, "word": "hello"}'

def show(title, cfg):
    print("\n=====", title, "=====")
    try:
        r = client.models.generate_content(model=MODEL, contents=Q, config=cfg)
        c = r.candidates[0] if r.candidates else None
        print("finish_reason:", getattr(c, "finish_reason", None))
        for i, p in enumerate((c.content.parts if c and c.content else []) or []):
            print(f"part {i} thought={getattr(p,'thought',None)} text={getattr(p,'text',None)!r}")
        print("r.text:", repr(getattr(r, "text", None)))
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e)[:500])

show("1 plain", {"max_output_tokens": 4096})
show("2 json mode", {"max_output_tokens": 4096, "response_mime_type": "application/json"})
show("3 json mode + schema", {"max_output_tokens": 4096, "response_mime_type": "application/json",
     "response_schema": {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}}}})
