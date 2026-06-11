"""SlidingWindowLimiter: deterministic tests with injected timestamps."""
from app.ratelimit import SlidingWindowLimiter


def test_allows_up_to_limit_then_blocks():
    lim = SlidingWindowLimiter(limit=3, window_seconds=60)
    assert all(lim.allow("ip1", now=t) for t in (0.0, 1.0, 2.0))
    assert lim.allow("ip1", now=3.0) is False


def test_window_slides_and_recovers():
    lim = SlidingWindowLimiter(limit=2, window_seconds=10)
    assert lim.allow("ip1", now=0.0)
    assert lim.allow("ip1", now=1.0)
    assert lim.allow("ip1", now=5.0) is False
    # first hit (t=0) leaves the window at t>10
    assert lim.allow("ip1", now=10.5) is True


def test_keys_are_independent():
    lim = SlidingWindowLimiter(limit=1, window_seconds=60)
    assert lim.allow("ip1", now=0.0)
    assert lim.allow("ip2", now=0.0)
    assert lim.allow("ip1", now=1.0) is False
    assert lim.allow("ip2", now=1.0) is False
