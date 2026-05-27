import json
import os
import re
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

try:
    from langchain_huggingface import HuggingFaceEmbeddings
    _EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
except ImportError:
    _EMBEDDING_MODEL = None

class ObsidianRAGEngine:
    def __init__(self, vault_path, db_path="faiss_index"):
        self.vault_path = vault_path
        self.db_path = db_path

        self.embeddings = None
        if _EMBEDDING_MODEL:
            print(f"[RAG] 로컬 임베딩 모델 사용: {_EMBEDDING_MODEL}")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=_EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
        else:
            print("[RAG] 로컬 임베딩 패키지가 없어 키워드 검색 모드로 실행합니다.")
        self.vector_store = None
        self._ensure_fallback_vault()

    def _ensure_fallback_vault(self):
        """옵시디언 폴더가 없으면 프로젝트 내부에 기본 테스트용 Vault 폴더 및 md 메모 생성"""
        if not os.path.exists(self.vault_path):
            print(f"[RAG Alert] 설정된 옵시디언 경로 '{self.vault_path}'가 존재하지 않습니다.")
            print("[RAG Alert] 프로젝트 루트 내에 'obsidian_vault' 임시 로컬 메모 저장소를 생성해 가동합니다.")
            self.vault_path = os.path.join(os.getcwd(), "obsidian_vault")
            os.makedirs(self.vault_path, exist_ok=True)

            # 기본 철학 및 카피 메모 md 생성
            notes = {
                "discipline.md": """# 마인드팩토리 - 규율의 미학
동기부여는 감정적 자극일 뿐이다. 그것은 2시간 후면 사라진다.
성공은 오직 매일 약속된 시스템과 규율을 지켜내는 굳건함에서 온다.
기분과 날씨에 의존하지 마라. 행동이 감정을 이끈다.
오늘 걷지 않으면 내일은 뛰어야 한다.""",
                "focus.md": """# 마인드팩토리 - 몰입의 법칙
소음이 가득한 세상에서 압도적 성취를 거두는 유일한 방법은 극도의 몰입이다.
멀티태스킹은 사기다. 한 번에 하나씩 쪼개어 가장 뾰족하게 파고들어라.
하루 딱 2시간 동안 모든 알림과 소음을 차단하고 핵심 작업에만 모든 에너지를 쏟아부어라.""",
                "growth.md": """# 마인드팩토리 - 성장과 한계돌파
성장은 고통스러운 영역에 숨어있다. 당신이 피하고 싶은 그 일 속에 한계 돌파의 열쇠가 있다.
어제보다 1% 나아지는 것에 초점을 맞춰라. 복리의 법칙은 성장에서 가장 강력하게 작동한다.
변화는 불편한 진실을 수용하고, 그것을 즉각적인 실행으로 파괴해 나가는 과정이다."""
            }

            for note_name, content in notes.items():
                note_path = os.path.join(self.vault_path, note_name)
                if not os.path.exists(note_path):
                    with open(note_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"  - 로컬 RAG 백업 메모 생성 완료: {note_name}")

    def build_or_update_db(self):
        """Vault 폴더의 md 메모들을 임베딩해 로컬 FAISS DB를 빌드 및 영구 저장"""
        if not os.path.exists(self.vault_path):
            print(f"[Error] 옵시디언 Vault 폴더가 없습니다: {self.vault_path}")
            return False
        if not self.embeddings:
            print("[RAG] 키워드 검색 모드에서는 벡터 DB 빌드를 생략합니다.")
            return False

        fingerprint = self._vault_fingerprint()
        if self._is_db_current(fingerprint):
            print("[RAG] 옵시디언 메모 변경 없음. 기존 벡터 DB를 재사용합니다.")
            return self.load_db()

        print(f"[RAG] 옵시디언 메모 임베딩 빌드 중: {self.vault_path}")

        try:
            # 1. md 파일 로더 설정
            loader = DirectoryLoader(
                self.vault_path,
                glob="**/*.md",
                loader_cls=TextLoader,
                loader_kwargs={'encoding': 'utf-8'}
            )
            documents = loader.load()
            if not documents:
                print("[RAG] 파싱 가능한 마크다운 파일이 존재하지 않습니다.")
                return False

            # 2. 텍스트 분할 (청크 크기 600)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
            chunks = text_splitter.split_documents(documents)

            # 3. 임베딩 계산 및 FAISS 저장
            self.vector_store = FAISS.from_documents(chunks, self.embeddings)
            self.vector_store.save_local(self.db_path)
            self._save_fingerprint(fingerprint)
            print(f"✅ RAG 로컬 벡터 DB 빌드/업데이트 성공 및 '{self.db_path}'에 저장 완료.")
            return True
        except Exception as e:
            print(f"[Error] RAG 로컬 벡터 DB 빌드 실패: {e}")
            return False

    def _fingerprint_path(self):
        return os.path.join(self.db_path, "vault_fingerprint.json")

    def _vault_fingerprint(self):
        entries = []
        for root, _, files in os.walk(self.vault_path):
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(root, name)
                try:
                    stat = os.stat(path)
                    entries.append({
                        "path": os.path.relpath(path, self.vault_path),
                        "mtime_ns": stat.st_mtime_ns,
                        "size": stat.st_size,
                    })
                except OSError:
                    continue
        return {
            "vault_path": os.path.abspath(self.vault_path),
            "files": sorted(entries, key=lambda item: item["path"]),
        }

    def _is_db_current(self, fingerprint):
        if not os.path.exists(os.path.join(self.db_path, "index.faiss")):
            return False
        try:
            with open(self._fingerprint_path(), "r", encoding="utf-8") as f:
                previous = json.load(f)
            return previous == fingerprint
        except Exception:
            return False

    def _save_fingerprint(self, fingerprint):
        os.makedirs(self.db_path, exist_ok=True)
        with open(self._fingerprint_path(), "w", encoding="utf-8") as f:
            json.dump(fingerprint, f, ensure_ascii=False, indent=2)

    def load_db(self):
        """로컬 FAISS DB 로드"""
        if not self.embeddings:
            return False
        if os.path.exists(self.db_path):
            try:
                self.vector_store = FAISS.load_local(
                    self.db_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True  # 로컬 가동 자격 부여
                )
                return True
            except Exception as e:
                print(f"[Warning] 로컬 DB 로드 실패: {e}")
        return False

    def retrieve_context(self, query, k=3):
        """특정 쿼리에 부합하는 옵시디언 메모 맥락 추출"""
        if not self.embeddings:
            return self._keyword_search(query, k=k)

        if not self.vector_store:
            if not self.load_db():
                # DB가 없거나 깨졌을 시 즉시 재생성 시도
                if not self.build_or_update_db():
                    print("[RAG] DB를 조회할 수 없어 RAG 맥락을 생략합니다.")
                    return ""

        try:
            docs = self.vector_store.similarity_search(query, k=k)
            context_parts = []
            for i, doc in enumerate(docs):
                source = os.path.basename(doc.metadata.get('source', 'unknown'))
                context_parts.append(f"[{source} 메모]:\n{doc.page_content}")
            return "\n\n".join(context_parts)
        except Exception as e:
            print(f"[Warning] 유사도 검색 중 오류 발생: {e}")
            return ""

    def _keyword_search(self, query, k=3):
        terms = {term for term in re.split(r"\s+", query.strip()) if term}
        scored = []
        for root, _, files in os.walk(self.vault_path):
            for name in files:
                if not name.endswith(".md"):
                    continue
                path = os.path.join(root, name)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    continue
                score = sum(content.count(term) for term in terms)
                if score:
                    scored.append((score, name, content[:1200]))

        scored.sort(key=lambda item: item[0], reverse=True)
        if not scored:
            return ""
        return "\n\n".join(f"[{name} 메모]:\n{content}" for _, name, content in scored[:k])
