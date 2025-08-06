# app/utils/logging_utils.py
import time

def measure_time(start: float) -> float:
    return round(time.time() - start, 3)
