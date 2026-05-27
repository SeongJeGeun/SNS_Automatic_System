# obsidian_linker.py
import os
import re
from constants import OBSIDIAN_VAULT_PATH

# 1. 핵심 허브 노트와 그 기본 내용 정의
HUB_NOTES = {
    "MindFactory_Core": """# MindFactory Core

MindFactory SNS 자동화 시스템의 중심 두뇌 노트입니다.

## 핵심 연결

[[트렌드_분석]]
[[콘텐츠_전략]]
[[성과_분석]]
[[다음_실험]]
[[실패_원인]]
[[저장률_높은_문장]]
[[첫_장_후킹]]

## 주요 감정 주제

[[번아웃]]
[[무기력]]
[[불안_관리]]
[[자기계발_피로감]]
[[관계_거리두기]]

#MindFactory #AI두뇌 #콘텐츠자동화
""",
    "트렌드_분석": """# 트렌드 분석

요즘 사람들이 겪는 고민과 검색/SNS 흐름을 콘텐츠 주제로 변환하는 노트입니다.

[[MindFactory_Core]]
[[콘텐츠_전략]]
[[번아웃]]
[[무기력]]
[[불안_관리]]
[[자기계발_피로감]]
[[관계_거리두기]]

#트렌드 #콘텐츠기획
""",
    "콘텐츠_전략": """# 콘텐츠 전략

트렌드와 성과 데이터를 바탕으로 카드뉴스 구조를 설계하는 노트입니다.

[[MindFactory_Core]]
[[트렌드_분석]]
[[저장률_높은_문장]]
[[첫_장_후킹]]
[[다음_실험]]
[[성과_분석]]

#전략 #카드뉴스 #CTA
""",
    "성과_분석": """# 성과 분석

게시 후 도달, 좋아요, 댓글, 저장률을 분석하고 다음 개선안을 만드는 노트입니다.

[[MindFactory_Core]]
[[콘텐츠_전략]]
[[실패_원인]]
[[다음_실험]]
[[저장률_높은_문장]]

#성과분석 #저장률 #개선
""",
    "다음_실험": """# 다음 실험

다음 카드뉴스에서 테스트할 가설과 개선안을 정리하는 노트입니다.

[[MindFactory_Core]]
[[성과_분석]]
[[실패_원인]]
[[첫_장_후킹]]
[[저장률_높은_문장]]

#다음실험 #AB테스트 #콘텐츠개선
""",
    "실패_원인": """# 실패 원인

성과가 낮았던 콘텐츠의 원인을 정리합니다.

[[MindFactory_Core]]
[[성과_분석]]
[[다음_실험]]
[[콘텐츠_전략]]

#실패원인 #개선
""",
    "저장률_높은_문장": """# 저장률 높은 문장

독자들의 공감과 저장 욕구를 자극하여 저장률 3.5%를 넘기기 위한 문장 팁입니다.

[[MindFactory_Core]]
[[콘텐츠_전략]]
[[다음_실험]]

#저장률 #체크리스트 #CTA
""",
    "첫_장_후킹": """# 첫 장 후킹

1초 만에 인스타그램 피드 피로감을 깨우는 표지 훅 기획 가이드입니다.

[[MindFactory_Core]]
[[콘텐츠_전략]]
[[다음_실험]]

#후킹 #첫장 #어그로
""",
    "번아웃": """# 번아웃

과도한 성취 지향과 성과 압박 속에서 방전된 2030 청년들을 위한 감정소진 분석입니다.

[[MindFactory_Core]]
[[트렌드_분석]]
[[무기력]]

#번아웃 #감정소진 #위로
""",
    "무기력": """# 무기력

'해야 하는 것'에 압도당해 시작조차 하지 못하고 자책하는 악순환을 분석합니다.

[[MindFactory_Core]]
[[트렌드_분석]]
[[번아웃]]

#무기력 #자율성 #자책
""",
    "불안_관리": """# 불안 관리

늦은 밤의 과각성과 아침의 무기력에 영향을 주는 요인들을 분석합니다.

[[MindFactory_Core]]
[[트렌드_분석]]

#불안관리 #수면루틴
""",
    "자기계발_피로감": """# 자기계발 피로감

갓생 살기 압박에 지친 오디언스에게 필요한 본질적 규율과 행동 철학입니다.

[[MindFactory_Core]]
[[트렌드_분석]]
[[growth]]

#자기계발 #성장 #지속가능성
""",
    "관계_거리두기": """# 관계 거리두기

인간관계에서 오는 감정 낭비를 줄이고 깊이 있는 홀로서기를 지원하는 노트입니다.

[[MindFactory_Core]]
[[트렌드_분석]]

#관계 #거리두기 #인간관계
"""
}

# 2. 키워드 매칭 기반 동적 링크 및 태그 규칙
KEYWORD_RULES = [
    {
        "keywords": ["번아웃", "소진", "지침", "피로"],
        "links": ["번아웃", "무기력"],
        "tags": ["번아웃", "감정소진"]
    },
    {
        "keywords": ["불안", "걱정", "수면", "잠"],
        "links": ["불안_관리"],
        "tags": ["불안관리", "수면루틴"]
    },
    {
        "keywords": ["자기계발", "성장", "노력", "루틴"],
        "links": ["자기계발_피로감", "growth"],
        "tags": ["자기계발", "성장"]
    },
    {
        "keywords": ["관계", "거리두기", "사람", "인간관계"],
        "links": ["관계_거리두기"],
        "tags": ["관계", "거리두기"]
    },
    {
        "keywords": ["저장", "다시 보기", "체크리스트"],
        "links": ["저장률_높은_문장"],
        "tags": ["저장률", "체크리스트"]
    },
    {
        "keywords": ["첫 장", "훅", "후킹", "제목"],
        "links": ["첫_장_후킹"],
        "tags": ["후킹", "첫장"]
    }
]

def run_linker():
    vault_path = OBSIDIAN_VAULT_PATH
    if not os.path.exists(vault_path):
        print(f"[Error] 옵시디언 Vault 경로가 존재하지 않습니다: {vault_path}")
        return

    print(f"============================================================")
    print(f"🧠 MindFactory Obsidian Knowledge Base Auto-Linker Run")
    print(f"경로: {vault_path}")
    print(f"============================================================")

    # 통계 변수
    created_hubs = 0
    updated_trends = 0
    added_links_count = 0
    added_tags_count = 0

    # 1. 핵심 허브 노트 생성 및 검증
    for name, content in HUB_NOTES.items():
        filename = f"{name}.md"
        filepath = os.path.join(vault_path, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✨ 허브 노트 신규 생성 완료: {filename}")
            created_hubs += 1

    # 2. .md 파일 전체 스캔
    all_files = [f for f in os.listdir(vault_path) if f.endswith(".md")]

    for filename in all_files:
        filepath = os.path.join(vault_path, filename)
        note_name = os.path.splitext(filename)[0]

        # 허브 노트 자체는 스킵 (기본 구조에 연결이 이미 선언됨)
        if note_name in HUB_NOTES:
            continue

        # A. trend_search_*.md 공통 링크 주입
        if filename.startswith("trend_search_"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"[Warning] {filename} 읽기 실패: {e}")
                continue

            updated = False

            # 공통 지식 링크 블록 추가 대상 여부 확인
            if "## 연결된 지식" not in content:
                link_block = "\n\n## 연결된 지식\n\n[[MindFactory_Core]]\n[[트렌드_분석]]\n[[콘텐츠_전략]]\n[[다음_실험]]\n\n#트렌드 #콘텐츠기획 #MindFactory\n"
                content += link_block
                added_links_count += 4
                added_tags_count += 3
                updated = True

            # 키워드 스캔 및 맞춤 링크 주입
            keywords_text = []
            tags_text = []
            for rule in KEYWORD_RULES:
                # 텍스트 내에서 키워드 출현 여부 확인
                if any(kw in content for kw in rule["keywords"]):
                    for link in rule["links"]:
                        link_syntax = f"[[{link}]]"
                        if link_syntax not in content:
                            keywords_text.append(link_syntax)
                            added_links_count += 1
                            updated = True
                    for tag in rule["tags"]:
                        tag_syntax = f"#{tag}"
                        if tag_syntax not in content:
                            tags_text.append(tag_syntax)
                            added_tags_count += 1
                            updated = True

            if keywords_text or tags_text:
                extra_block = "\n"
                if keywords_text:
                    extra_block += "\n".join(keywords_text) + "\n"
                if tags_text:
                    extra_block += " ".join(tags_text) + "\n"
                content += extra_block

            if updated:
                with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                updated_trends += 1

        # B. 기존 수동 기획 노트 discipline, focus, growth 연결
        elif note_name in ["discipline", "focus", "growth"]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                print(f"[Warning] {filename} 읽기 실패: {e}")
                continue

            updated = False
            links_to_add = []
            if note_name == "discipline":
                links_to_add = ["MindFactory_Core", "콘텐츠_전략", "자기계발_피로감", "다음_실험"]
            elif note_name == "focus":
                links_to_add = ["MindFactory_Core", "콘텐츠_전략", "불안_관리", "저장률_높은_문장"]
            elif note_name == "growth":
                links_to_add = ["MindFactory_Core", "콘텐츠_전략", "자기계발_피로감", "성과_분석"]

            new_lines = []
            for link in links_to_add:
                link_syntax = f"[[{link}]]"
                if link_syntax not in content:
                    new_lines.append(link_syntax)
                    added_links_count += 1
                    updated = True

            if new_lines:
                content += "\n\n## 연결된 허브 지식\n" + "\n".join(new_lines) + "\n"

            if updated:
                with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
                print(f"🔗 로컬 기획 노트 연동 완료: {filename}")

    # 3. 고립 노트(Isolated) 수 분석
    isolated_notes = 0
    for filename in all_files:
        filepath = os.path.join(vault_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                c = f.read()
            # [[링크]]나 #태그가 아예 없는 경우 고립노트로 간주
            links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", c)
            tags = re.findall(r"#([a-zA-Z가-힣0-9_-]+)", c)
            # hex 색상 해시태그 제거
            clean_tags = [t for t in tags if not (re.match(r"^[0-9a-fA-F]{6}$", t) or re.match(r"^[0-9a-fA-F]{3}$", t))]

            if not links and not clean_tags:
                isolated_notes += 1
        except Exception:
            pass

    print(f"============================================================")
    print(f"✅ 연동 완료 통계 보고:")
    print(f" - 신규 생성 허브 노트: {created_hubs}개")
    print(f" - 연동 업데이트된 트렌드 노트(trend_search_*.md): {updated_trends}개")
    print(f" - 주입된 총 내부 링크 수: {added_links_count}개")
    print(f" - 주입된 총 해시태그 수: {added_tags_count}개")
    print(f" - 고립된 노드 수 (Isolated): {isolated_notes}개")
    print(f"============================================================")

    return {
        "created_hubs": created_hubs,
        "updated_trends": updated_trends,
        "added_links": added_links_count,
        "added_tags": added_tags_count,
        "isolated_notes": isolated_notes
    }

if __name__ == "__main__":
    run_linker()
