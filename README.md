
# Instagram ChatGPT Auto-Reply Bot (Free-tier friendly)

This is a minimal Flask app that connects Meta Webhooks (Instagram Messaging) to OpenAI Chat Completions to auto-reply in Instagram Direct.

## 1) Prerequisites
- Instagram **Professional** account linked to a **Facebook Page** (Meta requirement).
- Meta Developer App (add **Instagram Graph API** + **Webhooks** products).
- Page Access Token for the Page linked to your IG account (for dev mode, role users can test).
- Public HTTPS URL for the webhook (Railway, Render, Replit or ngrok).

## 2) Environment variables
Set these in your hosting dashboard:
- `GRAPH_API_VERSION` = v21.0
- `PAGE_ACCESS_TOKEN` = your Page token
- `VERIFY_TOKEN` = any secret string you will also enter in Meta Webhooks UI
- `APP_SECRET` = your Meta App Secret (optional but recommended for signature validation)
- `OPENAI_API_KEY` = your OpenAI key
- `OPENAI_MODEL` = gpt-4o-mini (default) or other
- `SALON_NAME` = Yelena Heal Aura Studio
- `BOOKING_LINK` = https://dikidi.net/946726?p=0.pi-po

## 3) Run locally (for tests)
```bash
pip install -r requirements.txt
export PAGE_ACCESS_TOKEN=... VERIFY_TOKEN=... OPENAI_API_KEY=...
python app.py
```
Expose with ngrok and use the URL as your Webhook callback during verification.

## 4) Deploy
Use any free-tier friendly host (Railway/Render/Replit). Create a web service from this folder and set the env vars. Use the generated HTTPS URL as the Webhook Callback URL in Meta > App > Webhooks (Instagram).

## 5) Meta configuration (high level)
- In **Meta for Developers**: Add product **Instagram Graph API** and **Webhooks** to your app.
- Under **Webhooks**: Choose **Instagram**, click **Subscribe**, set **Callback URL** to `https://<your-host>/webhook`, and **Verify Token** = your `VERIFY_TOKEN`.
- In **App Roles** add your IG Business account as a tester so you can send test DMs.
- Subscribe to **messages** field for Instagram.
- Use **Graph API Explorer** or Page settings to generate a **Page Access Token**.

> Production note: To go live beyond testers, submit for App Review requesting `instagram_manage_messages`, `pages_manage_metadata`, `instagram_basic`.

## 6) How it replies
- Webhook receives each incoming DM, grabs the `sender.id` and text, calls OpenAI with a salon-specific system prompt, and posts the reply back via `POST https://graph.facebook.com/<version>/me/messages?access_token=<PAGE_ACCESS_TOKEN>`.

## 7) Safety / handoff
The prompt instructs the assistant to hand off to a human when unsure and to always include the booking link when relevant.
