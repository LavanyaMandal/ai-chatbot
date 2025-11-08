# ---------------------------------------------------------
#                   BRAINBOX FINAL BACKEND
#      All features + Stable gTTS + Reminders fixed (A)
# ---------------------------------------------------------

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import google.generativeai as genai
from serpapi import GoogleSearch
import os, json, re, uuid, requests, tempfile, logging
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import docx2txt
import PyPDF2
from PIL import Image
import pytesseract
from gtts import gTTS

# ---------------- CONFIG ----------------
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

MODEL_LIST = ["gemini-2.0-flash-exp", "gemini-2.5-flash"]
_MODELS = []
for m in MODEL_LIST:
    try:
        _MODELS.append(genai.GenerativeModel(m))
    except Exception as e:
        logging.warning(f"Model init failed: {m}: {e}")

def _llm(prompt: str) -> str:
    for model in _MODELS:
        try:
            out = model.generate_content(prompt)
            t = getattr(out, "text", None)
            if t:
                return t.strip()
        except Exception as e:
            logging.warning(f"LLM call failed: {e}")
    return "I couldn't process that right now."

# ---------------- FILES ----------------
BASE = Path(__file__).parent
HISTORY = BASE / "chathistory.json"
DOC = BASE / "doc.txt"
IMG = BASE / "img.txt"
REM = BASE / "reminders.json"
TTS_DIR = BASE / "static" / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

def _ensure(p: Path, default):
    if not p.exists():
        if isinstance(default, (dict, list)):
            p.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            p.write_text(str(default), encoding="utf-8")

_ensure(HISTORY, [])
_ensure(REM, [])

def read_txt(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""

def write_txt(p: Path, s: str):
    p.write_text(s, encoding="utf-8")

def load_json(p: Path, fb):
    try:
        raw = read_txt(p)
        return json.loads(raw) if raw.strip() else fb
    except Exception:
        return fb

def save_json(p: Path, obj):
    write_txt(p, json.dumps(obj, indent=2, ensure_ascii=False))

# ---------------- PERSONALITY / LANG (UNCHANGED) ----------------
PERSONALITY = {
    "default": "Friendly and natural.",
    "educational": "Clear, simple teacher tone with examples.",
    "developer": "Technical and precise. Short and direct.",
    "fun": "High-energy, playful, expressive. Do NOT mix languages unless Hinglish.",
    "professional": "Concise and formal.",
    "motivational": "Uplifting and encouraging."
}

LANG_MAP = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
    "es": "Spanish",
    "fr": "French",
    "auto": None
}

def translate(reply, lang, mode):
    if not reply or lang == "auto":
        return reply
    target = LANG_MAP.get(lang)
    if not target:
        return reply
    tone = PERSONALITY.get(mode, PERSONALITY["default"])
    if lang == "hinglish":
        prompt = f"""Convert text to Hinglish (Hindi in English letters). No Devanagari.

TEXT:
{reply}
"""
        return _llm(prompt) or reply
    prompt = f"""Translate to {target}. Keep tone similar to: {tone}. Do NOT add extra info.

TEXT:
{reply}
"""
    return _llm(prompt) or reply

def is_smalltalk(t):
    return (t or "").lower().strip() in ["hi","hello","hey","hola","namaste","bonjour"]

# ---------------- OCR & DOC QA (UNCHANGED) ----------------
def is_ocr_query(text):
    if not text: return False
    t = text.lower()
    keys = [
        "what is written in the image",
        "image mein kya","image me kya","text in image","read the image",
        "ocr","picture me kya","photo me kya","what is the text written"
    ]
    return any(k in t for k in keys)

def doc_answer(q, txt):
    if not txt.strip():
        return None
    prompt = f"""From the DOCUMENT, answer the QUESTION. If not found say: Not in document

QUESTION: {q}

DOCUMENT:
{txt[:7000]}

Answer:
"""
    return _llm(prompt)

# ---------------- WEB SEARCH (UNCHANGED) ----------------
def serp(q):
    if not SERPAPI_KEY:
        return []
    try:
        r = GoogleSearch({"q": q, "api_key": SERPAPI_KEY, "num": 6}).get_dict()
        return r.get("organic_results", [])
    except Exception:
        return []

def web_answer(q):
    items = serp(q)
    if not items:
        return _llm(f"Answer briefly:\nQ: {q}\nA:")
    ctx = "\n".join([f"- {i.get('title')} {i.get('snippet')}" for i in items[:5]])
    prompt = f"""Use ONLY this web context:

{ctx}

Answer the question briefly:
{q}

Answer:
"""
    return _llm(prompt)

# ---------------- REMINDERS (UPDATED) ----------------
def add_rem(text):
    items = load_json(REM, [])
    due = datetime.now(timezone.utc) + timedelta(minutes=1)
    items.append({
        "id": str(uuid.uuid4()),
        "task": text,
        "due_ts": due.isoformat(),
        "delivered": False
    })
    save_json(REM, items)
    return due.isoformat()

# ---------------- TTS (UNCHANGED) ----------------
GTT_LANG = {"en":"en","es":"es","fr":"fr","hi":"hi","hinglish":"en","auto":"en"}

def make_tts(text, lang):
    try:
        # speak only letters/numbers/basic punctuation
        clean = re.sub(r"[^0-9A-Za-zÀ-ž\s\.,!\?\-']", " ", text or "")
        clean = re.sub(r"\s+", " ", clean).strip()
        code = GTT_LANG.get(lang, "en")
        tts = gTTS(text=clean or " ", lang=code)
        fname = f"tts_{uuid.uuid4().hex}.mp3"
        path = TTS_DIR / fname
        tts.save(str(path))
        return f"/static/tts/{fname}"
    except Exception as e:
        logging.warning(f"TTS ERROR: {e}")
        return None

# ---------------------------------------------------------
# APP INIT
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/")
def home():
    return {"status": "Backend running"}

# ---------------- REMINDER ROUTES (NEW) ----------------
@app.route("/dashboard")
def dashboard():
    return jsonify(load_json(REM, []))

@app.route("/reminders-due")
def reminders_due():
    items = load_json(REM, [])
    now_iso = datetime.now(timezone.utc).isoformat()
    due = [x for x in items if not x.get("delivered") and x.get("due_ts","") <= now_iso]
    return jsonify(due)

@app.route("/reminders-ack", methods=["POST"])
def reminders_ack():
    data = request.get_json(silent=True) or {}
    rid = data.get("id")
    snooze = int(data.get("snooze_minutes", 0) or 0)
    items = load_json(REM, [])
    for x in items:
        if x.get("id") == rid:
            if snooze > 0:
                new_due = datetime.now(timezone.utc) + timedelta(minutes=snooze)
                x["due_ts"] = new_due.isoformat()
                x["delivered"] = False
            else:
                x["delivered"] = True
            break
    save_json(REM, items)
    return jsonify({"ok": True})

# ---------------------------------------------------------
# CHAT (UNCHANGED except reminder call)
# ---------------------------------------------------------
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    msg = (data.get("message") or "").strip()
    lang = (data.get("language") or "auto").lower()
    mode = data.get("mode","default")
    voice = bool(data.get("voice_enabled", False))

    if msg.lower() in ["clear","reset","new chat"]:
        save_json(HISTORY, [])
        if DOC.exists(): DOC.unlink()
        if IMG.exists(): IMG.unlink()
        save_json(REM, [])
        return jsonify({"reply":"✨ New chat started!", "audio_url":None})

    if msg.lower().startswith("remind"):
        due = add_rem(msg)
        return jsonify({"reply":f"✅ Reminder added (due: {due})", "audio_url":None})

    if is_smalltalk(msg):
        reply = translate("Hello! How can I help you?", lang, mode)
        audio = make_tts(reply, lang) if voice else None
        return jsonify({"reply":reply, "audio_url":audio})

    if is_ocr_query(msg) and IMG.exists():
        ocr = read_txt(IMG).strip()
        reply = translate(ocr or "I could not find readable text in the image.", lang, mode)
        audio = make_tts(reply, lang) if voice else None
        return jsonify({"reply":reply, "audio_url":audio})

    reply = None
    if DOC.exists():
        ans = doc_answer(msg, read_txt(DOC))
        if ans and ans != "Not in document":
            reply = ans
    if reply is None:
        reply = web_answer(msg)

    reply = translate(reply, lang, mode)
    audio = make_tts(reply, lang) if voice else None

    hist = load_json(HISTORY, [])
    hist.append({"who":"user","text":msg})
    hist.append({"who":"bot","text":reply})
    save_json(HISTORY, hist[-200:])

    return jsonify({"reply":reply, "audio_url":audio})

# ---------------- DOC / IMAGE / EXPORT / DELETE (UNCHANGED) ----------------
@app.route("/upload-doc", methods=["POST"])
def upload_doc():
    try:
        f = request.files["file"]
        ext = f.filename.lower().split(".")[-1]
        text=""
        if ext=="txt":
            text = f.read().decode("utf-8","ignore")
        elif ext=="pdf":
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        elif ext in ["doc","docx"]:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
                f.save(tmp.name)
                text = docx2txt.process(tmp.name)
        write_txt(DOC, text)
        summary = _llm("Summarize in 5 points:\n"+text[:2000])
        return jsonify({"message":"✅ Document uploaded", "analysis":summary})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/upload-image", methods=["POST"])
def upload_image():
    try:
        img = Image.open(request.files["file"].stream).convert("RGB")
        ocr = pytesseract.image_to_string(img)
        write_txt(IMG, ocr)
        return jsonify({"message":"✅ Image processed","ocr_text":ocr})
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/export-data")
def export_data():
    return Response(read_txt(HISTORY) or "[]", mimetype="application/json")

@app.route("/delete-data", methods=["DELETE"])
def delete_data():
    save_json(HISTORY, [])
    if DOC.exists(): DOC.unlink()
    if IMG.exists(): IMG.unlink()
    save_json(REM, [])
    return jsonify({"ok":True})

# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
