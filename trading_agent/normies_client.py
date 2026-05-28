"""HTTP client for the public Normies API with cache, backoff, and ID guards."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .config import Settings
from .normies_models import validate_token_id


class NormiesApiError(RuntimeError):
    """Raised when the Normies API returns an unrecoverable error."""


class NormiesNotAvailable(NormiesApiError):
    """Raised when a token endpoint returns 404/410 for burned or unavailable data."""


class NormiesClient:
    """Small stdlib-only client for Normies API endpoints."""

    def __init__(self, settings: Settings, use_cache: bool = True) -> None:
        self.settings = settings
        self.use_cache = use_cache
        self._last_request_at = 0.0

    def get_metadata(self, token_id: int) -> dict[str, Any]:
        return self._get_json(f"/normie/{validate_token_id(token_id)}/metadata")

    def get_traits(self, token_id: int) -> Any:
        return self._get_json(f"/normie/{validate_token_id(token_id)}/traits")

    def get_pixels(self, token_id: int) -> str:
        return self._get_text(f"/normie/{validate_token_id(token_id)}/pixels")

    def get_canvas_info(self, token_id: int) -> dict[str, Any]:
        return self._get_json(f"/normie/{validate_token_id(token_id)}/canvas/info")

    def get_canvas_diff(self, token_id: int) -> dict[str, Any]:
        return self._get_json(f"/normie/{validate_token_id(token_id)}/canvas/diff")

    def get_owner(self, token_id: int) -> dict[str, Any]:
        return self._get_json(f"/normie/{validate_token_id(token_id)}/owner")

    def get_history_stats(self) -> dict[str, Any]:
        return self._get_json("/history/stats")

    def _get_json(self, path: str) -> Any:
        body = self._request(path)
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise NormiesApiError(f"Expected JSON from {path}, got invalid payload") from exc

    def _get_text(self, path: str) -> str:
        return self._request(path)

    def _request(self, path: str) -> str:
        cache_path = self._cache_path(path)
        if self.use_cache and cache_path.exists():
            return cache_path.read_text(encoding="utf-8")

        url = f"{self.settings.normies_base_url}{path}"
        attempts = 4
        for attempt in range(1, attempts + 1):
            self._throttle()
            req = urllib.request.Request(url, headers={"User-Agent": self.settings.user_agent})
            try:
                with urllib.request.urlopen(req, timeout=self.settings.request_timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    if self.use_cache:
                        cache_path.parent.mkdir(parents=True, exist_ok=True)
                        cache_path.write_text(body, encoding="utf-8")
                    return body
            except urllib.error.HTTPError as exc:
                if exc.code in {404, 410}:
                    raise NormiesNotAvailable(f"{path} is not available ({exc.code})") from exc
                if exc.code == 429 or 500 <= exc.code <= 599:
                    if attempt < attempts:
                        self._sleep_for_retry(exc, attempt)
                        continue
                raise NormiesApiError(f"HTTP {exc.code} while requesting {path}") from exc
            except urllib.error.URLError as exc:
                if attempt < attempts:
                    time.sleep(min(2**attempt, 10))
                    continue
                raise NormiesApiError(f"Network error while requesting {path}: {exc}") from exc
        raise NormiesApiError(f"Failed requesting {path}")

    def _throttle(self) -> None:
        rpm = max(self.settings.requests_per_minute, 1)
        min_interval = 60.0 / rpm
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _sleep_for_retry(self, exc: urllib.error.HTTPError, attempt: int) -> None:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                time.sleep(float(retry_after))
                return
            except ValueError:
                pass
        time.sleep(min(2**attempt, 30))

    def _cache_path(self, path: str) -> Path:
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        suffix = ".json" if not path.endswith("/pixels") else ".txt"
        return self.settings.cache_dir / f"{digest}{suffix}"
