"""Legacy entrypoint.

The maintained scheduler/orchestrator is main_orchestrator.py. This wrapper
keeps old commands working without carrying a second, divergent pipeline.
"""

from main_orchestrator import main
from optimal_timing import calculate_optimal_timing, get_recommended_sleep_seconds


if __name__ == "__main__":
    calculate_optimal_timing()
    main()
