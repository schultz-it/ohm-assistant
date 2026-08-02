"""Genera icon.png (quadrata) e logo.png (orizzontale) per l'add-on.

Concetto: un quadrato diviso in due — ambra (Andrea) e azzurro (Genitori), gli
stessi colori che l'app usa per le due unità — separati da un fulmine bianco.
Il fulmine è la linea di divisione: elettricità + ripartizione in un segno solo.

Uso: ``python tools/make_icons.py`` (serve Pillow). Riscrive i due PNG
nell'add-on, quindi va rilanciato solo se si cambia il marchio.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "ohm_assistant"

AMBER = ((251, 191, 36), (217, 119, 6))    # amber-400 → amber-600
SKY = ((56, 189, 248), (2, 132, 199))      # sky-400 → sky-600
SS = 4                                      # supersampling per bordi puliti


def vgradient(size, top, bottom):
    """Sfumatura verticale come immagine RGB."""
    w, h = size
    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return grad.resize((w, h), Image.BILINEAR)


def bolt_points(w, h):
    """Spezzata del fulmine, dal bordo alto a quello basso (coordinate assolute)."""
    return [(0.68 * w, -0.03 * h), (0.33 * w, 0.47 * h),
            (0.64 * w, 0.47 * h), (0.28 * w, 1.03 * h)]


def tile(w, h, radius_frac=0.22, bolt_frac=0.10):
    """Il quadrato diviso, con angoli arrotondati e sfondo trasparente."""
    W, H = w * SS, h * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # Due sfumature affiancate, ritagliate dalla spezzata del fulmine.
    left, right = vgradient((W, H), *AMBER), vgradient((W, H), *SKY)
    pts = bolt_points(W, H)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(
        [(-10, -10)] + pts + [(-10, H + 10)], fill=255)
    img.paste(right, (0, 0))
    img.paste(left, (0, 0), mask)

    # Il fulmine bianco che separa le due metà.
    ImageDraw.Draw(img).line(pts, fill=(255, 255, 255, 255),
                             width=round(bolt_frac * W), joint="curve")

    # Angoli arrotondati.
    corners = Image.new("L", (W, H), 0)
    ImageDraw.Draw(corners).rounded_rectangle(
        [0, 0, W - 1, H - 1], radius=round(radius_frac * W), fill=255)
    img.putalpha(corners)
    return img.resize((w, h), Image.LANCZOS)


def icon(size=512):
    tile(size, size).save(OUT / "icon.png")
    return size


def logo(h=200, mark=150, pad=24, gap=28):
    """Marchio + testo, con la tela dimensionata sul testo (niente troncamenti)."""
    font_path = "/System/Library/Fonts/SFNSRounded.ttf"
    try:
        f1 = ImageFont.truetype(font_path, 56)
        f2 = ImageFont.truetype(font_path, 26)
    except OSError:
        f1 = f2 = ImageFont.load_default()

    title, claim = "Ohm Assistant", "bollette e spese divise"
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    text_w = max(probe.textlength(title, font=f1), probe.textlength(claim, font=f2))
    w = round(pad + mark + gap + text_w + pad)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    badge = tile(mark, mark)
    img.paste(badge, (pad, (h - mark) // 2), badge)

    draw = ImageDraw.Draw(img)
    x = pad + mark + gap
    # Ambra-600 e grigio medio: il logo finisce sia su schede chiare sia scure
    # nello store di HA, e il nero là sopra sparirebbe.
    draw.text((x, h // 2 - 6), title, font=f1, fill=(217, 119, 6, 255),
              anchor="ls")
    draw.text((x + 2, h // 2 + 34), claim, font=f2, fill=(140, 140, 140, 255),
              anchor="ls")
    img.save(OUT / "logo.png")
    return w, h


print("icon.png", icon(), "· logo.png", logo())
