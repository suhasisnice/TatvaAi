"""HTTP plumbing for external-source adapters. All adapters call the MOCK issuers service (base URL from config),
with timeouts and retries; a real authorised API can be plugged in later by changing MOCK_ISSUERS_URL."""
import hashlib
import json
from dataclasses import dataclass

import httpx

from app.core.config import settings

_factory = None  # tests install a TestClient factory here


def set_client_factory(f) -> None:
    global _factory
    _factory = f


_shared: httpx.Client | None = None


def _client():
    """One pooled client per process (a new connection per call made 100+ registry lookups slow)."""
    global _shared
    if _factory:
        return _factory()
    if _shared is None or str(_shared.base_url).rstrip("/") != settings.mock_issuers_url.rstrip("/"):
        _shared = httpx.Client(base_url=settings.mock_issuers_url, timeout=5.0, transport=httpx.HTTPTransport(retries=2))
    return _shared


@dataclass
class Result:
    source: str
    http_status: int | None  # None = network failure / timeout
    body: dict | None
    request_hash: str
    response_hash: str | None

    @property
    def available(self) -> bool:
        return self.http_status is not None and self.http_status < 500 and self.http_status != 501

    @property
    def record(self) -> dict | None:
        return (self.body or {}).get("record")


def call(source: str, path: str, **params) -> Result:
    req_hash = hashlib.sha256(json.dumps([path, params], sort_keys=True).encode()).hexdigest()
    try:
        c = _client()
        r = c.get(path, params=params)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text}
        return Result(source, r.status_code, body, req_hash, hashlib.sha256(r.content).hexdigest())
    except httpx.HTTPError:
        return Result(source, None, None, req_hash, None)
