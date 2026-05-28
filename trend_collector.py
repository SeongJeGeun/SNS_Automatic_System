"""Scaffold for future Instagram/Threads trend collection.

This module is intentionally passive. Importing it performs no API calls,
network access, file writes, scheduling, or publishing side effects.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class TrendSignal:
    """Normalized trend signal for future strategy inputs."""

    platform: str
    topic: str
    source: str
    observed_at: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrendCollectionResult:
    """Container for collected trend signals."""

    signals: List[TrendSignal]
    ok: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TrendCollector:
    """Placeholder collector for future social trend intake."""

    SUPPORTED_PLATFORMS = ("instagram", "threads")

    def collect(self, platforms: Optional[List[str]] = None) -> TrendCollectionResult:
        """Return an empty scaffold result without live API execution.

        TODO: Add authenticated Instagram trend collection behind an explicit call.
        TODO: Add Threads trend collection behind an explicit call.
        TODO: Persist normalized signals to a job-scoped artifact when integrated.
        """
        selected_platforms = platforms or list(self.SUPPORTED_PLATFORMS)
        unsupported = [
            platform
            for platform in selected_platforms
            if platform not in self.SUPPORTED_PLATFORMS
        ]
        if unsupported:
            return TrendCollectionResult(
                signals=[],
                ok=False,
                error=f"unsupported platforms: {', '.join(unsupported)}",
                metadata={"requested_platforms": selected_platforms},
            )

        return TrendCollectionResult(
            signals=[],
            ok=True,
            metadata={
                "requested_platforms": selected_platforms,
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scaffold_only": True,
            },
        )


def build_default_collector() -> TrendCollector:
    """Create the placeholder collector without side effects."""

    return TrendCollector()

