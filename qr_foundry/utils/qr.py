from __future__ import annotations
import io
import base64

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(data: str, *, box_size: int = 10, border: int = 2, label: str | None = None) -> bytes:
	"""Return PNG bytes for a QR with optional bottom label."""
	qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
	qr.add_data(data)
	qr.make(fit=True)
	img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

	if label:
		# Minimal label strip under QR
		from PIL import Image, ImageDraw, ImageFont

		W, H = img.size
		pad_h = max(26, H // 8)
		out = Image.new("RGB", (W, H + pad_h), "white")
		out.paste(img, (0, 0))
		draw = ImageDraw.Draw(out)
		try:
			font = ImageFont.load_default()
		except Exception:
			font = None
		text = str(label)
		tw, th = draw.textlength(text, font=font), (font.size if font else 12)
		draw.text(((W - tw) / 2, H + (pad_h - th) / 2), text, fill="black", font=font)
		img = out

	buf = io.BytesIO()
	img.save(buf, format="PNG", optimize=True)
	return buf.getvalue()


def make_data_uri(png_bytes: bytes) -> str:
	b64 = base64.b64encode(png_bytes).decode("ascii")
	return f"data:image/png;base64,{b64}"
