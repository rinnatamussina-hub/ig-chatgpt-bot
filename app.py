import os, json, requests
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# === ENV ===
VERIFY_TOKEN      = os.getenv("VERIFY_TOKEN", "rinnata_verify")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY", "")

BOOKING_LINK = "https://dikidi.ru/946726?p=2.pi-po-ssm&o=7"
MAPS_LINK    = "https://maps.app.goo.gl/wT6cVGeWgWH2XHeF7"
ADDRESS      = "Bağlarbaşı mahallesi Atatürk caddesi Omay pasajı No:56 A blok Daire 50 Maltepe/İstanbul, Turkey"
HOURS        = "Понедельник–суббота 10:00–20:00"

client = OpenAI(api_key=OPENAI_API_KEY)

def build_system_prompt():
    return f"""
Ты — вежливый и внимательный ассистент салона массажа «Yelena Heal Aura Studio».
Отвечай дружелюбно и по делу, без лишней воды. Используй максимум 2 уместных эмодзи.

📌 ОБЩИЕ ПРАВИЛА:
1) Если вопрос про запись, цены, услуги или отзывы — всегда указывай ссылку:
   «Смотрите актуальные цены, свободные окошки и отзывы по ссылке 👉 {BOOKING_LINK}»
2) Если клиент спрашивает про адрес — давай полный адрес + ссылку на Google Maps:
   «{ADDRESS}
   👉 {MAPS_LINK}»
3) График работы:
   «Мы открыты с понедельника по субботу с 10:00 до 20:00».
4) Язык:
   - Если клиент пишет на турецком — отвечай на турецком.
   - Если на русском — отвечай на русском.
   - Если язык непонятен — ответь сначала по-турецки, ниже по-русски.
5) Если клиент благодарит — отвечай:
   «Спасибо вам 🤍 Ждём снова в Yelena Heal Aura Studio».
6) Если вопрос не связан с салоном, услугами, ценами, адресом, записью или благодарностью — НЕ отвечай вообще.
   В таком случае верни строго строку: __NO_REPLY__
7) Никогда не придумывай цены и услуги — отправляй только на ссылку с онлайн-записью.
"""

def ask_gpt(user_text: str) -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"system","content": build_system_prompt()},
                {"role":"user","content": user_text.strip()}
            ],
            temperature=0.2,
            max_tokens=350
        )
        answer = resp.choices[0].message.content.strip()
        return answer
    except Exception as e:
        print("OpenAI error:", e)
        return "Şu anda teknik çalışma yapıyoruz, lütfen biraz sonra yazın. / Сейчас ведутся техработы, напишите, пожалуйста, немного позже. 🙏"

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode      = request.args.get("hub.mode")
        token     = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        return "Forbidden", 403

    data = request.get_json(silent=True) or {}
    print("INCOMING:", json.dumps(data, ensure_ascii=False))

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = (messaging.get("sender") or {}).get("id")
            msg_obj   = messaging.get("message") or {}
            text      = msg_obj.get("text")

            if sender_id and text:
                reply = ask_gpt(text)
                if reply.strip() == "__NO_REPLY__":
                    continue
                send_text(sender_id, reply)

    return "EVENT_RECEIVED", 200

def send_text(psid: str, text: str):
    if not PAGE_ACCESS_TOKEN:
        print("No PAGE_ACCESS_TOKEN set")
        return

    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": psid},
        "messaging_type": "RESPONSE",
        "message": {"text": text}
    }
    try:
        r = requests.post(url, params=params, json=payload, timeout=15)
        print("SEND STATUS:", r.status_code, r.text)
    except Exception as e:
        print("Send error:", e)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
