# Added

- 新增 Go SSE 流基础能力：解析事件 ID、事件名、JSON/多行 data 和心跳，识别 `RUN_FINISHED` / `RUN_ERROR`，在提前断流时输出 `turn_id + last_event_id` 恢复信息，并从 Web v2 chat 响应头读取会话标识。
