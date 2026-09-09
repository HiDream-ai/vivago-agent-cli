# 输出格式

所有普通命令输出一行 JSON，`ask` 和 `resume` 每行输出一个 JSON 对象。只解析这些字段，不抓取
stderr 或自由文本。

## `ask` / `resume` JSONL

首条记录：

```json
{"type":"session","conversation_id":"...","turn_id":"..."}
```

后续 SSE 事件：

```json
{"type":"event","event_id":"...","event":"message","data":{"type":"RUN_STARTED"}}
```

常见 `data.type` 包括 `RUN_STARTED`、`TEXT_MESSAGE_START/CONTENT/END`、
`TOOL_CALL_START/END/RESULT`、`ACTIVITY_SNAPSHOT`、`CUSTOM`，以及终态
`RUN_FINISHED` / `RUN_ERROR`。除两个终态以外都只是进度。

流提前结束时最后一条为：

```json
{"type":"stream_error","conversation_id":"...","turn_id":"...","last_event_id":"...","error":{"code":"STREAM_ENDED_EARLY","message":"..."}}
```

此时进程退出 50，使用同一 Turn 和 `last_event_id` 恢复。

## 普通 JSON envelope

成功：

```json
{"ok":true,"data":{},"error":null}
```

失败：

```json
{"ok":false,"data":null,"error":{"code":"...","message":"..."}}
```

`project create` 的 Project ID 位于服务端响应 `data.data.project_id`：

```json
{"ok":true,"data":{"code":0,"message":"success","data":{"project_id":"..."}},"error":null}
```

`artifact preview` / `artifact download`：

```json
{"ok":true,"data":{"path":"/tmp/gouda-agent-preview-.../preview.mp4","bytes":19404802,"content_type":"video/mp4"},"error":null}
```

`artifact url`：

```json
{"ok":true,"data":{"url":"https://media-cdn.hidreamai.com/<content-id>"},"error":null}
```

`auth status` 只返回状态，不返回凭证：

```json
{"ok":true,"data":{"logged_in":true,"backend":"file","needs_refresh":false},"error":null}
```

`state list` 的 `data.tasks[]` 只含 Project、Conversation、Turn、游标、状态和时间。`project assets`
返回账户级分页素材分组，`sub_assets[]` 中可找到 `content_id` 和媒体信息。

## 最终产物 ID

最终视频 `content_id` 通常出现在够搭 Agent 的收尾消息和 `project assets` 中，而不是单独的
终态字段。恢复交付时同时检查历史收尾消息和素材列表；收尾消息指向的合成视频是最终产物，
同一 Turn 的其他视频可能只是分场景片段。
