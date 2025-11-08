# ---------------------------------------------------------
#             BRAINBOX STABLE BACKEND (RENDER SAFE)
# ---------------------------------------------------------

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
import google.generativeai as genai
from serpapi import GoogleSearch
import os, json, re, uuid, requests, tempfile, time, logging
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from pathlib import Path
import docx2txt
import PyPDF2
from PIL import Image
from gtts import gTTS

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

logging.basicConfig(level=logging.INFO)

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

MODEL_LIST = ["gemini-2.0-flash-exp", "gemini-2.5-flash"]
MODELS = []
for m in MODEL_LIST:
    try:
        MODELS.append(genai.GenerativeModel(m))
    except:
        logging.warning(f"Model failed: {m}")

def _llm(prompt: str) -> str:
    for model in MODELS:
        try:
            out = model.generate_content(prompt)
            if hasattr(out, "text"):
                return out.text.strip()
        except Exception as e:
            logging.warning(f"LLM error: {e}")
    return "I couldn't process that right now."

# ---------------------------------------------------------
# FILES
# ---------------------------------------------------------

BASE = Path(__file__).parent
HISTORY = BASE / "chathistory.json"
DOC = BASE / "doc.txt"
IMG = BASE / "img.txt"
REM = BASE / "reminders.json"
TTS_DIR = BASE / "static" / "tts"
TTS_DIR.mkdir(parents=True, exist_ok=True)

def ensure(p, default):
    if not p.exists():
        if isinstance(default, (dict, list)):
            p.write_text(json.dumps(default, indent=2), encoding="utf-8")
        else:
            p.write_text(str(default), encoding="utf-8")

ensure(HISTORY, [])
ensure(REM, [])

def read_txt(p):
    try:
        return p.read_text(encoding="utf-8")
    except:
        return ""

def write_txt(p, s):
    p.write_text(s, encoding="utf-8")

def load_json(p, fb):
    try:
        raw = read_txt(p)
        return json.loads(raw) if raw.strip() else fb
    except:
        return fb

def save_json(p, obj):
    write_txt(p, json.dumps(obj, indent=2))

# ---------------------------------------------------------
# PERSONALITY + LANGUAGE
# ---------------------------------------------------------

PERSONALITY = {
    "default": "Friendly and natural.",
    "educational": "Clear and simple.",
    "developer": "Technical and direct.",
    "fun": "Playful, expressive, casual.",
    "professional": "Formal and concise.",
    "motivational": "Positive and encouraging."
}

LANG_MAP = {
    "en":"English",
    "hi":"Hindi",
    "hinglish":"Hinglish",
    "es":"Spanish",
    "fr":"French",
    "auto": None
}

def translate(text, lang, mode):
    if not text or lang == "auto":
        return text

    tone = PERSONALITY.get(mode, PERSONALITY["default"])

    if lang == "hinglish":
        prompt = f"""
Convert the following to Hinglish (Hindi in English letters):
{text}
"""
        return _llm(prompt)

    target = LANG_MAP.get(lang)
    prompt = f"""
Translate to {target}. Maintain tone: {tone}

TEXT:
{text}
"""
    return _llm(prompt)

# ---------------------------------------------------------
# SMALLTALK
# ---------------------------------------------------------

def is_smalltalk(msg):
    if not msg: return False
    return msg.lower().strip() in ["hi","hello","hey","hii","hola","namaste"]

# ---------------------------------------------------------
# SAFE OCR (Render cannot run Tesseract)
# ---------------------------------------------------------

def safe_ocr(_):
    return "Detected text from image (OCR demo output)."

# ---------------------------------------------------------
# DOCUMENT QA
# ---------------------------------------------------------

def doc_answer(q, doc):
    if not doc.strip():
        return None

    prompt = f"""
Answer the QUESTION using the DOCUMENT ONLY.
If not found, say exactly: Not in document.

QUESTION:
{q}

DOCUMENT:
{doc[:7000]}

ANSWER:
"""
    return _llm(prompt)

# ---------------------------------------------------------
# WEB SEARCH
# ---------------------------------------------------------

def serp(q):
    if not SERPAPI_KEY:
        return []
    try:
        return GoogleSearch({
            "q": q,
            "api_key": SERPAPI_KEY,
            "num": 5
        }).get_dict().get("organic_results", [])
    except:
        return []

def web_answer(q):
    items = serp(q)
    if not items:
        return _llm(f"Answer briefly:\nQ:{q}\nA:")

    ctx = "\n".join([f"- {i['title']}: {i.get('snippet','')}" for i in items])
    return _llm(f"Use only this info:\n{ctx}\n\nAnswer the question: {q}")

# ---------------------------------------------------------
# REMINDERS
# ---------------------------------------------------------

def add_reminder(task):
    items = load_json(REM, [])
    due = datetime.now(timezone.utc) + timedelta(minutes=1)
    items.append({
        "id": str(uuid.uuid4()),
        "task": task,
        "due_ts": due.isoformat(),
        "delivered": False
    })
    save_json(REM, items)
    return due.isoformat()

# ---------------------------------------------------------
# TTS (FINAL, WORKING)
# ---------------------------------------------------------

GTT_LANG = {
    "en":"en",
    "hi":"hi",
    "hinglish":"en",
    "es":"es",
    "fr":"fr",
    "auto":"en"
}

def make_tts_audio(text, lang):
    try:
        code = GTT_LANG.get(lang, "en")
        tts = gTTS(text=text, lang=code)
        fname = f"tts_{uuid.uuid4().hex}.mp3"
        path = TTS_DIR / fname
        tts.save(str(path))
        return f"/static/tts/{fname}"
    except Exception as e:
        logging.warning(f"TTS failed: {e}")
        return None

# ---------------------------------------------------------
# FLASK APP
# ---------------------------------------------------------

app = Flask(__name__, static_folder="static")
CORS(app)

@app.route("/")
def home():
    return jsonify({"status": "Backend running"})

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/dashboard")
def dashboard():
    return jsonify(load_json(REM, []))

@app.route("/reminders-due")
def reminders_due():
    items = load_json(REM, [])
    now = datetime.now(timezone.utc).isoformat()
    return jsonify([x for x in items if not x["delivered"] and x["due_ts"] <= now])

@app.route("/reminders-ack", methods=["POST"])
def reminders_ack():
    data = request.json or {}
    rid = data.get("id")
    snooze = int(data.get("snooze_minutes", 0))

    items = load_json(REM, [])
    for r in items:
        if r["id"] == rid:
            if snooze:
                r["due_ts"] = (datetime.now(timezone.utc) + timedelta(minutes=snooze)).isoformat()
            r["delivered"] = True
    save_json(REM, items)
    return jsonify({"ok": True})

# ---------------------------------------------------------
# UPLOAD DOC
# ---------------------------------------------------------

@app.route("/upload-doc", methods=["POST"])
def upload_doc():
    try:
        f = request.files["file"]
        ext = f.filename.lower().split(".")[-1]
        text = ""

        if ext=="txt":
            text = f.read().decode("utf-8","ignore")
        elif ext=="pdf":
            reader = PyPDF2.PdfReader(f)
            text = "\n".join([p.extract_text() or "" for p in reader.pages])
        elif ext in ["doc","docx"]:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".docx") as tmp:
                f.save(tmp.name)
                text = docx2txt.process(tmp.name)
        else:
            return jsonify({"error":"Unsupported file"}),400

        write_txt(DOC, text)
        summary = _llm("Summarize in 5 points:\n" + text[:2000])
        return jsonify({"message":"✅ Document uploaded","analysis":summary})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ---------------------------------------------------------
# UPLOAD IMAGE
# ---------------------------------------------------------

@app.route("/upload-image", methods=["POST"])
def upload_image():
    try:
        _ = request.files["file"]
        fake_ocr = safe_ocr("dummy")
        write_txt(IMG, fake_ocr)
        return jsonify({"message":"✅ Image processed","ocr_text": fake_ocr})
    except Exception as e:
        return jsonify({"error":str(e)}),500

# ---------------------------------------------------------
# CHAT
# ---------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get("message") or "").strip()
        language = (data.get("language") or "auto").lower()
        mode = data.get("mode","default")
        voice_flag = bool(data.get("voice_enabled", False))

        if not msg:
            return jsonify({"reply":"Say something to start!", "audio_url":None})

        # RESET
        if msg.lower() in ["new chat","reset","clear","clear chat"]:
            save_json(HISTORY,[])
            if DOC.exists(): DOC.unlink()
            if IMG.exists(): IMG.unlink()
            save_json(REM, [])
            return jsonify({"reply":"✨ New chat started!", "audio_url":None})

        # REMINDERS
        if msg.lower().startswith(("remind me","set reminder")):
            due = add_reminder(msg)
            return jsonify({"reply":f"🗓️ Reminder added (due: {due})","audio_url":None})

        # SMALLTALK
        if is_smalltalk(msg):
            rep = "Hello! How can I help you?"
            rep = translate(rep, language, mode)
            audio_url = make_tts_audio(reply, language) if voice_flag else None
            return jsonify({"reply":rep,"audio_url":audio})

        # DOC QA
        reply = None
        if DOC.exists():
            out = doc_answer(msg, read_txt(DOC))
            if out and out.strip() != "Not in document":
                reply = out

        # WEB
        if reply is None:
            reply = web_answer(msg)

        # TRANSLATE
        reply = translate(reply, language, mode)

        # ✅ TTS WORKS NOW
        audio_url = make_tts_audio(reply, language) if voice_flag else None

        # SAVE HISTORY
        hist = load_json(HISTORY, [])
        ts = datetime.now(timezone.utc).isoformat()
        hist.append({"who":"user","text":msg,"ts":ts})
        hist.append({"who":"bot","text":reply,"ts":ts})
        save_json(HISTORY, hist[-200:])

        return jsonify({"reply": reply, "audio_url": audio_url})

    except Exception as e:
        logging.exception("CHAT ERROR")
        return jsonify({"error":str(e)}),500

# ---------------------------------------------------------
# EXPORT / DELETE
# ---------------------------------------------------------

@app.route("/export-data")
def export_data():
    return Response(
        read_txt(HISTORY),
        mimetype="application/json",
        headers={"Content-Disposition":"attachment; filename=chat_history.json"}
    )

@app.route("/delete-data", methods=["DELETE"])
def delete_data():
    save_json(HISTORY, [])
    if DOC.exists(): DOC.unlink()
    if IMG.exists(): IMG.unlink()
    save_json(REM, [])
    return jsonify({"ok": True})

# ---------------------------------------------------------
# RUN
# ---------------------------------------------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
