# SmartTokenGuard

<!-- mcp-name: io.github.nwjnjjj/smart-token-guard -->

**Stop paying for broken AI video renders.**

SmartTokenGuard checks every keyframe and clip you generate with ComfyUI, Kling, Runway, Veo, Hailuo, Seedance or
any other AI video tool. It catches the render failures you would otherwise pay to re-render later, and tells your
AI assistant what to do next: pass it, retry with specific fixes, switch models, or stop spending on that shot.

| Tool | What it does |
| --- | --- |
| `stg_inspect_render` | Measures an image or video: blur and soft focus, over/under-exposure, black frames, frozen segments, flicker, hard cuts, impacts and flashes, and colour/lighting drift against a reference image. Returns review frames so your assistant can check hands, faces and identity. |
| `stg_qa_gate` | Turns measured issues + what the assistant saw into **PASS / RETRY_SAME_MODEL / SWITCH_TO_FALLBACK / HALT / HALT_BUDGET**, with concrete fixes (negative-prompt terms, lower motion, new seed). Keeps a spend ledger per project on your computer. |
| `stg_detect_events` | Exact frames of impacts, flashes and cuts, for placing sound effects. |
| `stg_spend_report` | What a project spent, attempts per passed shot, first-try pass rate, keyframes rejected before paying for video. |
| `stg_account`, `stg_pricing` | License usage and plans. |

**Check the keyframe first.** A rejected still costs nothing. A rejected 5-second clip has already been paid for.

What it does **not** do: it never generates or re-renders video, and never calls a paid AI API for you. Hands, faces
and identity are judged by your assistant from the review frames; a render is only PASS after that visual review.

## Plans

| Plan | Monthly | Yearly | Checks per month |
| --- | --- | --- | --- |
| **Starter** | US$9 | US$99 | 300 |
| **Pro** | US$29 | US$290 | 3,000 |

Checks reset on the 1st of each month (UTC). One license per person; teams buy one per member. Checkout, tax and
invoices are handled by Polar, the merchant of record. **The license key in your Polar receipt is your API key.**
Cancel or change plans in the Polar customer portal. Run `stg_pricing` for the checkout links.

## Install (MCP)

Requires [uv](https://docs.astral.sh/uv/).

**Claude Desktop / Cursor**: add to `claude_desktop_config.json` or `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "smart-token-guard": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nwjnjjj/smart-token-guard", "smart-token-guard"],
      "env": { "STG_LICENSE_KEY": "your-license-key" }
    }
  }
}
```

**Claude Code**

```bash
claude mcp add smart-token-guard -e STG_LICENSE_KEY=your-license-key -- uvx --from git+https://github.com/nwjnjjj/smart-token-guard smart-token-guard
```

**VS Code**: `.vscode/mcp.json` → `{"servers": {"smart-token-guard": {"type": "stdio", "command": "uvx", "args": [...same...], "env": {...}}}}`

Then ask: *"Inspect `renders/sh010_keyframe.png` against `refs/kai.png`. If it passes, I'll render the clip on Kling
(0.7 USD, fallback Runway)."*

## Python SDK

```bash
pip install git+https://github.com/nwjnjjj/smart-token-guard
```

```python
from smart_token_guard import Client

stg = Client()  # reads STG_LICENSE_KEY
report = stg.inspect("renders/sh010.mp4", reference_image="refs/kai.png")
print(report["report"]["issues"], report["license"]["checks_remaining"])

decision = stg.qa_gate(model="Kling", render_cost_usd=0.7, technical_issues=report["report"]["issues"],
                       semantic_defects=["deformed_hands"], fallback_model="Runway")
print(decision["decision"], decision["actions"])
```

HTTP API: `POST /v1/inspect` (multipart `file`, optional `reference`, `options` JSON), `POST /v1/qa-gate`,
`GET /v1/account` with `Authorization: Bearer <license key>`. See `GET /v1/capabilities`.

## Limits and privacy

- Up to 32 MB, 60 seconds and 1080p per file (JPEG, PNG, WebP, MP4, MOV, WebM, MKV). 30 requests per minute.
- Files are uploaded to the SmartTokenGuard API (Google Cloud), analysed in a temporary file, and **deleted before the
  response is sent**. Nothing is stored and nothing is used for training.
- The API receives your license key and the file. Project ledgers stay on your computer (`~/.smart-token-guard/`).
- Measured checks catch technical render failures. They do not certify anatomy, identity, copyright or story quality.

## Support

Refunds, invoices and cancellation: Polar customer portal (link in your receipt).
The client code in this repository is MIT licensed; the hosted API requires a paid license.
