"""SmartTokenGuard client SDK. All analysis runs on the SmartTokenGuard API; this package only uploads and calls it.

    from smart_token_guard import Client
    stg = Client()                      # reads STG_LICENSE_KEY
    report = stg.inspect("shot010.mp4")
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

__version__ = "1.2.2"
__all__ = ["Client", "STGError", "DEFAULT_API_URL"]

DEFAULT_API_URL = "https://stg-api-560636228350.asia-east1.run.app"
MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm", ".mkv"}
MAX_UPLOAD = 32 * 1024 * 1024


class STGError(Exception):
    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(f"[{code}] {message}")
        self.code, self.message, self.status = code, message, status


class Client:
    def __init__(self, license_key: Optional[str] = None, api_url: Optional[str] = None, timeout: float = 300):
        self.license_key = (license_key or os.environ.get("STG_LICENSE_KEY", "")).strip()
        self.api_url = (api_url or os.environ.get("STG_API_URL") or DEFAULT_API_URL).rstrip("/")
        if not self.api_url.startswith("https://") and not self.api_url.startswith(("http://127.0.0.1", "http://localhost")):
            raise STGError("INSECURE_URL", "The API URL must use https.")
        self._http = httpx.Client(timeout=timeout, headers={"User-Agent": f"smart-token-guard/{__version__}"})

    # ------------------------------------------------------------------ helpers
    def _headers(self) -> Dict[str, str]:
        if not self.license_key:
            raise STGError("LICENSE_REQUIRED", "Set STG_LICENSE_KEY to the license key from your Polar receipt.")
        return {"Authorization": f"Bearer {self.license_key}"}

    @staticmethod
    def _result(response: httpx.Response) -> Dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            raise STGError("BAD_RESPONSE", f"The API returned HTTP {response.status_code} without JSON.", response.status_code) from None
        if response.status_code >= 400 or body.get("ok") is False:
            error = body.get("error") or {}
            raise STGError(error.get("code", "HTTP_ERROR"), error.get("message", f"HTTP {response.status_code}"), response.status_code)
        body.pop("ok", None)
        return body

    def _send(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        try:
            return self._result(self._http.request(method, self.api_url + path, **kwargs))
        except httpx.TimeoutException:
            raise STGError("TIMEOUT", "The API did not answer in time. Try a shorter clip or retry.") from None
        except httpx.TransportError as e:
            raise STGError("NETWORK", f"Cannot reach the SmartTokenGuard API: {type(e).__name__}.") from None

    @staticmethod
    def _media(path: str, label: str) -> Path:
        p = Path(path).expanduser()
        if not p.is_file():
            raise STGError("NOT_FOUND", f"{label} not found: {p}")
        if p.suffix.lower() not in MEDIA_SUFFIXES:
            raise STGError("UNSUPPORTED_MEDIA", f"{label} must be JPEG, PNG, WebP, MP4, MOV, WebM or MKV.")
        if p.stat().st_size > MAX_UPLOAD - 64 * 1024:
            raise STGError("UPLOAD_LIMIT", f"{label} is larger than 32 MB. Export a shorter or lower-bitrate version.")
        return p

    # ------------------------------------------------------------------ API
    def pricing(self) -> Dict[str, Any]:
        return self._send("GET", "/v1/pricing")

    def account(self) -> Dict[str, Any]:
        return self._send("GET", "/v1/account", headers=self._headers())

    def inspect(self, path: str, reference_image: Optional[str] = None, review_frames: int = 3,
                sensitivity: Optional[str] = None, ignore_issues: Optional[List[str]] = None,
                overrides: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Measure an image or video. Uses 1 check. Returns report, review frames (base64 JPEG) and license usage."""
        headers = self._headers()
        media = self._media(path, "File")
        ref = self._media(reference_image, "Reference image") if reference_image else None
        options = {"review_frames": review_frames, "sensitivity": sensitivity,
                   "ignore_issues": ignore_issues or [], "overrides": overrides or {}}
        with media.open("rb") as f, (ref.open("rb") if ref else open(os.devnull, "rb")) as r:
            files = {"file": (media.name, f)}
            if ref:
                files["reference"] = (ref.name, r)
            return self._send("POST", "/v1/inspect", headers=headers, files=files, data={"options": json.dumps(options)})

    def qa_gate(self, model: str, render_cost_usd: float, technical_issues: Optional[List[Dict[str, Any]]] = None,
                semantic_defects: Optional[List[str]] = None, fallback_model: Optional[str] = None,
                shot_history: Optional[List[Dict[str, Any]]] = None, project_spent_usd: float = 0,
                project_budget_usd: Optional[float] = None, visually_reviewed: bool = False,
                stage: str = "clip", notes: str = "", pass_score: int = 85, max_retries_per_model: int = 1) -> Dict[str, Any]:
        """PASS / NEEDS_VISUAL_REVIEW / RETRY_SAME_MODEL / SWITCH_TO_FALLBACK / HALT / HALT_BUDGET. Not metered."""
        body = {k: v for k, v in locals().items() if k != "self"}
        return self._send("POST", "/v1/qa-gate", headers=self._headers(), json=body)
