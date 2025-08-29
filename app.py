
import os
import hmac
import hashlib
import time
from flask import Flask, request, abort
import requests

GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_me")
APP_SECRET = os.getenv("APP_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = Flask(__name__)

def verify_signature(req):
    if not APP_SECRET:
        return True
    signature = req.headers.get("X-Hub-Signature-256", "")
    if not signature.startswith("sha256="):
        return False
    digest = hmac.new(APP_SECRET.encode("utf-8"), msg=req.data, digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature.split("=", 1)[1], digest)

def send_ig_text(recipient_id: str, text: str):
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}
    resp = requests.post(url, params=params, json=payload, timeout=10)
    return resp.ok

def detect_lang(text: str) -> str:
    cyr = any("а" <= ch <= "я" or "А" <= ch <= "Я" for ch in text)
    tur = any(ch in "ığüşöçĞÜŞİÖÇ" for ch in text)
    if cyr and not tur:
        return "ru"
    if tur and not cyr:
        return "tr"
    return "both"

def build_system_prompt():
    return f"""
Ты — вежливый и внимательный ассистент салона массажа «Yelena Heal Aura Studio». 
Отвечай дружелюбно и по делу, без лишней воды. Используй максимум 2 уместных эмодзи.

📌 ОБЩИЕ ПРАВИЛА:
1) Если вопрос про запись, цены, услуги или отзывы — всегда указывай ссылку:
   «Смотрите актуальные цены, свободные окошки и отзывы по ссылке 👉 https://dikidi.ru/946726?p=2.pi-po-ssm&o=7»
2) Если клиент спрашивает про адрес — давай полный адрес + ссылку на Google Maps:
   «Bağlarbaşı mahallesi Atatürk caddesi Omay pasajı No:56 A blok Daire 50 Maltepe/İstanbul, Turkey
   👉 https://maps.app.goo.gl/wT6cVGeWgWH2XHeF7»
3) График работы:
   «Мы открыты с понедельника по субботу с 10:00 до 20:00».
4) Язык:
   - Если клиент пишет на турецком — отвечай на турецком.
   - Если на русском — отвечай на русском.
   - Если язык непонятен — ответь сначала по-турецки, ниже по-русски.
5) Если клиент благодарит — отвечай:
   «Спасибо вам 🤍 Ждём снова в Yelena Heal Aura Studio».
6) Если вопрос не связан с салоном, услугами, ценами, адресом, записью или благодарностью — НЕ отвечай вообще.
7) Никогда не придумывай цены и услуги — отправляй только на ссылку с онлайн-записью.
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
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=16)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return ""

@app.route("/health", methods=["GET"])
def health():
    return {"ok": True, "time": int(time.time())}

@app.route("/webhook", methods=["GET"])
def webhook_verify():
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
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            sender = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")
            if not sender or not text:
                continue
            lang_hint = detect_lang(text)
            reply = call_openai(text, lang_hint)
            if reply.strip():
                send_ig_text(sender, reply)
    return "OK", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
