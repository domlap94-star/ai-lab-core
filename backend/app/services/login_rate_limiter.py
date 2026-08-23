from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
import hashlib
import ipaddress
from threading import RLock
import time
from typing import Callable


@dataclass
class _AttemptBucket:
    failures: deque[float] = field(default_factory=deque)
    blocked_until: float = 0.0
    last_seen: float = 0.0


class LoginRateLimiter:
    """Bounded, process-local failed-login throttling.

    Client attribution intentionally uses only the ASGI socket peer. Forwarded
    headers are not trusted because the backend also has a direct loopback
    listener and there is no authenticated proxy-header contract yet.
    """

    def __init__(
        self,
        *,
        account_threshold: int = 5,
        source_threshold: int = 30,
        window_seconds: float = 60.0,
        cooldown_seconds: float = 60.0,
        max_buckets: int = 4096,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.account_threshold = account_threshold
        self.source_threshold = source_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: OrderedDict[str, _AttemptBucket] = OrderedDict()
        self._lock = RLock()

    @staticmethod
    def normalize_source(source: str | None) -> str:
        candidate = (source or "unknown").strip()
        try:
            return ipaddress.ip_address(candidate).compressed
        except ValueError:
            return "unknown"

    @staticmethod
    def account_digest(username: str) -> str:
        normalized = " ".join(username.strip().casefold().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _keys(self, source: str, username: str) -> tuple[str, str]:
        normalized_source = self.normalize_source(source)
        account = self.account_digest(username)
        return (
            f"source:{normalized_source}",
            f"account:{normalized_source}:{account}",
        )

    def _prune_bucket(self, bucket: _AttemptBucket, now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket.failures and bucket.failures[0] <= cutoff:
            bucket.failures.popleft()
        if bucket.blocked_until <= now:
            bucket.blocked_until = 0.0

    def _get_bucket(self, key: str, now: float) -> _AttemptBucket:
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _AttemptBucket()
            self._buckets[key] = bucket
        else:
            self._buckets.move_to_end(key)
        bucket.last_seen = now
        return bucket

    def _evict(self, now: float) -> None:
        expiry = now - max(self.window_seconds, self.cooldown_seconds) * 2
        stale = [
            key
            for key, bucket in self._buckets.items()
            if bucket.last_seen <= expiry and bucket.blocked_until <= now
        ]
        for key in stale:
            self._buckets.pop(key, None)
        while len(self._buckets) > self.max_buckets:
            self._buckets.popitem(last=False)

    def is_limited(self, source: str | None, username: str) -> bool:
        now = self._clock()
        source_key, account_key = self._keys(source or "unknown", username)
        with self._lock:
            for key in (source_key, account_key):
                bucket = self._buckets.get(key)
                if bucket is None:
                    continue
                self._prune_bucket(bucket, now)
                if bucket.blocked_until > now:
                    return True
            return False

    def record_failure(self, source: str | None, username: str) -> bool:
        now = self._clock()
        source_key, account_key = self._keys(source or "unknown", username)
        with self._lock:
            limited = False
            for key, threshold in (
                (source_key, self.source_threshold),
                (account_key, self.account_threshold),
            ):
                bucket = self._get_bucket(key, now)
                self._prune_bucket(bucket, now)
                bucket.failures.append(now)
                if len(bucket.failures) >= threshold:
                    bucket.blocked_until = max(
                        bucket.blocked_until,
                        now + self.cooldown_seconds,
                    )
                    limited = True
            self._evict(now)
            return limited

    def record_success(self, source: str | None, username: str) -> None:
        source_key, account_key = self._keys(source or "unknown", username)
        with self._lock:
            self._buckets.pop(account_key, None)
            source_bucket = self._buckets.get(source_key)
            if source_bucket is not None and source_bucket.failures:
                source_bucket.failures.popleft()
                source_bucket.blocked_until = 0.0

    def reset_for_tests(self) -> None:
        with self._lock:
            self._buckets.clear()


login_rate_limiter = LoginRateLimiter()
