"""Filesystem-only reader for Obsidian markdown context.

This module has no Obsidian app, plugin, API, network, or import-time file I/O
dependency. Files are read only when methods are called.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ObsidianNote:
    """Small note descriptor for future context retrieval."""

    path: str
    title: str
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ObsidianSnippet:
    """Short context snippet from one markdown note."""

    path: str
    title: str
    text: str


class ObsidianContextReader:
    """Read markdown context from a local Obsidian vault path."""

    def __init__(self, vault_path: str) -> None:
        self.vault_path = Path(vault_path).expanduser()

    def list_markdown_files(self, limit: int = 50) -> List[ObsidianNote]:
        """Return candidate markdown files without ranking.

        TODO: Add note ranking by recency, links, tags, and query relevance.
        TODO: Add ignore patterns for private or non-content notes.
        """
        if not self.vault_path.exists() or not self.vault_path.is_dir():
            return []

        notes = []
        for path in sorted(self.vault_path.rglob("*.md")):
            if len(notes) >= limit:
                break
            notes.append(
                ObsidianNote(
                    path=str(path),
                    title=path.stem,
                    metadata={"relative_path": str(path.relative_to(self.vault_path))},
                )
            )
        return notes

    def read_markdown_file(self, file_path: str, max_chars: int = 4000) -> str:
        """Read one markdown file safely, returning an empty string on failure."""
        path = Path(file_path).expanduser()
        try:
            if not path.exists() or not path.is_file() or path.suffix.lower() != ".md":
                return ""
            return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
        except Exception:
            return ""

    def get_context_snippets(
        self,
        query: Optional[str] = None,
        *,
        limit: int = 5,
        max_chars_per_note: int = 700,
    ) -> List[ObsidianSnippet]:
        """Return short snippets from candidate notes.

        If query is provided, this scaffold keeps notes containing the query
        first. It does not perform semantic retrieval.
        """
        notes = self.list_markdown_files(limit=100)
        snippets = []
        normalized_query = (query or "").strip().lower()

        for note in notes:
            text = self.read_markdown_file(note.path, max_chars=max_chars_per_note)
            if not text:
                continue
            if normalized_query and normalized_query not in text.lower() and normalized_query not in note.title.lower():
                continue
            snippets.append(ObsidianSnippet(path=note.path, title=note.title, text=text))
            if len(snippets) >= limit:
                break

        if snippets or normalized_query:
            return snippets

        for note in notes[:limit]:
            text = self.read_markdown_file(note.path, max_chars=max_chars_per_note)
            if text:
                snippets.append(ObsidianSnippet(path=note.path, title=note.title, text=text))
        return snippets


def build_obsidian_context_reader(vault_path: str) -> ObsidianContextReader:
    """Create a filesystem-only Obsidian context reader without side effects."""

    return ObsidianContextReader(vault_path)
