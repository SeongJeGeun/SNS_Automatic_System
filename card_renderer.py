import json
import os

from PIL import Image, ImageDraw, ImageFont

from image_generator import generate_background_images
from telegram_agent import request_telegram_approval


_BRAIN_PATH = os.path.expanduser(
    os.getenv(
        "CODEX_FALLBACK_IMAGE_DIR",
        os.path.join("codex_assets", "fallback_backgrounds"),
    )
)
BACKGROUND_IMAGES = [
    os.path.join(_BRAIN_PATH, f"page{i}_bg_1779811878358.png") if i == 1 else
    os.path.join(_BRAIN_PATH, f"page{i}_bg_1779811898677.png") if i == 2 else
    os.path.join(_BRAIN_PATH, f"page{i}_bg_1779811918374.png") if i == 3 else
    os.path.join(_BRAIN_PATH, f"page{i}_bg_1779811936436.png") if i == 4 else
    os.path.join(_BRAIN_PATH, f"page{i}_bg_1779811956257.png")
    for i in range(1, 6)
]


def wrap_text(text, font, max_width, draw):
    words = text.split(" ")
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] > max_width:
            current_line.pop()
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _font(path, size, fallback_path=None, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        if fallback_path:
            try:
                return ImageFont.truetype(fallback_path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _theme_colors(theme):
    if theme == "cream":
        return {
            "bg": (248, 250, 240, 255),
            "head": (15, 23, 42, 255),
            "sub": (71, 85, 105, 255),
            "accent": (29, 78, 216, 255),
        }
    if theme == "slate_gray":
        return {
            "bg": (51, 65, 85, 255),
            "head": (248, 250, 240, 255),
            "sub": (148, 163, 184, 255),
            "accent": (212, 175, 55, 255),
        }
    return {
        "bg": (15, 23, 42, 255),
        "head": (248, 250, 240, 255),
        "sub": (148, 163, 184, 255),
        "accent": (212, 175, 55, 255),
    }


def _measure_lines(lines, font, draw, spacing):
    heights = []
    total = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        height = bbox[3] - bbox[1]
        heights.append(height)
        total += height
    total += max(0, len(lines) - 1) * spacing
    return heights, total


def generate_card_news_images(script_file="script.json"):
    print("[Step 2] 카드뉴스 이미지 가변 합성 (Sophisticated Storytelling)...")
    if not os.path.exists(script_file):
        print("[Error] script.json 파일이 존재하지 않아 이미지 합성이 불가합니다.")
        return False

    try:
        with open(script_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        pages = data.get("pages", [])
        generated_backgrounds = generate_background_images(data)
        if not generated_backgrounds and os.getenv("IMAGE_GENERATION_PROVIDER", "codex").lower() == "codex":
            request_telegram_approval(
                "Codex 이미지 미생성",
                "새 배경 이미지가 아직 감지되지 않았습니다. 기존 fallback 배경으로 카드뉴스 합성을 계속 진행합니다.",
            )

        sans_font_path = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
        if not os.path.exists(sans_font_path):
            sans_font_path = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

        serif_font_path = "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf"
        if not os.path.exists(serif_font_path):
            serif_font_path = "/System/Library/Fonts/Supplemental/Times New Roman.ttf"

        for i, page in enumerate(pages):
            theme = page.get("theme_color", "deep_navy").lower()
            colors = _theme_colors(theme)
            width, height = 1080, 1080

            img = Image.new("RGBA", (width, height), colors["bg"])
            draw = ImageDraw.Draw(img)

            bg_path = None
            blend_strength = 0.38
            if i < len(generated_backgrounds) and os.path.exists(generated_backgrounds[i]):
                bg_path = generated_backgrounds[i]
            elif i < len(BACKGROUND_IMAGES) and os.path.exists(BACKGROUND_IMAGES[i]):
                bg_path = BACKGROUND_IMAGES[i]
                blend_strength = 0.12

            if bg_path:
                try:
                    bg_img = Image.open(bg_path).convert("RGBA").resize((width, height))
                    img = Image.blend(img, bg_img.convert("L").convert("RGBA"), blend_strength)
                    draw = ImageDraw.Draw(img)
                except Exception as exc:
                    print(f"    [Warning] 배경 오버레이 적용 실패: {exc}")

            frame_margin = 45
            accent = colors["accent"]
            outline = accent if theme == "cream" else (accent[0], accent[1], accent[2], 80)
            draw.rectangle([frame_margin, frame_margin, width - frame_margin, height - frame_margin], outline=outline, width=2)

            head_font = _font(serif_font_path, 54, "/System/Library/Fonts/Supplemental/Georgia.ttf")
            sub_font = _font(sans_font_path, 32, "/System/Library/Fonts/Helvetica.ttc")

            max_text_width = width - (frame_margin * 4)
            head_lines = wrap_text(page.get("heading", ""), head_font, max_text_width, draw)
            sub_lines = wrap_text(page.get("sub_text", ""), sub_font, max_text_width, draw)

            head_heights, total_head_height = _measure_lines(head_lines, head_font, draw, 15)
            sub_heights, total_sub_height = _measure_lines(sub_lines, sub_font, draw, 12)

            divider_space = 50
            current_y = (height - (total_head_height + divider_space + total_sub_height)) // 2

            for idx, line in enumerate(head_lines):
                bbox = draw.textbbox((0, 0), line, font=head_font)
                draw.text(((width - (bbox[2] - bbox[0])) // 2, current_y), line, font=head_font, fill=colors["head"])
                current_y += head_heights[idx] + 15

            current_y += 10
            line_y = current_y + 10
            line_length = 120
            draw.line([(width - line_length) // 2, line_y, (width + line_length) // 2, line_y], fill=accent, width=3)
            current_y += divider_space - 10

            for idx, line in enumerate(sub_lines):
                bbox = draw.textbbox((0, 0), line, font=sub_font)
                draw.text(((width - (bbox[2] - bbox[0])) // 2, current_y), line, font=sub_font, fill=colors["sub"])
                current_y += sub_heights[idx] + 12

            output_path = f"page{i + 1}.png"
            img.convert("RGB").save(output_path, "PNG")
            print(f"  - 이미지 합성 완료 (테마: {theme}): {output_path}")
        return True
    except Exception as exc:
        print(f"[Error] 카드뉴스 이미지 합성 실패: {exc}")
        return False


if __name__ == "__main__":
    generate_card_news_images()
