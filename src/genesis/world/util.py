def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp a value into [lo, hi] (defaults to the 0–100 need range)."""
    return max(lo, min(hi, v))
