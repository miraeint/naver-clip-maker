"""
네이버 클립 9:16 (1080x1920) 슬라이드 4장 렌더링 & ZIP 패키징 엔진
- 단독 실행(CLI): python make_clip_slides.py
- 웹 스튜디오(Streamlit) 연동 지원
- 배지 폭 자동 측정(textbbox), 긴 문장 자동 줄바꿈, 폰트/샘플 이미지 자동 세팅 포함
"""

import os
import json
import math
import shutil
import zipfile
import urllib.request
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH, HEIGHT = 1080, 1920


def ensure_fonts(font_bold_path: str = "font/bold.ttf", font_reg_path: str = "font/regular.ttf") -> Tuple[str, str]:
    """
    폰트 파일이 없을 경우 Pretendard 폰트를 다운로드하거나 Windows 기본 고딕(맑은 고딕)을 자동 연결합니다.
    """
    os.makedirs(os.path.dirname(font_bold_path) or "font", exist_ok=True)
    os.makedirs(os.path.dirname(font_reg_path) or "font", exist_ok=True)

    urls = {
        font_bold_path: "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Bold.ttf",
        font_reg_path: "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf",
    }
    win_fallbacks = {
        font_bold_path: r"C:\Windows\Fonts\malgunbd.ttf",
        font_reg_path: r"C:\Windows\Fonts\malgun.ttf",
    }

    for target_path, url in urls.items():
        if not os.path.exists(target_path):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp, open(target_path, "wb") as out_f:
                    shutil.copyfileobj(resp, out_f)
            except Exception:
                fb = win_fallbacks.get(target_path)
                if fb and os.path.exists(fb):
                    shutil.copyfile(fb, target_path)

    return font_bold_path, font_reg_path


def ensure_sample_images(data: Dict) -> None:
    """
    슬라이드에 지정된 이미지 파일이 아직 없을 경우,
    즉시 테스트가 가능하도록 고해상도 스마트공장/SPC 시각화 샘플 이미지를 자동 생성합니다.
    """
    os.makedirs("images", exist_ok=True)
    font_b_path, font_r_path = ensure_fonts(
        data.get("font_bold", "font/bold.ttf"),
        data.get("font_regular", "font/regular.ttf")
    )
    try:
        f_label = ImageFont.truetype(font_b_path, 28)
        f_small = ImageFont.truetype(font_r_path, 22)
    except Exception:
        f_label = ImageFont.load_default()
        f_small = ImageFont.load_default()

    for idx, slide in enumerate(data.get("slides", []), 1):
        img_path = slide.get("bg_image") if slide.get("type") == "vertical_bg" else slide.get("photo")
        if not img_path or os.path.exists(img_path):
            continue

        os.makedirs(os.path.dirname(img_path) or "images", exist_ok=True)

        if slide.get("type") == "vertical_bg":
            # 1080x1920 스마트공장 다크 테크 배경 생성
            im = Image.new("RGB", (WIDTH, HEIGHT), (12, 20, 38))
            dr = ImageDraw.Draw(im)
            for y in range(0, HEIGHT, 60):
                dr.line([(0, y), (WIDTH, y)], fill=(22, 36, 62), width=1)
            for x in range(0, WIDTH, 60):
                dr.line([(x, 0), (x, HEIGHT)], fill=(22, 36, 62), width=1)

            # 중앙 영역(500~1220)에 스마트공장 실시간 모니터링 대시보드 그래픽 배치
            dr.rounded_rectangle([(80, 560), (1000, 1180)], radius=28, fill=(18, 30, 54), outline=(56, 189, 248), width=3)
            dr.text((130, 605), "LIVE SMART FACTORY SPC MONITOR", font=f_label, fill=(56, 189, 248))
            dr.line([(130, 665), (950, 665)], fill=(239, 68, 68), width=2)  # UCL
            dr.text((850, 632), "UCL (상한선)", font=f_small, fill=(248, 113, 113))
            dr.line([(130, 860), (950, 860)], fill=(52, 211, 153), width=2)  # CL
            dr.text((860, 827), "CL (중심선)", font=f_small, fill=(52, 211, 153))
            dr.line([(130, 1055), (950, 1055)], fill=(239, 68, 68), width=2)  # LCL
            dr.text((850, 1065), "LCL (하한선)", font=f_small, fill=(248, 113, 113))

            pts = [
                (140, 880), (225, 830), (310, 870), (395, 810),
                (480, 845), (565, 770), (650, 730), (735, 695), (815, 665)
            ]
            dr.line(pts, fill=(56, 189, 248), width=5)
            for px, py in pts[:-1]:
                dr.ellipse([(px - 8, py - 8), (px + 8, py + 8)], fill=(56, 189, 248), outline=(255, 255, 255), width=2)
            # 마지막 경고 포인트
            lx, ly = pts[-1]
            dr.ellipse([(lx - 14, ly - 14), (lx + 14, ly + 14)], fill=(239, 68, 68), outline=(255, 255, 255), width=3)
            im.save(img_path, quality=95)
        else:
            # 970x600 카드용 고해상도 인포그래픽 샘플 사진 생성
            pw, ph = 970, 600
            im = Image.new("RGB", (pw, ph), (18, 28, 48))
            dr = ImageDraw.Draw(im)
            for y in range(0, ph, 40):
                dr.line([(0, y), (pw, y)], fill=(28, 42, 68), width=1)
            for x in range(0, pw, 40):
                dr.line([(x, 0), (x, ph)], fill=(28, 42, 68), width=1)

            h_color = tuple(slide.get("highlight_color", [56, 189, 248]))
            dr.rounded_rectangle([(40, 40), (pw - 40, ph - 40)], radius=20, fill=(15, 23, 42), outline=h_color, width=3)

            if idx == 2:
                dr.text((80, 75), "SPC Control Chart (관리도 조기 경보 원리)", font=f_label, fill=h_color)
                dr.line([(80, 170), (890, 170)], fill=(239, 68, 68), width=3)
                dr.text((745, 132), "UCL (관리상한선)", font=f_small, fill=(248, 113, 113))
                dr.line([(80, 320), (890, 320)], fill=(148, 163, 184), width=2)
                dr.text((755, 285), "CL (평균 중심선)", font=f_small, fill=(203, 213, 225))
                dr.line([(80, 470), (890, 470)], fill=(239, 68, 68), width=3)
                dr.text((745, 480), "LCL (관리하한선)", font=f_small, fill=(248, 113, 113))

                pts = [(110, 340), (210, 300), (310, 330), (410, 290), (510, 260), (610, 225), (710, 195), (810, 180)]
                dr.line(pts, fill=h_color, width=5)
                for px, py in pts:
                    dr.ellipse([(px - 8, py - 8), (px + 8, py + 8)], fill=h_color, outline=(255, 255, 255), width=2)
                dr.rounded_rectangle([(620, 210), (875, 265)], radius=10, fill=(239, 68, 68))
                dr.text((640, 224), "불량 발생 전 이상 감지!", font=f_small, fill=(255, 255, 255))
            elif idx == 3:
                dr.text((80, 75), "시간대별 공정 편차 분석 (특정 구간 흔들림 적발)", font=f_label, fill=h_color)
                bars = [45, 50, 48, 52, 165, 190, 175, 50, 46, 49]
                times = ["09시", "10시", "11시", "12시", "13시", "14시", "15시", "16시", "17시", "18시"]
                for i, (bh, t_str) in enumerate(zip(bars, times)):
                    bx1 = 90 + i * 80
                    by2 = 460
                    by1 = by2 - bh * 1.5
                    b_col = (239, 68, 68) if bh > 100 else h_color
                    dr.rounded_rectangle([(bx1, by1), (bx1 + 48, by2)], radius=6, fill=b_col)
                    dr.text((bx1, by2 + 15), t_str, font=f_small, fill=(203, 213, 225))
            else:
                # 디지털 트윈 & 스마트 데이터 그리드 시각화 씬 그래픽
                dr.rounded_rectangle([(60, 60), (pw - 60, ph - 60)], radius=16, fill=(16, 24, 40), outline=h_color, width=2)
                for i in range(12):
                    lx = 100 + i * 70
                    dr.line([(lx, 100), (lx, ph - 100)], fill=(30, 48, 80), width=1)
                for j in range(8):
                    ly = 100 + j * 50
                    dr.line([(100, ly), (pw - 100, ly)], fill=(30, 48, 80), width=1)
                node_pts = [
                    (180, 200), (320, 280), (460, 220), (600, 310), (740, 250),
                    (250, 380), (390, 450), (530, 390), (670, 460), (810, 400)
                ]
                for p1, p2 in zip(node_pts[:-1], node_pts[1:]):
                    dr.line([p1, p2], fill=h_color, width=3)
                for nx, ny in node_pts:
                    dr.ellipse([(nx - 10, ny - 10), (nx + 10, ny + 10)], fill=h_color, outline=(255, 255, 255), width=2)
                    dr.ellipse([(nx - 18, ny - 18), (nx + 18, ny + 18)], outline=h_color, width=1)

            im.save(img_path, quality=95)


def wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """
    지정된 픽셀 폭(max_width)을 넘지 않도록 텍스트를 자동 줄바꿈합니다.
    기존 줄바꿈(\n)도 그대로 유지합니다.
    """
    if not text:
        return []
    lines = []
    for raw_line in text.split("\n"):
        if not raw_line:
            lines.append("")
            continue
        current = ""
        for ch in raw_line:
            test_line = current + ch
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width or not current:
                current = test_line
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def create_slide_1(cfg, font_b, font_reg, f_badge, f_title, f_sub, f_cta):
    im = Image.open(cfg["bg_image"]).convert("RGBA")
    im_ratio = im.width / im.height
    target_ratio = WIDTH / HEIGHT
    if im_ratio > target_ratio:
        new_h = HEIGHT
        new_w = int(new_h * im_ratio)
    else:
        new_w = WIDTH
        new_h = int(new_w / im_ratio)
    im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - WIDTH) // 2
    top = (new_h - HEIGHT) // 2
    canvas = im.crop((left, top, left + WIDTH, top + HEIGHT))

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    for y in range(520):
        alpha = int(225 * (1 - y / 520))
        draw_ov.line([(0, y), (WIDTH, y)], fill=(10, 15, 25, alpha))

    for y in range(1100, HEIGHT):
        alpha = int(240 * ((y - 1100) / (HEIGHT - 1100)))
        draw_ov.line([(0, y), (WIDTH, y)], fill=(10, 15, 25, alpha))

    canvas = Image.alpha_composite(canvas, overlay)
    draw = ImageDraw.Draw(canvas)

    # Top Area - 실제 텍스트 폭 측정으로 배지 박스 크기 정확히 계산
    badge_text = cfg.get("badge", "")
    badge_bbox = draw.textbbox((0, 0), badge_text, font=f_badge)
    badge_w = (badge_bbox[2] - badge_bbox[0]) + 44
    draw.rounded_rectangle(
        [(55, 118), (55 + badge_w, 176)],
        radius=10,
        fill=(30, 41, 59, 225),
        outline=(59, 130, 246, 255),
        width=2
    )
    draw.text((77, 127), badge_text, font=f_badge, fill=(96, 165, 250))

    # Title & Subtitle (자동 줄바꿈 지원)
    title_lines = wrap_text_to_width(draw, cfg.get("title", ""), f_title, WIDTH - 110)
    title_str = "\n".join(title_lines)
    draw.text((55, 205), title_str, font=f_title, fill=(255, 255, 255), spacing=16)

    title_bbox = draw.textbbox((55, 205), title_str, font=f_title, spacing=16)
    sub_y = max(345, title_bbox[3] + 24)
    draw.text((55, sub_y), cfg.get("subtitle", ""), font=f_sub, fill=(203, 213, 225))

    # Bottom Area
    card_x1, card_y1, card_x2, card_y2 = 55, 1280, 1025, 1820
    card = Image.new("RGBA", (card_x2 - card_x1, card_y2 - card_y1), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [(0, 0), (card_x2 - card_x1, card_y2 - card_y1)],
        radius=24,
        fill=(15, 23, 42, 232),
        outline=(71, 85, 105, 200),
        width=2
    )
    canvas.alpha_composite(card, (card_x1, card_y1))

    text_x = card_x1 + 45
    draw.text((text_x, card_y1 + 45), cfg.get("card_badge", ""), font=font_b, fill=(250, 204, 21))

    cur_y = card_y1 + 120
    max_txt_w = (card_x2 - 45) - (text_x + 40)
    for item in cfg.get("bullets", []):
        bullet = item[0] if len(item) > 0 else "• "
        txt = item[1] if len(item) > 1 else ""
        draw.text((text_x, cur_y), bullet, font=font_b, fill=(56, 189, 248))
        wrapped = wrap_text_to_width(draw, txt, font_reg, max_txt_w)
        for line in wrapped:
            draw.text((text_x + 42, cur_y), line, font=font_reg, fill=(241, 245, 249))
            cur_y += 46
        cur_y += 29

    cta_box_y = card_y2 - 100
    draw.rounded_rectangle([(text_x, cta_box_y), (card_x2 - 45, cta_box_y + 65)], radius=12, fill=(30, 58, 138, 225))
    draw.text((text_x + 30, cta_box_y + 13), cfg.get("cta", ""), font=f_cta, fill=(191, 219, 254))

    return canvas.convert("RGB")


def make_standard_slide(cfg, font_b, font_reg, f_badge, f_title, f_sub, f_cta):
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (15, 23, 42, 255))
    raw_photo = Image.open(cfg["photo"]).convert("RGBA")

    # Background blur
    raw_ratio = raw_photo.width / raw_photo.height
    if raw_ratio > (WIDTH / HEIGHT):
        rh = HEIGHT
        rw = int(rh * raw_ratio)
    else:
        rw = WIDTH
        rh = int(rw / raw_ratio)
    bg_img = raw_photo.resize((rw, rh), Image.Resampling.LANCZOS)
    bx = (rw - WIDTH) // 2
    by = (rh - HEIGHT) // 2
    bg_crop = bg_img.crop((bx, by, bx + WIDTH, by + HEIGHT))
    bg_blurred = bg_crop.filter(ImageFilter.GaussianBlur(35))

    dark_tint = Image.new("RGBA", (WIDTH, HEIGHT), (10, 15, 26, 185))
    canvas = Image.alpha_composite(bg_blurred, dark_tint)
    draw = ImageDraw.Draw(canvas)

    h_color = tuple(cfg.get("highlight_color", [56, 189, 248]))

    # Top Area - 실제 텍스트 폭 측정
    badge_text = cfg.get("badge", "")
    badge_bbox = draw.textbbox((0, 0), badge_text, font=f_badge)
    badge_w = (badge_bbox[2] - badge_bbox[0]) + 44
    draw.rounded_rectangle(
        [(55, 98), (55 + badge_w, 156)],
        radius=10,
        fill=(30, 41, 59, 230),
        outline=h_color,
        width=2
    )
    draw.text((77, 107), badge_text, font=f_badge, fill=h_color)

    title_lines = wrap_text_to_width(draw, cfg.get("title", ""), f_title, WIDTH - 110)
    draw.text((55, 178), "\n".join(title_lines[:2]), font=f_title, fill=(255, 255, 255), spacing=10)
    draw.text((55, 255), cfg.get("subtitle", ""), font=f_sub, fill=(203, 213, 225))

    # Center Photo Frame
    photo_w, photo_h = 970, 600
    p_ratio = raw_photo.width / raw_photo.height
    if p_ratio > (photo_w / photo_h):
        ph = photo_h
        pw = int(ph * p_ratio)
    else:
        pw = photo_w
        ph = int(pw / p_ratio)
    p_resized = raw_photo.resize((pw, ph), Image.Resampling.LANCZOS)
    px = (pw - photo_w) // 2
    py = (ph - photo_h) // 2
    p_cropped = p_resized.crop((px, py, px + photo_w, py + photo_h))

    mask = Image.new("L", (photo_w, photo_h), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([(0, 0), (photo_w, photo_h)], radius=24, fill=255)

    photo_y_start = 340
    canvas.paste(p_cropped, (55, photo_y_start), mask)
    draw.rounded_rectangle(
        [(55, photo_y_start), (55 + photo_w, photo_y_start + photo_h)],
        radius=24,
        outline=(148, 163, 184, 180),
        width=3
    )

    # Bottom Area
    card_x1, card_y1, card_x2, card_y2 = 55, 990, 1025, 1820
    card = Image.new("RGBA", (card_x2 - card_x1, card_y2 - card_y1), (0, 0, 0, 0))
    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle(
        [(0, 0), (card_x2 - card_x1, card_y2 - card_y1)],
        radius=24,
        fill=(15, 23, 42, 235),
        outline=(71, 85, 105, 220),
        width=2
    )
    canvas.alpha_composite(card, (card_x1, card_y1))

    text_x = card_x1 + 45
    draw.text((text_x, card_y1 + 45), cfg.get("card_badge", ""), font=font_b, fill=(250, 204, 21))

    cur_y = card_y1 + 125
    max_txt_w = (card_x2 - 45) - (text_x + 40)
    for item in cfg.get("bullets", []):
        bullet = item[0] if len(item) > 0 else "▶ "
        title_p = item[1] if len(item) > 1 else ""
        desc_p = item[2] if len(item) > 2 else ""
        draw.text((text_x, cur_y), bullet, font=font_b, fill=h_color)
        draw.text((text_x + 40, cur_y), title_p, font=font_b, fill=(255, 255, 255))
        if desc_p:
            wrapped_desc = wrap_text_to_width(draw, desc_p, font_reg, max_txt_w)
            desc_y = cur_y + 48
            for d_line in wrapped_desc:
                draw.text((text_x + 40, desc_y), d_line, font=font_reg, fill=(203, 213, 225))
                desc_y += 42
            cur_y = max(cur_y + 125, desc_y + 28)
        else:
            cur_y += 75

    cta_box_y = card_y2 - 100
    draw.rounded_rectangle([(text_x, cta_box_y), (card_x2 - 45, cta_box_y + 65)], radius=12, fill=(30, 58, 138, 225))
    draw.text((text_x + 30, cta_box_y + 13), cfg.get("cta", ""), font=f_cta, fill=(191, 219, 254))

    return canvas.convert("RGB")


def render_slides_from_config(data: Dict, output_dir: str = "output") -> Tuple[List[str], str]:
    """
    설정 딕셔너리(data)를 받아 4장의 슬라이드 PNG와 ZIP 파일을 생성하고 경로를 반환합니다.
    """
    os.makedirs(output_dir, exist_ok=True)
    font_b_path, font_r_path = ensure_fonts(
        data.get("font_bold", "font/bold.ttf"),
        data.get("font_regular", "font/regular.ttf")
    )
    ensure_sample_images(data)

    font_b = ImageFont.truetype(font_b_path, 34)
    font_reg = ImageFont.truetype(font_r_path, 32)
    f_badge = ImageFont.truetype(font_b_path, 34)
    f_title = ImageFont.truetype(font_b_path, 54)
    f_sub = ImageFont.truetype(font_b_path, 38)
    f_cta = ImageFont.truetype(font_b_path, 34)

    project_name = data.get("project_name", "clip_project")
    generated_files = []

    for idx, slide_cfg in enumerate(data.get("slides", []), 1):
        if slide_cfg.get("type") == "vertical_bg":
            img = create_slide_1(slide_cfg, font_b, font_reg, f_badge, f_title, f_sub, f_cta)
        else:
            img = make_standard_slide(slide_cfg, font_b, font_reg, f_badge, f_title, f_sub, f_cta)

        out_name = os.path.join(output_dir, f"{project_name}_slide_{idx}.png")
        img.save(out_name, "PNG", quality=95)
        generated_files.append(out_name)
        print(f"Generated: {out_name}")

    zip_path = os.path.join(output_dir, f"{project_name}_1080x1920.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in generated_files:
            zf.write(f, os.path.basename(f))
    print(f"\nCompleted! ZIP package created at: {zip_path}")

    return generated_files, zip_path


def main():
    with open("data.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    render_slides_from_config(data, output_dir="output")


if __name__ == "__main__":
    main()
