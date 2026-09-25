import datetime as dt

from scraper.poller import _backoff_active
from scraper.settings import settings


class _FakeSource:
    def __init__(self, consecutive_errors: int, last_polled_at, poll_interval_sec: int = 900):
        self.consecutive_errors = consecutive_errors
        self.last_polled_at = last_polled_at
        self.poll_interval_sec = poll_interval_sec


def test_no_backoff_below_threshold():
    source = _FakeSource(
        consecutive_errors=settings.consecutive_errors_backoff_threshold,
        last_polled_at=dt.datetime.now(dt.UTC),
    )
    assert _backoff_active(source) is False


def test_no_backoff_without_prior_poll():
    source = _FakeSource(
        consecutive_errors=settings.consecutive_errors_backoff_threshold + 5,
        last_polled_at=None,
    )
    assert _backoff_active(source) is False


def test_backoff_active_right_after_failure_past_threshold():
    source = _FakeSource(
        consecutive_errors=settings.consecutive_errors_backoff_threshold + 1,
        last_polled_at=dt.datetime.now(dt.UTC),
    )
    assert _backoff_active(source) is True


def test_backoff_clears_once_enough_time_has_passed():
    long_ago = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    source = _FakeSource(
        consecutive_errors=settings.consecutive_errors_backoff_threshold + 1,
        last_polled_at=long_ago,
    )
    assert _backoff_active(source) is False


def test_backoff_multiplier_is_capped():
    # Even with a huge error streak, the multiplier must not exceed
    # consecutive_errors_backoff_max_multiplier -- otherwise a source that
    # failed for a long time could end up effectively disabled forever.
    poll_interval_sec = 900
    max_backoff_seconds = poll_interval_sec * settings.consecutive_errors_backoff_max_multiplier
    last_polled_at = dt.datetime.now(dt.UTC) - dt.timedelta(
        seconds=max_backoff_seconds + 1
    )
    source = _FakeSource(
        consecutive_errors=settings.consecutive_errors_backoff_threshold + 1000,
        last_polled_at=last_polled_at,
        poll_interval_sec=poll_interval_sec,
    )
    assert _backoff_active(source) is False
