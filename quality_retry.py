import os


def run_until_pass(evaluate_once, regenerate, max_retries=None):
    """Run a quality gate with bounded retries.

    Returns True when the gate passes. Returns False after max_retries.
    The retry count is bounded to avoid infinite automation loops.
    """
    if max_retries is None:
        max_retries = int(os.getenv("MAX_QUALITY_RETRIES", "5"))

    attempt = 0
    while attempt <= max_retries:
        attempt += 1
        if evaluate_once():
            return True
        if attempt > max_retries:
            print(f"[Quality Retry] failed after {max_retries} retries")
            return False
        print(f"[Quality Retry] retry {attempt}/{max_retries}")
        regenerate()

    return False
