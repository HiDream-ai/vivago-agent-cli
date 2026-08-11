# GitHub 开发 CI

- 增加只读的 GitHub 开发 CI，覆盖默认和 prod 测试、Race、Vet、六平台构建、双插件校验、checksum、来源和环境边界验证。
- 增加手动开发发布，严格限制 `-dev.N` 版本，只创建 Prerelease 并以普通快进提交更新 `dev-marketplace`。
- 流水线不硬编码个人 GitHub 仓库；后续公司 GitHub 可以复用质量与构建约束，并通过独立的受保护 prod 发布入口生成 Beta。
- 验证方式：工作流契约测试、分发包验证器测试、完整 Go/Python 测试、官方 Codex 校验器和 Claude Code Marketplace 校验。
