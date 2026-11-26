#!/usr/bin/env python3
"""Generate the Fellows vs Mentors volleyball matchday fixture poster."""

import os
from PIL import Image, ImageDraw, ImageFont


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def draw_centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw / 2, y), text, font=font, fill=fill)


def draw_glass_box(canvas, box, radius, fill_rgba, outline_rgba, width=2):
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(layer)
    ldraw.rounded_rectangle(box, radius=radius, fill=fill_rgba, outline=outline_rgba, width=width)
    return Image.alpha_composite(canvas, layer)


def draw_volleyball(draw, cx, cy, r, ball_fill, line_color):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ball_fill, outline=line_color, width=3)
    draw.arc((cx - r, cy - r, cx + int(r * 0.4), cy + r), 290, 70, fill=line_color, width=3)
    draw.arc((cx - int(r * 0.4), cy - r, cx + r, cy + r), 110, 250, fill=line_color, width=3)
    draw.line([(cx - r + 4, cy), (cx + r - 4, cy)], fill=line_color, width=3)


def draw_team_logo_card(canvas, box, fill_bg, accent, rim, ball_fill, ball_line, label, subtitle, font_name, font_sub):
    x, y, w, h = box
    canvas = draw_glass_box(canvas, (x, y, x + w, y + h), radius=24, fill_rgba=(8, 22, 36, 220), outline_rgba=accent + (210,), width=3)
    draw = ImageDraw.Draw(canvas)

    # Shield crest
    cx = x + w // 2
    sy = y + 36
    sw, sh = 176, 198
    shield_pts = [
        (cx, sy),
        (cx + sw // 2, sy + 28),
        (cx + sw // 2, sy + 108),
        (cx + int(sw * 0.34), sy + 166),
        (cx, sy + sh),
        (cx - int(sw * 0.34), sy + 166),
        (cx - sw // 2, sy + 108),
        (cx - sw // 2, sy + 28),
    ]
    draw.polygon(shield_pts, fill=fill_bg + (255,), outline=rim + (255,), width=5)

    # Volleyball inside shield
    draw_volleyball(draw, cx, sy + 78, 38, ball_fill + (255,), ball_line + (255,))

    # Team ribbon inside shield
    draw.rounded_rectangle((cx - 76, sy + 128, cx + 76, sy + 164), radius=9, fill=(7, 17, 27, 255), outline=rim + (255,), width=2)
    f_badge = ImageFont.truetype(FONT_BOLD, 20)
    draw_centered_text(draw, cx, sy + 135, label.upper(), f_badge, rim + (255,))

    # Card title & subtitle
    draw_centered_text(draw, cx, y + 266, label, font_name, (255, 255, 255, 255))
    draw_centered_text(draw, cx, y + 314, subtitle, font_sub, accent + (255,))
    return canvas


def build_poster(out_path=None):
    if out_path is None:
        out_path = os.path.join(STATIC_DIR, "fixture-poster.png")

    W, H = 1280, 760
    canvas = Image.new("RGBA", (W, H), (8, 22, 38, 255))
    draw = ImageDraw.Draw(canvas)

    # Volleyball court backdrop (court floor + attack lines + center net line)
    draw.rectangle((60, 40, W - 60, H - 40), fill=(15, 42, 66, 255), outline=(255, 255, 255, 60), width=3)
    draw.rectangle((140, 132, W - 140, H - 100), fill=(154, 72, 34, 95), outline=(255, 255, 255, 75), width=3)
    draw.line([(460, 132), (460, H - 100)], fill=(255, 255, 255, 65), width=2)
    draw.line([(W - 460, 132), (W - 460, H - 100)], fill=(255, 255, 255, 65), width=2)
    draw.line([(W // 2, 122), (W // 2, H - 90)], fill=(255, 255, 255, 110), width=4)

    f_kicker = ImageFont.truetype(FONT_BOLD, 18)
    f_header = ImageFont.truetype(FONT_BOLD, 44)
    f_team = ImageFont.truetype(FONT_BOLD, 34)
    f_sub = ImageFont.truetype(FONT_REG, 17)
    f_vs = ImageFont.truetype(FONT_BOLD, 34)
    f_venue = ImageFont.truetype(FONT_BOLD, 23)
    f_prize = ImageFont.truetype(FONT_BOLD, 20)

    # Top header pill
    canvas = draw_glass_box(
        canvas, (300, 26, 980, 64), radius=19, fill_rgba=(12, 30, 48, 225), outline_rgba=(250, 204, 21, 210), width=2
    )
    draw = ImageDraw.Draw(canvas)
    draw_centered_text(draw, W / 2, 34, "VOLLEYBALL MATCHDAY FIXTURE  •  BEST OF 3 ROUNDS", f_kicker, (253, 224, 71, 255))
    draw_centered_text(draw, W / 2, 78, "FELLOWS   VS   MENTORS", f_header, (255, 255, 255, 255))

    # Two Team Logo Cards
    card_w, card_h = 390, 380
    top_y = 152
    canvas = draw_team_logo_card(
        canvas,
        (125, top_y, card_w, card_h),
        fill_bg=(16, 110, 58),
        accent=(250, 204, 21),
        rim=(254, 240, 138),
        ball_fill=(254, 240, 138),
        ball_line=(7, 46, 22),
        label="Fellows",
        subtitle="Home Team  •  Gold & Emerald",
        font_name=f_team,
        font_sub=f_sub,
    )
    canvas = draw_team_logo_card(
        canvas,
        (W - 125 - card_w, top_y, card_w, card_h),
        fill_bg=(168, 28, 36),
        accent=(248, 113, 113),
        rim=(248, 250, 252),
        ball_fill=(248, 250, 252),
        ball_line=(127, 29, 29),
        label="Mentors",
        subtitle="Away Team  •  Crimson & Silver",
        font_name=f_team,
        font_sub=f_sub,
    )

    # Center VS badge
    draw = ImageDraw.Draw(canvas)
    cx, cy = W // 2, top_y + card_h // 2
    r = 46
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(250, 204, 21, 255), outline=(255, 255, 255, 235), width=4)
    draw_centered_text(draw, cx, cy - 19, "VS", f_vs, (7, 19, 12, 255))

    # Venue & Time bar
    vy1, vy2 = 564, 626
    canvas = draw_glass_box(
        canvas, (125, vy1, W - 125, vy2), radius=14, fill_rgba=(10, 26, 42, 232), outline_rgba=(148, 163, 184, 195), width=2
    )
    draw = ImageDraw.Draw(canvas)
    draw_centered_text(draw, W / 2, vy1 + 17, "VENUE: LEEF CENTER VOLLEYBALL COURT    |    TIME: 5:00 PM", f_venue, (241, 245, 249, 255))

    # Prize strip
    py1, py2 = 644, 704
    canvas = draw_glass_box(
        canvas, (125, py1, W - 125, py2), radius=14, fill_rgba=(30, 24, 6, 232), outline_rgba=(250, 204, 21, 195), width=2
    )
    draw = ImageDraw.Draw(canvas)
    draw_centered_text(draw, W / 2, py1 + 18, "EXACT PROGRESSION PRIZES:   1ST: ₦20,000   •   2ND: ₦10,000   •   3RD: ₦5,000", f_prize, (253, 224, 71, 255))

    canvas.convert("RGB").save(out_path, format="PNG")
    return out_path


if __name__ == "__main__":
    saved = build_poster()
    print("Generated volleyball fixture poster:", saved)
