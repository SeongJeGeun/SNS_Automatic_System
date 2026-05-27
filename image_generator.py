import base64
import glob
from io import BytesIO
import os
import shutil
from datetime import datetime
from urllib.request import urlopen

import requests
from dotenv import load_dotenv
from PIL import Image

load_dotenv()


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
""".strip()


def generate_openai_image(prompt, output_path):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[Image Gen] OPENAI_API_KEY가 없어 이미지 자동생성을 건너뜁니다.")
        return False

    model = os.getenv("IMAGE_GENERATION_MODEL", "gpt-image-1.5")
    quality = os.getenv("IMAGE_GENERATION_QUALITY", "medium")
    size = os.getenv("IMAGE_GENERATION_SIZE", "1024x1024")

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        data = response.json()
    except Exception as exc:
        print(f"[Image Gen] 이미지 생성 요청 실패: {exc}")
        return False

    if response.status_code != 200:
        print(f"[Image Gen] 이미지 생성 API 오류 ({response.status_code}): {data}")
        return False

    image_data = data.get("data", [{}])[0]
    try:
        if image_data.get("b64_json"):
            raw = base64.b64decode(image_data["b64_json"])
        elif image_data.get("url"):
            with urlopen(image_data["url"], timeout=60) as img_response:
                raw = img_response.read()
        else:
            print("[Image Gen] 응답에서 이미지 데이터를 찾지 못했습니다.")
            return False

        with open(output_path, "wb") as f:
            f.write(raw)
        return True
    except Exception as exc:
        print(f"[Image Gen] 이미지 저장 실패: {exc}")
        return False


def generate_gemini_image(prompt, output_path):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[Image Gen] GEMINI_API_KEY가 없어 나노바나나 이미지 생성을 건너뜁니다.")
        return False

    model = os.getenv("IMAGE_GENERATION_MODEL", "gemini-2.5-flash-image")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=[prompt],
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )

        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None):
                image = Image.open(BytesIO(part.inline_data.data))
                image.save(output_path)
                return True

        print("[Image Gen] Gemini 응답에서 이미지 데이터를 찾지 못했습니다.")
        return False
    except Exception as exc:
        print(f"[Image Gen] 나노바나나 이미지 생성 실패: {exc}")
        return False


def write_antigravity_image_brief(prompts, output_file="antigravity_image_requests.md"):
    lines = [
        "# Antigravity Nano Banana Image Requests",
        "",
        "아래 프롬프트는 안티그래비티 내장 나노바나나 이미지 생성에 넘길 장별 요청입니다.",
        "각 이미지는 생성 후 `ANTIGRAVITY_OUTPUT_DIR`에 넣거나, 안티그래비티 기본 brain 폴더에 저장되면 파이프라인이 최신 PNG를 찾아 사용합니다.",
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


def find_antigravity_images(required_count, run_started_at):
    explicit_dir = os.getenv("ANTIGRAVITY_OUTPUT_DIR", "").strip()
    if explicit_dir:
        candidates = glob.glob(os.path.join(explicit_dir, "*.png"))
    else:
        candidates = glob.glob(
            os.path.expanduser("~/.gemini/antigravity-ide/brain/**/*.png"),
            recursive=True,
        )

    candidates = [
        path for path in candidates
        if os.path.isfile(path) and os.path.getmtime(path) >= run_started_at
    ]
    candidates.sort(key=lambda path: os.path.getmtime(path))
    return candidates[:required_count]


def collect_antigravity_images(prompts, output_dir, run_started_at):
    write_antigravity_image_brief(prompts)
    wait_seconds = int(os.getenv("ANTIGRAVITY_IMAGE_WAIT_SECONDS", "0"))
    explicit_dir = os.getenv("ANTIGRAVITY_OUTPUT_DIR", "").strip()
    if wait_seconds > 0:
        print(f"[Image Gen] 안티그래비티 이미지 산출물 대기 중... ({wait_seconds}초)")
        import time
        time.sleep(wait_seconds)
    elif not explicit_dir:
        print("[Image Gen] 안티그래비티 요청 파일만 생성했습니다. 대기 시간이 0초라 이미지 탐색을 생략합니다.")
        print("  - 요청 파일: antigravity_image_requests.md")
        return []

    found_images = find_antigravity_images(len(prompts), run_started_at)
    if len(found_images) < len(prompts):
        print("[Image Gen] 안티그래비티 생성 이미지가 충분하지 않아 기존 배경으로 폴백합니다.")
        print("  - 요청 파일: antigravity_image_requests.md")
        return []

    output_paths = []
    for index, source_path in enumerate(found_images, start=1):
        target_path = os.path.join(output_dir, f"page{index}_bg.png")
        shutil.copy2(source_path, target_path)
        output_paths.append(target_path)
        print(f"  - 안티그래비티 이미지 연결: {source_path} -> {target_path}")
    return output_paths


def generate_background_images(script_data, output_root="generated_backgrounds"):
    pages = script_data.get("pages", [])
    if not pages:
        return []

    provider = os.getenv("IMAGE_GENERATION_PROVIDER", "antigravity").lower()
    if provider not in {"antigravity", "gemini", "openai"}:
        print(f"[Image Gen] 지원하지 않는 이미지 생성 provider입니다: {provider}")
        return []

    run_started_at = datetime.now().timestamp()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_root, run_id)
    os.makedirs(output_dir, exist_ok=True)

    title = script_data.get("title", "")
    generated_paths = []
    prompts = [build_background_prompt(page, title) for page in pages]

    if provider == "antigravity":
        return collect_antigravity_images(prompts, output_dir, run_started_at)

    for index, prompt in enumerate(prompts, start=1):
        output_path = os.path.join(output_dir, f"page{index}_bg.png")
        print(f"[Image Gen] {index}장 배경 자동생성 중...")

        if provider == "gemini":
            success = generate_gemini_image(prompt, output_path)
        else:
            success = generate_openai_image(prompt, output_path)

        if success:
            generated_paths.append(output_path)
            print(f"  - 생성 완료: {output_path}")
        else:
            print(f"  - 생성 실패: {index}장")
            return []

    return generated_paths
