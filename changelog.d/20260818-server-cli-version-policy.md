# 2026-08-18

- 明确公开 Beta 的坏版本止损责任由 VivagoAgent 承担，并记录服务端精确版本 denylist、HTTP 426
  错误契约、清空回滚方法及海外非生产演练要求；CLI 仓库不实现第二套版本封禁逻辑。
- CLI 识别服务端受控的 `426 + CLI_VERSION_BLOCKED` 响应并输出明确升级提示，同时继续脱敏其他
  HTTP 错误响应。
