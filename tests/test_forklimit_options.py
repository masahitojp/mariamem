"""Input-boundary tests, not evidence of installed Fork admission yet."""
import math

import pytest

from mariamem._forklimit import MAX_FORKS, MAX_WAIT_SECONDS, capacity, wait_nanoseconds


class IntSubclass(int):
    pass


class FloatSubclass(float):
    pass


@pytest.mark.parametrize("value, expected", [(None, 0), (1, 1), (MAX_FORKS, MAX_FORKS)])
def test_capacity_boundaries(value, expected):
    assert capacity(value) == expected


@pytest.mark.parametrize("value", [0, -1, MAX_FORKS + 1, 2**100, 2**10000,
                                  True, False, 1.0, "1", IntSubclass(1), [], {}])
def test_invalid_capacity_is_local_value_error(value):
    with pytest.raises(ValueError, match="max_forks"):
        capacity(value)


@pytest.mark.parametrize("value, expected", [
    (None, None), (1, "1000000000ns"), (0.25, "250000000ns"),
    (1e-100, "1ns"), (math.nextafter(0.0, 1.0), "1ns"),
    (MAX_WAIT_SECONDS, "2147483647000000000ns"),
    (float(MAX_WAIT_SECONDS), "2147483647000000000ns"),
])
def test_wait_serialization(value, expected):
    assert wait_nanoseconds(value) == expected


@pytest.mark.parametrize("value", [0, -1, MAX_WAIT_SECONDS + 1,
                                  math.nextafter(float(MAX_WAIT_SECONDS), math.inf),
                                  2**100, 2**10000, math.nan, math.inf, -math.inf,
                                  True, False, "1", IntSubclass(1), FloatSubclass(1), [], {}])
def test_invalid_wait_is_local_value_error(value):
    with pytest.raises(ValueError, match="fork timeout"):
        wait_nanoseconds(value)


def test_fixture_wait_cannot_be_indefinite():
    with pytest.raises(ValueError, match="fork timeout"):
        wait_nanoseconds(None, allow_none=False)


def test_watchdog_margin_fits_host_duration():
    assert (MAX_WAIT_SECONDS + 25) * 1_000_000_000 < 2**63 - 1
