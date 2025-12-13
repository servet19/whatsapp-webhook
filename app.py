import os
import time
import requests
from flask import Flask, request

app = Flask(__name__)

# Secrets / config (Render -> Environment'dan gelecek)
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "servet123")  # istersen Render'da da ver
ACCESS_TOKEN = os.getenv("EAAbnaT4dTsIBQFcDBoOn4R2ZB1kBu9qihuN1XbKZBS5iUVi5xWqoB5PbgeHmQZBjKVIrH2EI8NYH0e5BTMlQVGV6c3XtWZBIGjMr9sjqfe00twVuqWV9TcGdRIqhNwPErboFXdWP0zbYRjPZBN2pNWUoLbaKXZABsZAfM9BUcSEKdHnAcVDtfub8e8grC75CoCs7Kdeb8kW7apCVtgnXIJ5Mo5ohepSqsizRtEKL85z3o8NArHqoXFwewgCwWqAOQUWvmcYrPXvo6Ggx6IDkx1gThlAugZDZD")              # zorunlu
PHONE_NUMBER_ID = os.getenv(805413139332295")        # zorunlu
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v20.0")

# Demo state store (RAM). Prod'da DB kullanılır.
SESSIONS = {}  # phone -> dict(step, product, name, address, payment, created_at)

PRODUCTS = {
    "1": ("Pizza", 499),
    "2": ("Burger", 349),
    "3": ("İçecek", 79),
}

def send_text(to: str, body: str) -> None:
    if not ACCESS_TOKEN or not PHONE_NUMBER_ID:
        # Bu hata olursa Render Environment eksik demektir
        print("❌ ACCESS_TOKEN veya PHONE_NUMBER_ID eksik. Render Environment'e ekle.")
        return

    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=20)
    if r.status_code >= 300:
        print("❌ Send error:", r.status_code, r.text)

def get_message(req_json: dict):
    """
    Cloud API webhook payload içinden tek bir mesajı çeker.
    """
    try:
        msg = req_json["entry"][0]["changes"][0]["value"]["messages"][0]
        from_number = msg["from"]
        text = (msg.get("text", {}) or {}).get("body", "")
        return from_number, text
    except Exception:
        return None, None

@app.get("/health")
def health():
    return {"ok": True}, 200

# 1) Webhook verify (GET)
@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

# 2) Messages (POST)
@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}
    from_number, text = get_message(data)

    # WhatsApp bazen status event vs yollar; mesaj yoksa ok dön
    if not from_number:
        return "ok", 200

    msg = (text or "").strip()
    lower = msg.lower()

    # Başlat / reset komutları
    if lower in ("siparis", "sipariş", "/siparis", "başla", "basla"):
        SESSIONS[from_number] = {
            "step": "product",
            "created_at": time.time(),
            "product": None,
            "name": None,
            "address": None,
            "payment": None,
        }
        send_text(
            from_number,
            "Sipariş başlıyor ✅\n"
            "Ürün seç:\n"
            "1) Pizza (499₺)\n"
            "2) Burger (349₺)\n"
            "3) İçecek (79₺)\n\n"
            "Cevap: 1 / 2 / 3"
        )
        return "ok", 200

    if lower in ("iptal", "cancel", "/iptal"):
        SESSIONS.pop(from_number, None)
        send_text(from_number, "İptal edildi ❌ Tekrar başlamak için 'siparis' yaz.")
        return "ok", 200

    s = SESSIONS.get(from_number)
    if not s:
        send_text(from_number, "Sipariş başlatmak için 'siparis' yaz.\nİptal için 'iptal'.")
        return "ok", 200

    step = s["step"]

    # 1) ürün seçimi
    if step == "product":
        if msg not in PRODUCTS:
            send_text(from_number, "Lütfen 1 / 2 / 3 yaz.")
            return "ok", 200
        pname, price = PRODUCTS[msg]
        s["product"] = {"name": pname, "price": price}
        s["step"] = "name"
        send_text(from_number, f"Seçtin: {pname} ✅\nAd Soyad yaz:")
        return "ok", 200

    # 2) ad soyad
    if step == "name":
        if len(msg) < 3:
            send_text(from_number, "Ad soyad çok kısa. Tekrar yaz:")
            return "ok", 200
        s["name"] = msg
        s["step"] = "address"
        send_text(from_number, "Adresini yaz (il/ilçe/mahalle + açık adres):")
        return "ok", 200

    # 3) adres
    if step == "address":
        if len(msg) < 10:
            send_text(from_number, "Adres kısa görünüyor. Biraz daha detay yaz:")
            return "ok", 200
        s["address"] = msg
        s["step"] = "payment"
        send_text(from_number, "Ödeme seç:\n1) Kapıda ödeme\n2) Havale\nCevap: 1 / 2")
        return "ok", 200

    # 4) ödeme
    if step == "payment":
        if msg not in ("1", "2"):
            send_text(from_number, "Lütfen 1 (Kapıda) veya 2 (Havale) yaz.")
            return "ok", 200
        s["payment"] = "Kapıda ödeme" if msg == "1" else "Havale"
        s["step"] = "confirm"
        p = s["product"]
        send_text(
            from_number,
            "Sipariş özeti:\n"
            f"Ürün: {p['name']} ({p['price']}₺)\n"
            f"Ad: {s['name']}\n"
            f"Adres: {s['address']}\n"
            f"Ödeme: {s['payment']}\n\n"
            "Onaylıyor musun?\n1) Onayla\n2) İptal"
        )
        return "ok", 200

    # 5) onay
    if step == "confirm":
        if msg == "1":
            order_no = "S" + str(int(time.time()))[-6:]
            p = s["product"]
            send_text(from_number, f"Onaylandı ✅\nSipariş No: {order_no}\n{p['name']} hazırlanıyor.")
            SESSIONS.pop(from_number, None)
            return "ok", 200
        if msg == "2":
            SESSIONS.pop(from_number, None)
            send_text(from_number, "İptal edildi ❌ Tekrar başlamak için 'siparis' yaz.")
            return "ok", 200
        send_text(from_number, "Lütfen 1 (Onayla) veya 2 (İptal) yaz.")
        return "ok", 200

    # default
    send_text(from_number, "Bir şeyler karıştı. Tekrar başlamak için 'siparis' yaz.")
    SESSIONS.pop(from_number, None)
    return "ok", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
