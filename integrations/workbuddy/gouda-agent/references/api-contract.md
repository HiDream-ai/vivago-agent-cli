# 国内接口协议

本 Skill 只连接 `https://goudaai.com`，不提供 dev 或自定义 origin 参数。

| 能力 | 请求 |
| --- | --- |
| 刷新登录票据 | `GET /prod-api/user/apikey2token` |
| 创建 Project | `POST /api/agent/v1/project/create` |
| Project 列表 | `POST /api/agent/v1/project/list` |
| Project 详情 | `POST /api/agent/v1/project/detail` |
| 账户素材列表 | `POST /api/agent/v1/project_asset_list` |
| 提交/恢复 Turn | `POST /api/agent/v2/conversation/chat` |
| 取消 Turn | `POST /api/agent/v2/conversation/cancel` |
| Conversation 历史 | `POST /api/agent/v2/conversation/history` |
| 国内 OSS STS | `GET /prod-api/user/oss_key/{image|media}` |

Project 协作深链由本地生成，不请求服务端，固定格式为：

```text
https://goudaai.com/new-chat?project_id={project-id}&conversation_id={conversation-id}
```

创建 Project 的请求体固定为：

```json
{"name":"<name>","version":"v3"}
```

普通接口返回一行 JSON envelope：

```json
{"ok":true,"data":{},"error":null}
```

`ask` 和 `resume` 返回 JSONL。第一行为：

```json
{"type":"session","conversation_id":"...","turn_id":"..."}
```

随后每行是一条 SSE 事件：

```json
{"type":"event","event_id":"...","event":"message","data":{"type":"RUN_STARTED"}}
```

终态只有 `RUN_FINISHED` 和 `RUN_ERROR`。没有终态就结束的流必须当作可恢复中断，不能当作成功。

请求携带 `X-Client-Platform: web`。第一版暂用后端已经识别的 `X-Source: cli` 兼容值；
`User-Agent` 中的 `gouda-agent-workbuddy/<version>` 用于区分 WorkBuddy 调用。增加独立的
`workbuddy` 持久化来源需要服务端先扩展白名单，不在本 Skill 内伪造。

## 上传与资源协议

国内附件凭证：

```text
GET https://goudaai.com/prod-api/user/oss_key/image
GET https://goudaai.com/prod-api/user/oss_key/media
```

国内资源地址：

```text
image: https://storage-cdn.hidreamai.com/image/{oss-key}
video/audio: https://media-cdn.hidreamai.com/{oss-key}
```
