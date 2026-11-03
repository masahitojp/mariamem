"""Private, side-effect-free validation for the #53 capacity protocol.

Public entry points will validate before preparing, capturing, or sending. The
Go host owns automatic sizing; Python never derives a second independent cap.
"""
import math

MAX_FORKS = (1 << 31) - 1
MAX_WAIT_SECONDS = (1 << 31) - 1


def capacity(value):
    """Return the private Go representation (zero selects automatic sizing)."""
    if value is None:
        return 0
    if type(value) is not int or not 1 <= value <= MAX_FORKS:
        raise ValueError("max_forks must be None or a built-in integer between 1 and 2147483647")
    return value


def wait_nanoseconds(value, *, allow_none=True):
    """Return an integer-nanosecond duration without lossy float conversion.

    None is for direct Fork only; supplied fixtures require a finite wait.
    Subnanosecond positive values round up, and the maximum plus watchdog margin
    fits Go's signed 64-bit duration. Existing SDK timeouts are unaffected.
    """
    if value is None and allow_none:
        return None
    # Check arbitrary-precision int magnitude before math.isfinite/float/JSON.
    if (type(value) not in (int, float)
            or not 0 < value <= MAX_WAIT_SECONDS):
        raise ValueError("fork timeout must be positive and at most 2147483647 seconds")
    if type(value) is int:
        nanoseconds = value * 1_000_000_000
    else:
        # NaN/inf are already rejected by the range predicate. Use the exact
        # float ratio so the upper endpoint never overflows through rounding.
        if not math.isfinite(value):
            raise ValueError("fork timeout must be finite")
        numerator, denominator = value.as_integer_ratio()
        nanoseconds = (numerator * 1_000_000_000 + denominator - 1) // denominator
    return f"{nanoseconds}ns"
