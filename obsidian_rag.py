import json
import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

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
        self.chunks = []
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
        if self.load_db(fingerprint):
            return True

        try:
            import numpy as np
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)
            chunks = []
            for entry in fingerprint["files"]:
                path = Path(self.vault_path, entry["path"])
                if any(part.startswith(".") for part in Path(entry["path"]).parts):
                    continue
                chunks.extend((path.name, text) for text in splitter.split_text(path.read_text(encoding="utf-8")))
            if not chunks:
                return False

            vectors = np.asarray(self.embeddings.embed_documents([text for _, text in chunks]), dtype=np.float32)
            self._set_index(chunks, vectors)
            os.makedirs(self.db_path, exist_ok=True)
            # Replace the whole snapshot together, including its source fingerprint.
            with NamedTemporaryFile(dir=self.db_path, delete=False) as cache:
                try:
                    metadata = json.dumps({"fingerprint": fingerprint, "chunks": chunks}, ensure_ascii=False)
                    np.savez(cache, metadata=metadata, vectors=vectors)
                    cache.close()
                    os.replace(cache.name, self._cache_path())
                finally:
                    Path(cache.name).unlink(missing_ok=True)
            return True
        except Exception as exc:
            print(f"[RAG] 로컬 색인 생성 실패: {exc}")
            return False

    def _cache_path(self):
        return os.path.join(self.db_path, "embeddings.npz")

    def _set_index(self, chunks, vectors):
        import faiss

        if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or vectors.shape[1] == 0:
            raise ValueError("Invalid embedding dimensions")
        index = faiss.IndexFlatL2(vectors.shape[1])
        index.add(vectors)
        self.vector_store = index
        self.chunks = chunks

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
            "model": _EMBEDDING_MODEL,
            "vault_path": os.path.abspath(self.vault_path),
            "files": sorted(entries, key=lambda item: item["path"]),
        }

    def load_db(self, fingerprint=None):
        """Load plain vectors and document text. Legacy indexes rebuild from vault notes."""
        if not self.embeddings or not os.path.isfile(self._cache_path()):
            return False
        import numpy as np
        try:
            with np.load(self._cache_path(), allow_pickle=False) as cache:
                metadata = json.loads(cache["metadata"].item())
                cached = metadata["fingerprint"]
                if cached["vault_path"] != os.path.abspath(self.vault_path) or cached["model"] != _EMBEDDING_MODEL:
                    return False
                if fingerprint is not None and cached != fingerprint:
                    return False
                self._set_index(metadata["chunks"], cache["vectors"])
            return True
        except Exception as exc:
            print(f"[RAG] 로컬 색인 재생성 필요: {exc}")
            return False

    def retrieve_context(self, query, k=3):
        """특정 쿼리에 부합하는 옵시디언 메모 맥락 추출"""
        if not self.embeddings:
            return self._keyword_search(query, k=k)

        if k < 1:
            return ""
        if self.vector_store is None and not self.load_db():
            if not self.build_or_update_db():
                return self._keyword_search(query, k=k)

        try:
            import numpy as np

            vector = np.asarray([self.embeddings.embed_query(query)], dtype=np.float32)
            _, indices = self.vector_store.search(vector, min(k, len(self.chunks)))
            return "\n\n".join(f"[{self.chunks[i][0]} 메모]:\n{self.chunks[i][1]}"
                               for i in indices[0] if i >= 0)
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
