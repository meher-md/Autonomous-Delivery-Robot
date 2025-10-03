from flask import Flask, request, jsonify
import qrcode
import base64
from io import BytesIO

app = Flask(__name__)

@app.route("/generate_qr", methods=["POST"])
def generate_qr():
    try:
        data = request.get_json(force=True)
        order_id = data.get("order_id", "")
        phone    = data.get("phone", "")
        address  = data.get("address", "")

        if not order_id or not phone or not address:
            return jsonify({"success": False, "message": "Missing fields"}), 400

        # النص اللي يدخل جوا الـ QR
        qr_text = f"Order:{order_id}; Phone:{phone}; Address:{address}"

        # توليد QR
        img = qrcode.make(qr_text)
        buf = BytesIO()
        img.save(buf, format="PNG")
        qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return jsonify({
            "success": True,
            "message": "QR generated",
            "qr_base64": qr_base64
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    # خليه يشتغل على كل الـ IPs بتاعة الروبوت
    app.run(host="0.0.0.0", port=5000)

@app.route("/move_robot", methods=["POST"])
def move_robot():
    try:
        data = request.get_json(force=True)
        cmd  = (data.get("cmd") or "").lower()   # forward / back / left / right / stop
        # TODO: هنا نفّذ الأمر على الروبوت (publish ROS2, call service.. الخ)
        # مؤقتًا نرجّع OK فقط
        return jsonify({"ok": True, "echo": cmd})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500
