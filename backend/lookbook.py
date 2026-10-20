"""Compose a WhatsApp-ready new-collection card (1080x1350 PNG)."""
import math
from io import BytesIO
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONTS = Path(__file__).parent / "fonts"
W, H = 1080, 1350
NAVY, GOLD, IVORY, INK, MUTED = "#1F3A5F", "#D9AE55", "#FAF8F5", "#1F2430", "#5F6672"


def _font(name: str, size: int):
    return ImageFont.truetype(str(FONTS / name), size)


def _fit(draw, text: str, font, max_w: int) -> str:
    while text and draw.textlength(text, font=font) > max_w:
        text = text[:-2] + "…" if len(text) > 2 else ""
    return text


def inr(n: int) -> str:
    s = str(int(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        head = ",".join([head[max(0, i - 2):i] for i in range(len(head), 0, -2)][::-1])
        s = f"{head},{tail}"
    return f"₹{s}"


def build_card(title: str, subtitle: Optional[str], branch_name: str, footer: str,
               tiles: List[dict]) -> bytes:
    """tiles: [{photo: bytes|None, name, detail, price}]"""
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 210], fill=NAVY)
    d.text((60, 52), _fit(d, title, _font("CormorantGaramond-Bold.ttf", 76), W - 120),
           font=_font("CormorantGaramond-Bold.ttf", 76), fill=GOLD)
    d.text((62, 146), _fit(d, subtitle or branch_name, _font("NotoSans-Regular.ttf", 30), W - 120),
           font=_font("NotoSans-Regular.ttf", 30), fill="#FFFFFF")

    n = len(tiles)
    cols = 1 if n == 1 else 2
    rows = math.ceil(n / cols)
    top, bottom, pad = 240, H - 120, 30
    cw = (W - pad * (cols + 1)) // cols
    ch = (bottom - top - pad * (rows - 1)) // rows
    text_h = 118
    f_name, f_det, f_price = (_font("NotoSans-Bold.ttf", 30), _font("NotoSans-Regular.ttf", 24),
                              _font("NotoSans-Bold.ttf", 34))
    for idx, t in enumerate(tiles):
        r, c = divmod(idx, cols)
        x, y = pad + c * (cw + pad), top + r * (ch + pad)
        if cols == 2 and n % 2 and idx == n - 1:
            x = (W - cw) // 2
        d.rectangle([x, y, x + cw, y + ch], fill="#FFFFFF", outline="#E7E2D9", width=2)
        ph = ch - text_h
        if t.get("photo"):
            try:
                src = Image.open(BytesIO(t["photo"])).convert("RGB")
                photo = ImageOps.contain(src, (cw - 4, ph - 2))
                d.rectangle([x + 2, y + 2, x + cw - 2, y + ph], fill="#FFFFFF")
                img.paste(photo, (x + 2 + (cw - 4 - photo.width) // 2, y + 2 + (ph - 2 - photo.height) // 2))
            except Exception:
                t["photo"] = None
        if not t.get("photo"):
            d.rectangle([x + 2, y + 2, x + cw - 2, y + ph], fill="#F3F0EA")
            d.text((x + cw / 2, y + ph / 2), "Photo coming soon", font=f_det, fill=MUTED, anchor="mm")
        d.line([x, y + ph, x + cw, y + ph], fill=GOLD, width=3)
        ty = y + ph + 12
        d.text((x + 20, ty), _fit(d, t["name"], f_name, cw - 40), font=f_name, fill=INK)
        price_w = d.textlength(t["price"], font=f_price)
        d.text((x + 20, ty + 42), _fit(d, t["detail"], f_det, cw - 60 - price_w), font=f_det, fill=MUTED)
        d.text((x + cw - 20, ty + 40), t["price"], font=f_price, fill=NAVY, anchor="ra")

    d.rectangle([0, H - 90, W, H], fill=NAVY)
    d.text((W / 2, H - 45), _fit(d, footer, _font("NotoSans-Regular.ttf", 22), W - 80),
           font=_font("NotoSans-Regular.ttf", 22), fill="#FFFFFF", anchor="mm")
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
