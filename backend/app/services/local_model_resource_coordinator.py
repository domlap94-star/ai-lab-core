from __future__ import annotations

import asyncio
import contextvars
import inspect
import threading
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.services.supervisor_resource_client import (
    SupervisorResourceClient,
    SupervisorResourceTelemetryUnavailable,
)


GIB = 1024**3
MIB = 1024**2

WINDOWS_TARGET_RESERVE_BYTES = 4 * GIB
WSL_TARGET_RESERVE_BYTES = 4 * GIB
EMERGENCY_FLOOR_BYTES = 3 * GIB
MAX_SWAP_GROWTH_BYTES = 256 * MIB

# The diagnostic observed an approximately 6.34-GiB Windows-available drop
# while qwen3.5:9b @4096 loaded next to the embedding model.  Admission uses a
# larger 6.60-GiB increment and independently preserves the four-GiB reserve.
QWEN9_WINDOWS_INCREMENT_BYTES = int(6.60 * GIB)
QWEN9_WSL_INCREMENT_BYTES = int(6.25 * GIB)
CONSERVATIVE_GENERATOR_WINDOWS_INCREMENT_BYTES = QWEN9_WINDOWS_INCREMENT_BYTES
CONSERVATIVE_GENERATOR_WSL_INCREMENT_BYTES = QWEN9_WSL_INCREMENT_BYTES

MONITOR_SECONDS = 2.0
MAX_CONSECUTIVE_MONITOR_FAILURES = 3
RESOURCE_RETRY_SECONDS = 5.0
LEGACY_RESOURCE_WAIT_SECONDS = 10.0


class LocalModelResourceError(RuntimeError):
    pass


class LocalModelResourceUnavailable(LocalModelResourceError, OSError):
    pass


class LocalModelResourceBusy(LocalModelResourceUnavailable):
    pass


class LocalModelEmergencyAbort(LocalModelResourceUnavailable):
    pass


@dataclass(frozen=True)
class ResidentModel:
    name: str
    size_bytes: int
    size_vram_bytes: int


@dataclass(frozen=True)
class LocalResourceSnapshot:
    windows_total_bytes: int
    windows_available_bytes: int
    wsl_total_bytes: int
    wsl_available_bytes: int
    wsl_swap_total_bytes: int
    wsl_swap_used_bytes: int
    resident_models: tuple[ResidentModel, ...]


@dataclass
class LocalModelLease:
    lease_id: str
    model: str
    admitted_snapshot: LocalResourceSnapshot
    unload_on_release: bool
    emergency_reason: str | None = None
    model_unloaded: bool = False


ResourceCallback = Callable[[str], Awaitable[None] | None]


def _parse_meminfo(path: Path = Path("/proc/meminfo")) -> tuple[int, int, int, int]:
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        values[key] = int(parts[0]) * 1024
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    if total <= 0 or available < 0 or available > total:
        raise LocalModelResourceUnavailable("LOCAL_WSL_TELEMETRY_UNAVAILABLE")
    return total, available, swap_total, max(0, swap_total - swap_free)


class LocalModelTelemetryProvider:
    """Combine private Windows telemetry, WSL `/proc`, and Ollama residency."""

    def __init__(self) -> None:
        self.supervisor = SupervisorResourceClient()
        self.ollama_url = settings.ollama_url.rstrip("/")

    @staticmethod
    def _models(payload: dict[str, Any]) -> tuple[ResidentModel, ...]:
        rows: list[ResidentModel] = []
        for item in payload.get("models") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("model") or "").strip()
            if not name:
                continue
            rows.append(ResidentModel(
                name=name,
                size_bytes=max(0, int(item.get("size") or 0)),
                size_vram_bytes=max(0, int(item.get("size_vram") or 0)),
            ))
        return tuple(rows)

    async def resident_models(self) -> tuple[ResidentModel, ...]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.ollama_url}/api/ps")
                response.raise_for_status()
                return self._models(response.json())
        except Exception as error:
            raise LocalModelResourceUnavailable("LOCAL_OLLAMA_RESIDENCY_UNAVAILABLE") from error

    def resident_models_sync(self) -> tuple[ResidentModel, ...]:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0)) as client:
                response = client.get(f"{self.ollama_url}/api/ps")
                response.raise_for_status()
                return self._models(response.json())
        except Exception as error:
            raise LocalModelResourceUnavailable("LOCAL_OLLAMA_RESIDENCY_UNAVAILABLE") from error

    async def snapshot(self) -> LocalResourceSnapshot:
        try:
            windows, meminfo, models = await asyncio.gather(
                asyncio.to_thread(self.supervisor.snapshot),
                asyncio.to_thread(_parse_meminfo),
                self.resident_models(),
            )
        except SupervisorResourceTelemetryUnavailable as error:
            raise LocalModelResourceUnavailable(
                "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
            ) from error
        return LocalResourceSnapshot(
            windows_total_bytes=windows.physical_total_bytes,
            windows_available_bytes=windows.physical_available_bytes,
            wsl_total_bytes=meminfo[0],
            wsl_available_bytes=meminfo[1],
            wsl_swap_total_bytes=meminfo[2],
            wsl_swap_used_bytes=meminfo[3],
            resident_models=models,
        )

    async def resource_snapshot(self) -> LocalResourceSnapshot:
        """Read the safety envelope without querying the busy generator API.

        Residency is required during admission, but it is not an input to the
        mid-run Windows/WSL emergency floors.  Ollama's `/api/ps` may be slow
        while CPU inference is active, so coupling it to the memory monitor can
        falsely abort a healthy owned generation.
        """
        try:
            windows, meminfo = await asyncio.gather(
                asyncio.to_thread(self.supervisor.snapshot),
                asyncio.to_thread(_parse_meminfo),
            )
        except SupervisorResourceTelemetryUnavailable as error:
            raise LocalModelResourceUnavailable(
                "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
            ) from error
        return LocalResourceSnapshot(
            windows_total_bytes=windows.physical_total_bytes,
            windows_available_bytes=windows.physical_available_bytes,
            wsl_total_bytes=meminfo[0],
            wsl_available_bytes=meminfo[1],
            wsl_swap_total_bytes=meminfo[2],
            wsl_swap_used_bytes=meminfo[3],
            resident_models=(),
        )

    async def unload(self, model: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": "",
                        "stream": False,
                        "keep_alive": 0,
                    },
                )
                response.raise_for_status()
        except Exception as error:
            raise LocalModelResourceUnavailable("LOCAL_MODEL_UNLOAD_FAILED") from error


_ACTIVE_LOCAL_MODEL_LEASE: contextvars.ContextVar[LocalModelLease | None] = (
    contextvars.ContextVar("active_next_stabil_local_model_lease", default=None)
)


class LocalModelResourceCoordinator:
    """Process-global arbitration for every NEXT Stabil-owned Ollama call.

    The production backend has one Uvicorn worker.  A threading condition is
    nevertheless required because embedding calls are synchronous and execute
    both in FastAPI's worker pool and in backend dispatch threads.
    """

    def __init__(self, provider: LocalModelTelemetryProvider | None = None) -> None:
        self.provider = provider or LocalModelTelemetryProvider()
        self._condition = threading.Condition()
        self._heavy_queue: deque[str] = deque()
        self._active_heavy_id: str | None = None
        self._active_embeddings = 0

    @staticmethod
    async def _callback(callback: ResourceCallback | None, value: str) -> None:
        if callback is None:
            return
        result = callback(value)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _deadline(wait_timeout: float | None) -> float | None:
        return None if wait_timeout is None else time.monotonic() + max(0.0, wait_timeout)

    @staticmethod
    def _timed_out(deadline: float | None) -> bool:
        return deadline is not None and time.monotonic() >= deadline

    async def _claim_heavy(
        self,
        lease_id: str,
        *,
        deadline: float | None,
        on_wait: ResourceCallback | None,
    ) -> None:
        with self._condition:
            self._heavy_queue.append(lease_id)
        notified = False
        try:
            while True:
                with self._condition:
                    first = bool(self._heavy_queue) and self._heavy_queue[0] == lease_id
                    if first and self._active_heavy_id is None and self._active_embeddings == 0:
                        self._heavy_queue.popleft()
                        self._active_heavy_id = lease_id
                        self._condition.notify_all()
                        return
                if not notified:
                    await self._callback(on_wait, "LOCAL_MODEL_BUSY")
                    notified = True
                if self._timed_out(deadline):
                    raise LocalModelResourceBusy("LOCAL_MODEL_RESOURCE_BUSY")
                await asyncio.sleep(0.1)
        finally:
            with self._condition:
                if self._active_heavy_id != lease_id:
                    try:
                        self._heavy_queue.remove(lease_id)
                    except ValueError:
                        pass
                    self._condition.notify_all()

    def _release_heavy(self, lease_id: str) -> None:
        with self._condition:
            if self._active_heavy_id == lease_id:
                self._active_heavy_id = None
            self._condition.notify_all()

    @staticmethod
    def _resident(snapshot: LocalResourceSnapshot, model: str) -> bool:
        return any(item.name == model for item in snapshot.resident_models)

    @staticmethod
    def _projected_reserve(
        snapshot: LocalResourceSnapshot, model: str
    ) -> tuple[int, int]:
        already_resident = LocalModelResourceCoordinator._resident(snapshot, model)
        windows_increment = 0 if already_resident else (
            QWEN9_WINDOWS_INCREMENT_BYTES
            if model == "qwen3.5:9b"
            else CONSERVATIVE_GENERATOR_WINDOWS_INCREMENT_BYTES
        )
        wsl_increment = 0 if already_resident else (
            QWEN9_WSL_INCREMENT_BYTES
            if model == "qwen3.5:9b"
            else CONSERVATIVE_GENERATOR_WSL_INCREMENT_BYTES
        )
        return (
            snapshot.windows_available_bytes - windows_increment,
            snapshot.wsl_available_bytes - wsl_increment,
        )

    async def _admit(
        self,
        model: str,
        *,
        deadline: float | None,
        on_wait: ResourceCallback | None,
    ) -> tuple[LocalResourceSnapshot, bool]:
        last_reason: str | None = None
        while True:
            try:
                snapshot = await self.provider.snapshot()
            except LocalModelResourceUnavailable as error:
                reason = str(error) or "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
                if reason != last_reason:
                    await self._callback(on_wait, reason)
                    last_reason = reason
                if self._timed_out(deadline):
                    raise
                await asyncio.sleep(RESOURCE_RETRY_SECONDS)
                continue

            embedding_resident = self._resident(snapshot, settings.embedding_model)
            if embedding_resident:
                try:
                    await self.provider.unload(settings.embedding_model)
                except LocalModelResourceUnavailable as error:
                    if self._timed_out(deadline):
                        raise
                    reason = str(error)
                    if reason != last_reason:
                        await self._callback(on_wait, reason)
                        last_reason = reason
                    await asyncio.sleep(RESOURCE_RETRY_SECONDS)
                    continue
                await self._callback(on_wait, "LOCAL_EMBEDDING_UNLOAD_RECOVERY")
                await asyncio.sleep(MONITOR_SECONDS)
                continue

            # A generator already resident before NEXT Stabil acquires its
            # lease has unknown ownership (for example Open WebUI).  Do not
            # overlap it and never unload it.  The request remains queued until
            # that external residency naturally expires.
            external_generators = tuple(
                item for item in snapshot.resident_models
                if item.name != settings.embedding_model
            )
            if external_generators:
                reason = "LOCAL_EXTERNAL_GENERATOR_RESIDENT"
                if reason != last_reason:
                    await self._callback(on_wait, reason)
                    last_reason = reason
                if self._timed_out(deadline):
                    raise LocalModelResourceUnavailable(reason)
                await asyncio.sleep(RESOURCE_RETRY_SECONDS)
                continue

            windows_projected, wsl_projected = self._projected_reserve(snapshot, model)
            if (
                snapshot.windows_available_bytes >= EMERGENCY_FLOOR_BYTES
                and snapshot.wsl_available_bytes >= EMERGENCY_FLOOR_BYTES
                and windows_projected >= WINDOWS_TARGET_RESERVE_BYTES
                and wsl_projected >= WSL_TARGET_RESERVE_BYTES
            ):
                return snapshot, self._resident(snapshot, model)

            reason = "LOCAL_RESOURCE_RESERVE_WAIT"
            if reason != last_reason:
                await self._callback(on_wait, reason)
                last_reason = reason
            if self._timed_out(deadline):
                raise LocalModelResourceUnavailable(reason)
            await asyncio.sleep(RESOURCE_RETRY_SECONDS)

    async def _monitor(
        self,
        owner_task: asyncio.Task[Any],
        lease: LocalModelLease,
    ) -> None:
        baseline_swap = lease.admitted_snapshot.wsl_swap_used_bytes
        telemetry_failures = 0
        while True:
            await asyncio.sleep(MONITOR_SECONDS)
            try:
                snapshot_factory = getattr(
                    self.provider, "resource_snapshot", self.provider.snapshot
                )
                snapshot = await snapshot_factory()
                reason = None
                if snapshot.windows_available_bytes < EMERGENCY_FLOOR_BYTES:
                    reason = "LOCAL_RESOURCE_WINDOWS_EMERGENCY"
                elif snapshot.wsl_available_bytes < EMERGENCY_FLOOR_BYTES:
                    reason = "LOCAL_RESOURCE_WSL_EMERGENCY"
                elif snapshot.wsl_swap_used_bytes - baseline_swap > MAX_SWAP_GROWTH_BYTES:
                    reason = "LOCAL_RESOURCE_SWAP_EMERGENCY"
            except LocalModelResourceUnavailable:
                telemetry_failures += 1
                if telemetry_failures < MAX_CONSECUTIVE_MONITOR_FAILURES:
                    continue
                reason = "LOCAL_RESOURCE_TELEMETRY_UNAVAILABLE"
            else:
                telemetry_failures = 0
            if reason is None:
                continue
            lease.emergency_reason = reason
            if lease.unload_on_release:
                try:
                    await self.provider.unload(lease.model)
                    lease.model_unloaded = True
                except LocalModelResourceUnavailable:
                    pass
            owner_task.cancel()
            return

    @asynccontextmanager
    async def generator_session(
        self,
        model: str,
        *,
        wait_timeout: float | None = LEGACY_RESOURCE_WAIT_SECONDS,
        on_wait: ResourceCallback | None = None,
        on_ready: ResourceCallback | None = None,
    ) -> AsyncIterator[LocalModelLease]:
        current = _ACTIVE_LOCAL_MODEL_LEASE.get()
        if current is not None:
            if current.model != model:
                raise LocalModelResourceBusy("LOCAL_MODEL_NESTED_MODEL_CONFLICT")
            yield current
            return

        lease_id = str(uuid.uuid4())
        deadline = self._deadline(wait_timeout)
        claimed = False
        lease: LocalModelLease | None = None
        token: contextvars.Token | None = None
        monitor: asyncio.Task | None = None
        try:
            await self._claim_heavy(
                lease_id, deadline=deadline, on_wait=on_wait
            )
            claimed = True
            admitted, preexisting = await self._admit(
                model, deadline=deadline, on_wait=on_wait
            )
            lease = LocalModelLease(
                lease_id=lease_id,
                model=model,
                admitted_snapshot=admitted,
                unload_on_release=not preexisting,
            )
            token = _ACTIVE_LOCAL_MODEL_LEASE.set(lease)
            await self._callback(on_ready, "LOCAL_RESOURCE_ADMITTED")
            owner_task = asyncio.current_task()
            if owner_task is None:
                raise LocalModelResourceUnavailable("LOCAL_MODEL_TASK_UNAVAILABLE")
            monitor = asyncio.create_task(
                self._monitor(owner_task, lease),
                name=f"local-model-resource-monitor-{lease_id}",
            )
            try:
                yield lease
            except asyncio.CancelledError as error:
                if lease.emergency_reason:
                    raise LocalModelEmergencyAbort(lease.emergency_reason) from error
                raise
        finally:
            if monitor is not None:
                monitor.cancel()
                try:
                    await monitor
                except asyncio.CancelledError:
                    pass
            if lease is not None and lease.unload_on_release and not lease.model_unloaded:
                try:
                    await self.provider.unload(model)
                    lease.model_unloaded = True
                except LocalModelResourceUnavailable:
                    # Admission remains blocked by actual residency on the next
                    # request.  Never release safety by pretending unload passed.
                    pass
            if token is not None:
                _ACTIVE_LOCAL_MODEL_LEASE.reset(token)
            if claimed:
                self._release_heavy(lease_id)

    async def unload_owned_model(self, model: str) -> bool:
        current = _ACTIVE_LOCAL_MODEL_LEASE.get()
        if model == settings.embedding_model:
            await self.provider.unload(model)
            return True
        if current is None or current.model != model or not current.unload_on_release:
            return False
        await self.provider.unload(model)
        current.model_unloaded = True
        return True

    def _event_loop_thread(self) -> bool:
        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _external_heavy_resident(self) -> bool:
        models = self.provider.resident_models_sync()
        return any(item.name != settings.embedding_model for item in models)

    @contextmanager
    def embedding_session(
        self, *, wait_timeout: float | None = 300.0
    ) -> Iterator[None]:
        if _ACTIVE_LOCAL_MODEL_LEASE.get() is not None:
            raise LocalModelResourceBusy("LOCAL_EMBEDDING_DURING_GENERATOR")
        deadline = self._deadline(wait_timeout)
        acquired = False
        while not acquired:
            # Ollama residency requires I/O.  Never hold the process-global
            # condition while waiting for it, otherwise a generator release
            # cannot make progress while this probe is blocked.
            external_heavy = self._external_heavy_resident()
            with self._condition:
                blocked = self._active_heavy_id is not None or bool(self._heavy_queue)
                if not blocked:
                    # A model loaded outside NEXT Stabil is included in resource
                    # admission and is never force-unloaded.  Embedding waits for
                    # it to leave residency instead of creating unsafe overlap.
                    blocked = external_heavy
                if not blocked:
                    self._active_embeddings += 1
                    acquired = True
                    break
                if self._event_loop_thread():
                    raise LocalModelResourceBusy("LOCAL_EMBEDDING_RESOURCE_BUSY")
                if self._timed_out(deadline):
                    raise LocalModelResourceBusy("LOCAL_EMBEDDING_RESOURCE_BUSY")
                self._condition.wait(timeout=0.5)
        try:
            yield
        finally:
            if acquired:
                with self._condition:
                    self._active_embeddings = max(0, self._active_embeddings - 1)
                    self._condition.notify_all()

    def state(self) -> dict[str, int | bool]:
        with self._condition:
            return {
                "heavy_active": self._active_heavy_id is not None,
                "heavy_waiters": len(self._heavy_queue),
                "embedding_active": self._active_embeddings,
            }


local_model_resource_coordinator = LocalModelResourceCoordinator()
