"""Serialization-lock tests for the API client."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from custom_components.ecovolter.api import (
    EcovolterApiClient,
    EcovolterApiClientCommunicationError,
)


class FakeResponse:
    def __init__(self) -> None:
        self.status = 200

    def raise_for_status(self) -> None:
        return None

    async def json(self) -> Any:
        return {"ok": True}


class RecordingSession:
    """Fake aiohttp session that tracks request overlap inside the locked section."""

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0
        self.raise_timeout = False

    async def request(self, method, url, headers=None, json=None) -> FakeResponse:
        if self.raise_timeout:
            raise TimeoutError("forced")
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            # Yield control so a second un-serialized request could interleave here.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            return FakeResponse()
        finally:
            self.active -= 1


def _make_client(session: Any) -> EcovolterApiClient:
    return EcovolterApiClient(
        serial_number="abc",
        secret_key="secret",
        base_uri="http://ecovolter.test",
        session=session,
    )


@pytest.mark.asyncio
async def test_get_and_patch_never_overlap() -> None:
    """A GET and a PATCH issued concurrently are serialized by the lock."""
    session = RecordingSession()
    client = _make_client(session)

    await asyncio.gather(
        client.async_get_status(),
        client.async_set_settings({"targetCurrent": 12}),
    )

    assert session.max_active == 1


@pytest.mark.asyncio
async def test_many_concurrent_requests_never_overlap() -> None:
    """Even a burst of concurrent requests is fully serialized."""
    session = RecordingSession()
    client = _make_client(session)

    await asyncio.gather(*(client.async_get_status() for _ in range(10)))

    assert session.max_active == 1


@pytest.mark.asyncio
async def test_lock_released_after_timeout() -> None:
    """A forced TimeoutError releases the lock so the next request proceeds."""
    session = RecordingSession()
    client = _make_client(session)

    session.raise_timeout = True
    with pytest.raises(EcovolterApiClientCommunicationError):
        await client.async_get_status()

    # Lock must be free again.
    assert client._request_lock.locked() is False

    # And a subsequent request succeeds (proving the lock was released).
    session.raise_timeout = False
    result = await client.async_get_status()
    assert result == {"ok": True}
