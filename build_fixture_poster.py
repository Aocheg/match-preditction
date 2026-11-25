#!/usr/bin/env python3
"""Generate the combined Legendary FC vs Learn2Earn FC matchday fixture poster."""

import os
from PIL import Image, ImageDraw, ImageFont, ImageOps


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def load_font(path, size):
    return ImageFont.truetype(path, size)


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    return mask


def draw_centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw / 2, y), text, font=font, fill=fill)


def draw_glass_box(canvas, box, radius, fill_rgba, outline_rgba, width=2):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layer)
    ldraw.rounded_rectangle(box, radius=radius, fill=fill_rgba, outline=outline_rgba, width=width)
    return Image.alpha_composite(canvas, layer)


def paste_team_card(canvas, img_path, box, border_color, title, subtitle, font_title, font_sub):
    x, y, w, h = box
    radius = 20
    img = ImageOps.exif_transpose(Image.open(img_path)).convert("RGB")
    card_img = ImageOps.fit(img, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.15))

    # Subtle bottom gradient inside the portrait for clean team name legibility
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    bar_h = 98
    for dy in range(bar_h):
        alpha = int(230 * (dy / bar_h))
        odraw.line([(0, h - bar_h + dy), (w, h - bar_h + dy)], fill=(6, 14, 10, alpha))
    card_rgba = Image.alpha_composite(card_img.convert("RGBA"), overlay)

    mask = rounded_mask((w, h), radius)
    canvas.paste(card_rgba, (x, y), mask)

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((x, y, x + w, y + h), radius=radius, outline=border_color, width=4)
    draw_centered_text(draw, x + w / 2, y + h - 72, title, font_title, (255, 255, 255, 255))
    draw_centered_text(draw, x + w / 2, y + h - 36, subtitle, font_sub, border_color + (255,))


def build_poster(out_path=None):
    if out_path is None:
        out_path = os.path.join(STATIC_DIR, "fixture-poster.png")

    W, H = 1280, 780
    bg = Image.open(os.path.join(STATIC_DIR, "hero-3d.jpg")).convert("RGB")
    bg = ImageOps.fit(bg, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).convert("RGBA")

    # Dark stadium tint so the team portraits and match details pop cleanly
    scrim = Image.new("RGBA", (W, H), (6, 16, 12, 168))
    canvas = Image.alpha_composite(bg, scrim)

    f_kicker = load_font(FONT_BOLD, 18)
    f_header = load_font(FONT_BOLD, 40)
    f_team = load_font(FONT_BOLD, 25)
    f_sub = load_font(FONT_REG, 15)
    f_vs = load_font(FONT_BOLD, 32)
    f_venue = load_font(FONT_BOLD, 24)
    f_prize = load_font(FONT_BOLD, 20)

    # Top header pill
    canvas = draw_glass_box(
        canvas, (300, 24, 980, 62), radius=19, fill_rgba=(20, 32, 18, 210), outline_rgba=(250, 204, 21, 200), width=2
    )
    draw = ImageDraw.Draw(canvas)
    draw_centered_text(draw, W / 2, 32, "OFFICIAL MATCHDAY FIXTURE  •  SCORE PREDICTOR", f_kicker, (253, 224, 71, 255))
    draw_centered_text(draw, W / 2, 74, "LEGENDARY FC   VS   LEARN2EARN FC", f_header, (255, 255, 255, 255))

    # Side-by-side abdomen-upward portraits
    card_w, card_h = 380, 445
    top_y = 140
    left_x = 125
    right_x = W - 125 - card_w

    paste_team_card(
        canvas,
        os.path.join(STATIC_DIR, "team-legendary.jpg"),
        (left_x, top_y, card_w, card_h),
        (250, 204, 21),
        "LEGENDARY FC",
        "Home  •  Black & Yellow, Black Shorts",
        f_team,
        f_sub,
    )
    paste_team_card(
        canvas,
        os.path.join(STATIC_DIR, "team-learn2earn.jpg"),
        (right_x, top_y, card_w, card_h),
        (248, 113, 113),
        "LEARN2EARN FC",
        "Away  •  Red & White Jersey",
        f_team,
        f_sub,
    )

    # Center VS badge
    draw = ImageDraw.Draw(canvas)
    cx, cy = W // 2, top_y + card_h // 2
    r = 45
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 204, 21, 255), outline=(255, 255, 255, 235), width=4)
    draw_centered_text(draw, cx, cy - 18, "VS", f_vs, (7, 19, 12, 255))

    # Venue & Kickoff bar
    vy1, vy2 = 608, 668
    canvas = draw_glass_box(
        canvas, (125, vy1, W - 125, vy2), radius=14, fill_rgba=(10, 28, 20, 225), outline_rgba=(134, 239, 172, 185), width=2
    )
    draw = ImageDraw.Draw(canvas)
    draw_centered_text(draw, W / 2, vy1 + 16, "VENUE: MINT SCHOOL PITCH    |    KICKOFF TIME: 5:00 PM", f_venue, (241, 245, 249, 255))

    # Prize strip
    py1, py2 = 686, 744
    canvas = draw_glass_box(
        canvas, (125, py1, W - 125, py2), radius=14, fill_rgba=(28, 22, 6, 225), outline_rgba=(250, 204, 21, 185), width=2
    )
    draw = ImageDraw.Draw(canvas)
    prize_text = "EXACT SCORE PRIZES:    1ST: ₦20,000    •    2ND: ₦10,000    •    3RD: ₦5,000"
    draw_centered_text(draw, W / 2, py1 + 17, prize_text, f_prize, (253, 224, 71, 255))

    canvas.convert("RGB").save(out_path, format="PNG")
    return out_path


if __name__ == "__main__":
    saved = build_poster()
    print("Generated fixture poster:", saved)
