# VivagoAgent Hosted MCP + Local MCP Bridge 设计（已归档）

本方案已经归档。当前实施和后续演进请以
[`2026-08-07-vivago-agent-cli-go-public-beta-design.md`](2026-08-07-vivago-agent-cli-go-public-beta-design.md)
为准。Hosted MCP + 插件内置文件 Helper 仅是未来公开阶段的按需参考，不是当前实施主线。

Local MCP Bridge 不再承担上传、预览和下载：Hosted MCP 复用现有预签名上传能力，插件内置脚本流式 PUT；不新增 upload session、finalize 和 Asset 表。预览和下载优先使用 Codex、Claude Code 自身能力。当前 Go CLI/认证继续作为主线，标准 OAuth 完成后再评估由宿主直连 Hosted MCP。
