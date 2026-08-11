# Changed

- 明确公开 Beta 使用 `platform=web + source=cli`：VivagoAgent 只为 Project、Conversation 和 Turn 增加来源字段，资产通过现有关联标识追溯，CustomWorkflow 不修改；日志、监控和限流统计记录 CLI 来源，同时保持 Web 可见性和现有用户级限流。
