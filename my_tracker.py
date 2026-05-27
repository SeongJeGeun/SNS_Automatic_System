"""Backward-compatible entrypoint for the Instagram metrics syncer.

Use update_insights.py for new automation wiring.
"""

from update_insights import main


if __name__ == "__main__":
    main()
