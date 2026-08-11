# Changed

- 明确公开 Beta 的凭证降级策略：macOS 和 Windows 必须使用系统凭证库，只有 Linux/WSL 在 Secret Service 不可用时允许使用 `0700` 目录和 `0600` 文件；同时确认首批操作系统与 CPU 支持范围。
