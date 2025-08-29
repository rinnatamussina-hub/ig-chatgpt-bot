
import os
import hmac
import hashlib
import json
import time
from flask import Flask, request, jsonify, abort
import requests

# ---------- Config ----------
GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")  # Page token connected to IG Professional account
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_me")
APP_SECRET = os.getenv("APP_SECRET", "")  # Optional: for signature verification
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SALON_NAME = os.getenv("SALON_NAME", "Yelena Heal Aura Studio")
BOOKING_LINK = os.getenv("BOOKING_LINK", "https://dikidi.net/946726?p=0.pi-po")
DEFAULT_LANGS = os.getenv("DEFAULT_LANGS", "detect")  # "detect" or "tr+ru"
TIMEOUT_SECS = float(os.getenv("TIMEOUT_SECS", "16"))

app = Flask(__name__)

# ---------- Helpers ----------
def verify_signature(req):
    """Verify X-Hub-Signature-256 from Meta (optional but recommended)."""
    if not APP_SECRET:
        return True
    signature = req.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False
    digest = hmac.new(APP_SECRET.encode("utf-8"), msg=req.data, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.split("=", 1)[1], digest)

def send_ig_text(recipient_id: str, text: str):
    """Send a text reply to an Instagram user via Messenger Send API (for IG DM)."""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    resp = requests.post(url, params=params, json=payload, timeout=10)
    if not resp.ok:
        app.logger.error("Meta send error %s %s", resp.status_code, resp.text)
    return resp.ok

def detect_lang(text: str) -> str:
    """Very light heuristic: if Cyrillic -> ru, if Turkish chars -> tr, else fallback."""
    cyr = any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in text)
    tur = any(ch in "ığüşöçĞÜŞİÖÇ" for ch in text)
    if cyr and not tur:
        return "ru"
    if tur and not cyr:
        return "tr"
    return "both"

def build_system_prompt():
    return f"""
Ты — вежливый, краткий ассистент салона массажа «{SALON_NAME}».
Правила ответа:
1) Отвечай дружелюбно и по делу, без лишней воды.
2) Если вопрос про запись, ВСЕГДА добавляй ссылку на онлайн-запись: {BOOKING_LINK}
3) Если пользователь пишет на турецком — отвечай на турецком. Если на русском — на русском. Если язык непонятен — ответь сначала по‑турецки, ниже по‑русски.
4) Форматируй короткими абзацами и эмодзи по ситуации (не больше 2).
5) Если вопрос не по теме салона или требует человека, отвечай: «Передаю администратору, он скоро напишет».
6) Никогда не придумывай цены, используй формулировку «güncel fiyatlar ve uygun saatler için linke tıklayın / актуальные цены и свободные окошки по ссылке: {BOOKING_LINK}».
7) Не запрашивай персональные данные, кроме необходимых для записи (имя, телефон, желаемое время).
"""

def call_openai(user_text: str, lang_hint: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_text},
    ]
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 300
    }
    try:
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=TIMEOUT_SECS)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        # Fallback generic bilingual reply
        return f"Merhaba! Sorunuzu aldım. Randevu ve fiyatlar için link: {BOOKING_LINK}\n\nЗдравствуйте! Ваш вопрос получил(а). Записаться и посмотреть цены: {BOOKING_LINK}"

# ---------- Routes ----------
@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "time": int(time.time())}

@app.route("/webhook", methods=["GET"])
def webhook_verify():
    # Verification handshake
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook_receive():
    if not verify_signature(request):
        abort(403)
    payload = request.get_json(force=True, silent=True) or {}
    # Instagram + Messenger share the "entry" -> "messaging" shape
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")
            # Ignore non-text messages
            if not sender or not text:
                continue
            lang_hint = detect_lang(text)
            reply = call_openai(text, lang_hint)
            send_ig_text(sender, reply)
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
