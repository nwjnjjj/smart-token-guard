"""SmartTokenGuard MCP server (stdio). Reads local files the user points at, sends them to the API, keeps the
per-project spend ledger on this computer."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import anyio
from pydantic import Field

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, ImageContent, TextContent

from . import Client, STGError, __version__

Defect = Literal["facial_distortion", "identity_drift", "deformed_hands", "extra_limbs", "body_morphing",
                 "wardrobe_drift", "background_warping", "text_artifacts", "other"]

mcp = MCPServer(
    name="SmartTokenGuard",
    version=__version__,
    instructions=(
        "SmartTokenGuard stops wasted AI video renders. Inspect the keyframe image with stg_inspect_render BEFORE paying "
        "for image-to-video, then inspect every clip. Look at the returned review frames yourself for hands, faces, "
        "identity and wardrobe, and pass what you see to stg_qa_gate (visually_reviewed=true only after looking). "
        "Follow its decision: PASS, RETRY_SAME_MODEL with the suggested negative terms / lower motion / new seed, "
        "SWITCH_TO_FALLBACK, or HALT. Each inspection uses 1 check; stg_qa_gate, stg_spend_report and stg_account are free. "
        "If a tool says a license is required, run stg_pricing and show the plans; payment happens in the browser on "
        "Polar's checkout page, never in chat. Reply in the user's language."
    ),
)


def _client() -> Client:
    return Client()


def _fail(e: STGError) -> ToolError:
    if e.code in ("LICENSE_REQUIRED", "INVALID_KEY", "SUBSCRIPTION_INACTIVE", "EXPIRED", "WRONG_PRODUCT"):
        return ToolError(f"License required [{e.code}]: {e.message} Run stg_pricing to show the plans.")
    return ToolError(f"[{e.code}] {e.message}")


async def _call(fn, *args, **kwargs):
    try:
        return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
    except STGError as e:
        raise _fail(e) from None


# ---------------------------------------------------------------- local ledger (never leaves this computer)
def _home() -> Path:
    home = Path(os.environ.get("STG_HOME", Path.home() / ".smart-token-guard")) / "ledgers"
    home.mkdir(parents=True, exist_ok=True)
    return home


def _ledger_path(project: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]{0,63}", project or ""):
        raise ToolError("project must be 1-64 letters, digits, '-' or '_'")
    return _home() / f"{project}.json"


def _load(project: str) -> Dict[str, Any]:
    path = _ledger_path(project)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"budget_usd": None, "shots": {}}


def _save(project: str, ledger: Dict[str, Any]):
    path = _ledger_path(project)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- tools
@mcp.tool()
async def stg_pricing() -> Dict[str, Any]:
    """Plans, prices and checkout links for SmartTokenGuard. No license needed."""
    return await _call(_client().pricing)


@mcp.tool()
async def stg_account() -> Dict[str, Any]:
    """Check the configured license: who it is licensed to, checks used and checks remaining."""
    return await _call(_client().account)


@mcp.tool()
async def stg_inspect_render(
    path: str,
    reference_image: Optional[str] = None,
    review_frames: int = Field(default=3, ge=1, le=6),
    sensitivity: Optional[Literal["strict", "standard", "relaxed"]] = None,
    ignore_issues: Optional[List[str]] = None,
) -> CallToolResult:
    """
    Measure a rendered image or video (local path, max 32 MB / 60 s / 1080p): blur, exposure, black and frozen frames,
    flicker, hard cuts, impacts and flashes, and colour/lighting drift against `reference_image`. Uses 1 check.
    Returns a JSON report plus review frames — look at them for anatomy/identity defects, then call stg_qa_gate.
    """
    result = await _call(_client().inspect, path, reference_image, review_frames, sensitivity, ignore_issues)
    images = result.pop("review_images_jpeg_base64", [])
    report = result["report"]
    content: List[Any] = [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    for frame, data in zip(report.get("review_frames", []), images):
        content.append(TextContent(type="text", text=f"Review frame {frame['frame']} @ {frame['time_sec']}s ({frame['reason']})"))
        content.append(ImageContent(type="image", data=data, mime_type="image/jpeg"))
    return CallToolResult(content=content, structured_content=result)


@mcp.tool()
async def stg_detect_events(video_path: str) -> Dict[str, Any]:
    """Frames and times of impacts, flashes and cuts in a video — for placing sound effects in an editor. Uses 1 check."""
    result = await _call(_client().inspect, video_path, None, 0)
    report = result["report"]
    return {"fps": report.get("fps"), "duration_sec": report.get("duration_sec"), "events": report.get("events", []),
            "license": result.get("license")}


@mcp.tool()
async def stg_qa_gate(
    project: str,
    shot_id: str,
    model: str,
    render_cost_usd: float = Field(ge=0),
    technical_issues: Optional[List[Dict[str, Any]]] = None,
    semantic_defects: Optional[List[Defect]] = None,
    fallback_model: Optional[str] = None,
    visually_reviewed: bool = False,
    project_budget_usd: Optional[float] = Field(default=None, ge=0),
    stage: Literal["keyframe", "clip"] = "clip",
    notes: str = "",
) -> Dict[str, Any]:
    """
    Decide what to do with a render: PASS / NEEDS_VISUAL_REVIEW / RETRY_SAME_MODEL / SWITCH_TO_FALLBACK / HALT /
    HALT_BUDGET, with concrete fixes (negative-prompt terms, lower motion, new seed). technical_issues: the `issues`
    array from stg_inspect_render. semantic_defects: what you saw in the review frames ("other" + notes if unlisted).
    Records the attempt and its cost in a local project ledger. Free (needs a license, uses no checks).
    """
    ledger = _load(project)
    if project_budget_usd is not None:
        ledger["budget_usd"] = project_budget_usd
    history = ledger["shots"].get(shot_id, [])
    spent = round(sum(a["cost_usd"] for shot in ledger["shots"].values() for a in shot), 4)
    result = await _call(_client().qa_gate, model, render_cost_usd, technical_issues, list(semantic_defects or []),
                         fallback_model, history, spent, ledger["budget_usd"], visually_reviewed, stage, notes)
    attempt = result.pop("record_this_attempt")
    attempt.update({"stage": stage, "visually_reviewed": visually_reviewed, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    ledger["shots"].setdefault(shot_id, []).append(attempt)
    _save(project, ledger)
    result["shot"] = {"shot_id": shot_id, "attempts": len(ledger["shots"][shot_id]),
                      "spent_usd": round(sum(a["cost_usd"] for a in ledger["shots"][shot_id]), 4)}
    return result


@mcp.tool()
async def stg_spend_report(project: str) -> Dict[str, Any]:
    """What a project spent on renders, attempts per shot, first-try pass rate and failed renders caught. Local only."""
    shots = _load(project)["shots"]
    passed = {s: a for s, a in shots.items() if any(x["decision"] == "PASS" for x in a)}
    rejected = [x for a in shots.values() for x in a if x["decision"] not in ("PASS", "NEEDS_VISUAL_REVIEW")]
    return {
        "project": project,
        "spent_usd": round(sum(x["cost_usd"] for a in shots.values() for x in a), 4),
        "shots": len(shots), "shots_passed": len(passed),
        "attempts_per_passed_shot": round(sum(len(a) for a in passed.values()) / len(passed), 2) if passed else None,
        "first_try_pass_rate": round(sum(1 for a in passed.values() if a[0]["decision"] == "PASS") / len(passed), 2) if passed else None,
        "renders_rejected": len(rejected),
        "rejected_keyframes": sum(1 for x in rejected if x.get("stage") == "keyframe"),
        "note": "Rejected keyframes are image-to-video renders you did not have to pay for.",
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
