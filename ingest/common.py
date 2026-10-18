"""Shared HTTP and raw-file helpers for public procurement data sources."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any

import requests
from requests import Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CACHE_DIR = RAW_DIR / ".cache"
TIMEOUT = 30
USER_AGENT = "BidCompass/0.1 (public procurement research)"

_session = requests.Session()
_retry = Retry(
    total=4,
    connect=4,
    read=4,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=frozenset({"GET", "POST"}),
    respect_retry_after_header=True,
)
_adapter = HTTPAdapter(max_retries=_retry)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)
_session.headers.update({"User-Agent": USER_AGENT})


def _cache_path(url: str, params: dict[str, Any] | None) -> Path:
    request_key = {
        "url": url,
        "params": params or {},
    }
    encoded_key = json.dumps(request_key, sort_keys=True, default=str).encode("utf-8")
    return CACHE_DIR / f"{hashlib.sha256(encoded_key).hexdigest()}.json"


def _cached_response(cache_path: Path) -> Response:
    cached = json.loads(cache_path.read_text(encoding="utf-8"))
    response = Response()
    response.status_code = cached["status_code"]
    response._content = base64.b64decode(cached["content"])
    response.headers.update(cached["headers"])
    response.url = cached["url"]
    response.encoding = cached.get("encoding")
    return response


def _write_cache(cache_path: Path, response: Response) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(
            {
                "status_code": response.status_code,
                "content": base64.b64encode(response.content).decode("ascii"),
                "headers": dict(response.headers),
                "url": response.url,
                "encoding": response.encoding,
            }
        ),
        encoding="utf-8",
    )


def get(url: str, params: dict[str, Any] | None = None) -> Response:
    """GET a URL with retries, a timeout, a polite User-Agent, and disk caching."""
    cache_path = _cache_path(url, params)
    if cache_path.exists():
        return _cached_response(cache_path)

    response = _session.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    _write_cache(cache_path, response)
    return response


def post(url: str, json_body: dict[str, Any]) -> Response:
    """POST JSON with retries, a timeout, and the shared User-Agent."""
    response = _session.post(url, json=json_body, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def save_raw(source: str, name: str, data: Any) -> Path:
    """Save bytes unchanged or serialize JSON data under ``data/raw/<source>``."""
    destination = RAW_DIR / source / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        destination.write_bytes(data)
    else:
        destination.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    return destination
