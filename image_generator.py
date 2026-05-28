import glob
import os
import shutil
from datetime import datetime

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter
from antigravity_bridge import run_image_task

load_dotenv()


REQUEST_LABEL = "Codex/Research Request"
IMAGE_REQUEST_FILE = "codex_image_requests.md"


def build_background_prompt(page, title):
    image_prompt = page.get("image_prompt", "").strip()
    heading = page.get("heading", "").strip()
    sub_text = page.get("sub_text", "").strip()
    theme = page.get("theme_color", "deep_navy").strip()

    return f"""
Create a premium square editorial background image for a Korean Instagram carousel.
Topic: {title}
Slide headline: {heading}
Slide supporting message: {sub_text}
Visual direction: {image_prompt}
Theme color direction: {theme}

Requirements:
- 1:1 square composition
- high-end magazine / cinematic editorial mood
- low saturation, black and white or muted navy/slate/cream palette
- strong empty center area for Korean typography overlay
- no text, no letters, no logos, no watermark, no UI
- avoid neon colors and childish illustration
- Subtly weave in visual storytelling metaphors like the 'Nano Banana' concept (representing slippery daily traps of laziness or sharp focus triggers) to enhance the visual depth and editorial storytelling.
""".strip()


def write_codex_image_brief(prompts, output_file=IMAGE_REQUEST_FILE):
    lines = [
        "# Codex Image Requests",
        "",
        "아래 프롬프트는 Codex/Research Request 이미지 생성으로 처리할 장별 요청입니다.",
        "각 이미지는 생성 후 `CODEX_OUTPUT_DIR`에 저장하면 파이프라인이 최신 PNG를 찾아 사용합니다.",
        "",
    ]
    for index, prompt in enumerate(prompts, start=1):
        lines.extend([
            f"## Page {index}",
            "```text",
            prompt,
            "```",
            "",
        ])

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def find_codex_images(required_count, run_started_at):
    explicit_dir = os.getenv("CODEX_OUTPUT_DIR", "").strip()
    if not explicit_dir:
        return []
    candidates = glob.glob(os.path.join(explicit_dir, "*.png"))

    candidates = [
        path for path in candidates
        if os.path.isfile(path) and os.path.getmtime(path) >= run_started_at
    ]
    candidates.sort(key=lambda path: os.path.getmtime(path))
    return candidates[:required_count]


def generate_codex_local_backgrounds(prompts, output_dir):
    output_paths = []
    palettes = [
        ((15, 23, 42), (212, 175, 55)),
        ((51, 65, 85), (148, 163, 184)),
        ((248, 250, 240), (29, 78, 216)),
        ((25, 31, 46), (94, 234, 212)),
        ((38, 38, 38), (180, 180, 180)),
    ]

    for index, prompt in enumerate(prompts, start=1):
        base, accent = palettes[(index - 1) % len(palettes)]
        img = Image.new("RGB", (1080, 1080), base)
        draw = ImageDraw.Draw(img, "RGBA")

        for step in range(0, 1080, 36):
            alpha = max(10, 70 - step // 24)
            draw.line([(0, step), (1080, step + 320)], fill=(*accent, alpha), width=2)

        margin = 90 + (index % 3) * 24
        draw.rectangle(
            [margin, margin, 1080 - margin, 1080 - margin],
            outline=(*accent, 70),
            width=3,
        )
        draw.ellipse(
            [760 - index * 18, 120 + index * 20, 1160 - index * 18, 520 + index * 20],
            outline=(*accent, 45),
            width=5,
        )

        # The prompt is intentionally not rendered as text; it only influences a stable visual seed.
        seed = sum(ord(ch) for ch in prompt)
        for n in range(16):
            x = (seed * (n + 3) * 17) % 1080
            y = (seed * (n + 5) * 23) % 1080
            r = 20 + ((seed + n * 13) % 90)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*accent, 10))

        img = img.filter(ImageFilter.GaussianBlur(radius=0.7))
        output_path = os.path.join(output_dir, f"page{index}_bg.png")
        img.save(output_path, "PNG")
        output_paths.append(output_path)
        print(f"  - Codex/Research Request 폴백 로컬 배경 생성: {output_path}")

    return output_paths


def collect_codex_images(prompts, output_dir, run_started_at):
    write_codex_image_brief(prompts)

    generated_by_request = []
    for index, prompt in enumerate(prompts, start=1):
        output_path = os.path.join(output_dir, f"page{index}_bg.png")
        result = run_image_task(prompt, output_path)
        if result:
            generated_by_request.append(result)

    if len(generated_by_request) == len(prompts):
        print("[Image Gen] Codex/Research Request 이미지 생성 완료.")
        return generated_by_request

    wait_seconds = int(os.getenv("CODEX_IMAGE_WAIT_SECONDS", "0"))
    explicit_dir = os.getenv("CODEX_OUTPUT_DIR", "").strip()
    if wait_seconds > 0:
        print(f"[Image Gen] 외부 이미지 산출물 대기 중... ({wait_seconds}초)")
        import time
        time.sleep(wait_seconds)
    elif not explicit_dir:
        print("[Image Gen] Codex Image Request 파일만 생성했습니다. 대기 시간이 0초라 이미지 탐색을 생략합니다.")
        print(f"  - 요청 파일: {IMAGE_REQUEST_FILE}")
        return []

    found_images = find_codex_images(len(prompts), run_started_at)
    if len(found_images) < len(prompts):
        print("[Image Gen] Codex/External 산출 이미지가 충분하지 않아 로컬 폴백 배경을 생성합니다.")
        print(f"  - 요청 파일: {IMAGE_REQUEST_FILE}")
        return generate_codex_local_backgrounds(prompts, output_dir)

    output_paths = []
    for index, source_path in enumerate(found_images, start=1):
        target_path = os.path.join(output_dir, f"page{index}_bg.png")
        shutil.copy2(source_path, target_path)
        output_paths.append(target_path)
        print(f"  - 외부 생성 이미지 연결: {source_path} -> {target_path}")
    return output_paths


def generate_background_images(script_data, output_root="generated_backgrounds"):
    pages = script_data.get("pages", [])
    if not pages:
        return []

    run_started_at = datetime.now().timestamp()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_root, run_id)
    os.makedirs(output_dir, exist_ok=True)

    title = script_data.get("title", "")
    prompts = [build_background_prompt(page, title) for page in pages]
    return collect_codex_images(prompts, output_dir, run_started_at)
