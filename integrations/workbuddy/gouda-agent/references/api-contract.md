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

请求携带 `X-Client-Platform: web` 和 `X-Source: workbuddy`，让后端能够独立归因
WorkBuddy Skill 创建的 Project、Conversation 和 Turn。`User-Agent` 中的
`gouda-agent-workbuddy/<version>` 用于识别具体 Skill 版本。现有 Go CLI 继续使用
`X-Source: cli`，两者互不切换。

## 支付门槛

如果 SSE 事件报告积分或会员等级不足，命令会在原始事件之后输出一条
`payment_required` 记录，并尝试打开够搭网页使用的商品页：

| 业务原因 | 服务端代码 | 商品页 |
| --- | ---: | --- |
| 积分不足 | `2007` 或 `insufficient_credits` | `https://market.volcengine.com/goods/detail?goodsId=wysf9000287&detailFrom=2` |
| 会员等级不足 | `2020` | `https://market.volcengine.com/goods/detail?goodsId=wysf9000286&detailFrom=2` |

记录格式为（国内接口数字错误码）：

```json
{"type":"payment_required","reason":"credits","code":2007,"url":"https://market.volcengine.com/goods/detail?goodsId=wysf9000287&detailFrom=2","return_url":"https://goudaai.com/home","opened":true}
```

AgentOS `RUN_ERROR` 使用字符串错误码时，`payment_required.code` 保留为
`insufficient_credits`，其余字段和处理方式相同。

`opened=false` 只表示宿主没有成功拉起浏览器，不能解释为支付失败；此时手动打开
`url`。支付完成后回到 `return_url`，按够搭网页提示确认支付，再在原 Conversation 中创建新的
Turn。支付门槛不是网络中断，不要用 `resume` 重试失败的原 Turn，也不要自动声称支付成功。

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
