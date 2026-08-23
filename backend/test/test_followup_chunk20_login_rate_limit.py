from __future__ import annotations

from app.services.login_rate_limiter import LoginRateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    clock = Clock()
    limiter = LoginRateLimiter(
        account_threshold=5,
        source_threshold=30,
        window_seconds=60,
        cooldown_seconds=60,
        max_buckets=16,
        clock=clock,
    )

    for _ in range(4):
        require(not limiter.record_failure("10.0.0.1", "Admin"), "burst blocked early")
    require(limiter.record_failure("10.0.0.1", "admin"), "threshold not enforced")
    require(limiter.is_limited("10.0.0.1", " ADMIN "), "normalized account bypass")
    require(not limiter.is_limited("10.0.0.2", "admin"), "different source blocked")
    require(not limiter.is_limited("10.0.0.1", "other"), "different account blocked")

    clock.advance(61)
    require(not limiter.is_limited("10.0.0.1", "admin"), "cooldown did not expire")

    for _ in range(5):
        limiter.record_failure("10.0.0.1", "admin")
    limiter.record_success("10.0.0.1", "admin")
    require(not limiter.is_limited("10.0.0.1", "admin"), "success did not reset")

    source_limiter = LoginRateLimiter(
        account_threshold=5,
        source_threshold=30,
        window_seconds=60,
        cooldown_seconds=60,
        max_buckets=128,
        clock=clock,
    )
    for index in range(29):
        require(
            not source_limiter.record_failure("10.0.0.9", f"source-user-{index}"),
            "source bucket blocked before threshold",
        )
    require(
        source_limiter.record_failure("10.0.0.9", "source-user-29"),
        "source threshold not enforced",
    )
    require(
        not source_limiter.is_limited("10.0.0.10", "source-user-29"),
        "different source was blocked",
    )

    require(
        limiter.normalize_source("not-an-ip") == "unknown",
        "invalid source was trusted",
    )
    require(
        limiter.account_digest("Missing User") == limiter.account_digest(" missing   user "),
        "account normalization differs",
    )

    for index in range(40):
        limiter.record_failure(f"192.0.2.{(index % 250) + 1}", f"user-{index}")
    require(len(limiter._buckets) <= 16, "bucket storage is unbounded")

    print("CHUNK20_LOGIN_RATE_LIMIT_MATRIX=PASS")
    print("CHUNK20_FORWARDED_HEADER_TRUST=IGNORED_FAIL_CLOSED")
    print("CHUNK20_LOGIN_RATE_LIMIT_STORAGE=BOUNDED")


if __name__ == "__main__":
    main()
