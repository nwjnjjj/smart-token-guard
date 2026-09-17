# SmartTokenGuard

[English](README.md) · **简体中文**

**别再为 AI 视频废片烧钱。**

每一段黑屏、卡帧、角色跑脸的片段，都是你已经花出去的钱。SmartTokenGuard 在 ComfyUI、可灵、即梦、海螺、
Runway、Veo 或任何 AI 视频工具生成完成的那一刻检查关键帧和视频，并告诉你的 AI 助手是否值得为下一步付费：
通过、带着具体修正重试、换模型，或者停止在这个镜头上花钱。

**废片每个月让你损失多少？** 试试省钱计算器：https://nwjnjjj.github.io/smart-token-guard/zh/

| 工具 | 功能 |
| --- | --- |
| `stg_inspect_render` | 测量图片或视频：模糊与虚焦、过曝/欠曝、黑屏、卡帧、闪烁、硬切、撞击与闪光，以及与参考图的色彩/光线偏移。返回审阅帧，让 AI 助手检查手、脸和角色一致性。 |
| `stg_qa_gate` | 把测量结果和助手看到的问题转换为 **PASS / RETRY_SAME_MODEL / SWITCH_TO_FALLBACK / HALT / HALT_BUDGET**，并给出具体修正（负面提示词、降低运动幅度、新种子）。每个项目的花费记录保存在你自己的电脑上。 |
| `stg_detect_events` | 精确到帧的撞击、闪光和剪切点，方便对齐音效。 |
| `stg_spend_report` | 项目花费、每个通过镜头的尝试次数、一次通过率、在生成视频前被淘汰的关键帧数量。 |
| `stg_account`、`stg_pricing` | 许可证用量和价格方案。 |

**先检查关键帧。** 淘汰一张图不花钱，淘汰一段 5 秒视频的钱已经付出去了。

## 价格

| 方案 | 月付 | 年付 | 每月检查次数 |
| --- | --- | --- | --- |
| **Starter** | US$9 | US$99 | 300 |
| **Pro** | US$29 | US$290 | 3,000 |

检查次数每月 1 日（UTC）重置。每个许可证限一人使用。结账、税务和发票由 Polar 处理，支持 Visa、Mastercard 等银行卡。
**Polar 收据中的许可证密钥就是你的 API 密钥。**

## 安装（MCP）

**Claude Desktop：** 下载 [smart-token-guard-1.2.2.mcpb](https://github.com/nwjnjjj/smart-token-guard/releases/latest/download/smart-token-guard-1.2.2.mcpb)，双击并粘贴密钥。

**Claude Code**

```bash
claude mcp add smart-token-guard -e STG_LICENSE_KEY=你的许可证密钥 -- uvx --from git+https://github.com/nwjnjjj/smart-token-guard smart-token-guard
```

**Cursor / VS Code / Python SDK / 远程 MCP / A2A：** 见 [英文 README](README.md#install-mcp)。

然后直接问：*"在我付费生成下一段之前，先检查 `renders/sh010_keyframe.png` 是否和 `refs/kai.png` 一致。"*

## 隐私

文件上传到 SmartTokenGuard API（Google Cloud），分析完成后在返回结果之前立即删除，不保存、不用于训练。
