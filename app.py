from flask import Flask, request
import requests

app = Flask(__name__)

VERIFY_TOKEN = "servet123"
ACCESS_TOKEN = "META_ACCESS_TOKEN"
PHONE_NUMBER_ID = "META_PHONE_NUMBER_ID"

@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge"), 200
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = msg["from"]
        text = msg["text"]["body"].lower()
    except:
        return "ok", 200

    if text == "siparis":
        send_message(from_number, "Sipariş başladı ✅")
    return "ok", 200

def send_message(to, body):
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    requests.post(url, headers=headers, json={
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body}
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
