from __future__ import annotations

import asyncio
import contextvars
import threading
from collections import deque

import pytest

import app.services.local_model_resource_coordinator as resource_module
from app.core.config import settings
from app.services.local_model_resource_coordinator import (
    EMERGENCY_FLOOR_BYTES,
    GIB,
    LocalModelEmergencyAbort,
    LocalModelResourceCoordinator,
    LocalModelResourceUnavailable,
    LocalResourceSnapshot,
    ResidentModel,
)


def snapshot(
    *,
    windows_available: int = 12 * GIB,
    wsl_available: int = 12 * GIB,
    swap_used: int = 0,
    models: tuple[ResidentModel, ...] = (),
) -> LocalResourceSnapshot:
    return LocalResourceSnapshot(
        windows_total_bytes=32 * GIB,
        windows_available_bytes=windows_available,
        wsl_total_bytes=16 * GIB,
        wsl_available_bytes=wsl_available,
        wsl_swap_total_bytes=8 * GIB,
        wsl_swap_used_bytes=swap_used,
        resident_models=models,
    )


class FakeProvider:
    def __init__(self, snapshots: list[LocalResourceSnapshot]) -> None:
        self.snapshots = deque(snapshots)
        self.current = snapshots[-1]
        self.unloaded: list[str] = []

    async def snapshot(self) -> LocalResourceSnapshot:
        if self.snapshots:
            self.current = self.snapshots.popleft()
        return self.current

    async def unload(self, model: str) -> None:
        self.unloaded.append(model)
        self.current = snapshot(
            windows_available=self.current.windows_available_bytes,
            wsl_available=self.current.wsl_available_bytes,
            swap_used=self.current.wsl_swap_used_bytes,
            models=tuple(row for row in self.current.resident_models if row.name != model),
        )

    def resident_models_sync(self) -> tuple[ResidentModel, ...]:
        return self.current.resident_models


class FailingProvider(FakeProvider):
    async def snapshot(self) -> LocalResourceSnapshot:
        raise LocalModelResourceUnavailable("LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE")


@pytest.mark.asyncio
async def test_generator_admission_preserves_projected_four_gib_reserve() -> None:
    provider = FakeProvider([snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.2):
        assert coordinator.state()["heavy_active"] is True

    assert provider.unloaded == ["qwen3.5:9b"]
    assert coordinator.state() == {
        "heavy_active": False,
        "heavy_waiters": 0,
        "embedding_active": 0,
    }


@pytest.mark.asyncio
async def test_generator_fails_closed_when_projected_reserve_is_too_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource_module, "RESOURCE_RETRY_SECONDS", 0.01)
    provider = FakeProvider([snapshot(windows_available=9 * GIB)])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    with pytest.raises(LocalModelResourceUnavailable, match="LOCAL_RESOURCE_RESERVE_WAIT"):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.03):
            pytest.fail("unsafe generator admission")

    assert provider.unloaded == []
    assert coordinator.state()["heavy_active"] is False


@pytest.mark.asyncio
async def test_generator_fails_closed_when_projected_wsl_reserve_is_too_low(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource_module, "RESOURCE_RETRY_SECONDS", 0.01)
    provider = FakeProvider([snapshot(wsl_available=9 * GIB)])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    with pytest.raises(LocalModelResourceUnavailable, match="LOCAL_RESOURCE_RESERVE_WAIT"):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.03):
            pytest.fail("unsafe generator admission")

    assert provider.unloaded == []
    assert coordinator.state()["heavy_active"] is False


@pytest.mark.asyncio
async def test_embedding_is_unloaded_before_generator_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource_module, "MONITOR_SECONDS", 0.01)
    embedding = ResidentModel(settings.embedding_model, 1, 0)
    provider = FakeProvider([snapshot(models=(embedding,)), snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.2):
        pass

    assert provider.unloaded == [settings.embedding_model, "qwen3.5:9b"]


@pytest.mark.asyncio
async def test_emergency_floor_cancels_owner_and_unloads_owned_qwen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource_module, "MONITOR_SECONDS", 0.01)
    provider = FakeProvider([
        snapshot(),
        snapshot(windows_available=EMERGENCY_FLOOR_BYTES - 1),
    ])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    with pytest.raises(LocalModelEmergencyAbort, match="LOCAL_RESOURCE_WINDOWS_EMERGENCY"):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.2):
            await asyncio.sleep(1)

    assert provider.unloaded == ["qwen3.5:9b"]
    assert coordinator.state()["heavy_active"] is False


@pytest.mark.asyncio
async def test_wsl_emergency_floor_cancels_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resource_module, "MONITOR_SECONDS", 0.01)
    provider = FakeProvider([
        snapshot(),
        snapshot(wsl_available=EMERGENCY_FLOOR_BYTES - 1),
    ])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    with pytest.raises(LocalModelEmergencyAbort, match="LOCAL_RESOURCE_WSL_EMERGENCY"):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0.2):
            await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_supervisor_telemetry_unavailable_fails_closed() -> None:
    coordinator = LocalModelResourceCoordinator(
        provider=FailingProvider([snapshot()])
    )

    with pytest.raises(
        LocalModelResourceUnavailable, match="LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
    ):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0):
            pytest.fail("generator admitted without telemetry")


@pytest.mark.asyncio
async def test_heavy_generators_are_serialized() -> None:
    provider = FakeProvider([snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
            order.append("first-enter")
            first_entered.set()
            await release_first.wait()
            order.append("first-exit")

    async def second() -> None:
        await first_entered.wait()
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
            order.append("second-enter")

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())
    await first_entered.wait()
    await asyncio.sleep(0.05)
    assert "second-enter" not in order
    release_first.set()
    await asyncio.gather(first_task, second_task)

    assert order == ["first-enter", "first-exit", "second-enter"]


@pytest.mark.asyncio
async def test_embedding_request_waits_while_generator_is_active() -> None:
    provider = FakeProvider([snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)
    embedding_entered = threading.Event()

    def embed() -> None:
        with coordinator.embedding_session(wait_timeout=1):
            embedding_entered.set()

    async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
        task = asyncio.get_running_loop().run_in_executor(None, embed)
        await asyncio.sleep(0.05)
        assert not embedding_entered.is_set()
    await task
    assert embedding_entered.is_set()


@pytest.mark.asyncio
async def test_cancel_while_waiting_removes_heavy_waiter() -> None:
    provider = FakeProvider([snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
        async def wait_for_generator() -> None:
            async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
                pytest.fail("second generator entered")

        waiting = asyncio.create_task(wait_for_generator(), context=contextvars.Context())
        await asyncio.sleep(0.05)
        assert coordinator.state()["heavy_waiters"] == 1
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert coordinator.state()["heavy_waiters"] == 0


@pytest.mark.asyncio
async def test_cancel_while_generating_releases_and_unloads() -> None:
    provider = FakeProvider([snapshot()])
    coordinator = LocalModelResourceCoordinator(provider=provider)
    entered = asyncio.Event()

    async def generate() -> None:
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=1):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(generate())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert provider.unloaded == ["qwen3.5:9b"]
    assert coordinator.state()["heavy_active"] is False


@pytest.mark.asyncio
async def test_external_resident_model_is_not_force_unloaded() -> None:
    external = ResidentModel("other-model:latest", 1, 0)
    provider = FakeProvider([snapshot(models=(external,))])
    coordinator = LocalModelResourceCoordinator(provider=provider)

    with pytest.raises(LocalModelResourceUnavailable):
        async with coordinator.generator_session("qwen3.5:9b", wait_timeout=0):
            pytest.fail("unsafe generator admission")

    assert "other-model:latest" not in provider.unloaded
