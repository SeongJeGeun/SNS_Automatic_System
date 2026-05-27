"""Legacy entrypoint.

The maintained scheduler/orchestrator is main_orchestrator.py. This wrapper
keeps old commands working without carrying a second, divergent pipeline.
"""

from main_orchestrator import main


if __name__ == "__main__":
    main()
