import os
import qrcode
from django.conf import settings

def generate_qr(token: str, session_id: str):
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    media_path = os.path.join(settings.MEDIA_ROOT, f"telegram_login_qr_{session_id}.png")
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    if os.path.exists(media_path):
        os.remove(media_path)
    img.save(media_path)