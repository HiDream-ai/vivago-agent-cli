# 命令与输出

所有命令都从 Skill 根目录执行：

```bash
node scripts/gouda-agent.js doctor
node scripts/gouda-agent.js auth status
node scripts/gouda-agent.js auth login
node scripts/gouda-agent.js auth refresh
node scripts/gouda-agent.js auth logout

node scripts/gouda-agent.js project create --name "<name>"
node scripts/gouda-agent.js project list [--page-no 0] [--page-size 20]
node scripts/gouda-agent.js project detail --project-id "<id>"
node scripts/gouda-agent.js project assets [--offset 0] [--page-size 20]
node scripts/gouda-agent.js project link --project-id "<id>" --conversation-id "<id>"

node scripts/gouda-agent.js ask \
  (--project-id "<id>" | --conversation-id "<id>") \
  --prompt "<task>" [--image-search] [--file "<absolute-path>"]...

node scripts/gouda-agent.js resume --turn-id "<id>" [--last-event-id "<id>"]
node scripts/gouda-agent.js cancel --conversation-id "<id>" --turn-id "<id>"
node scripts/gouda-agent.js history --conversation-id "<id>" [--page-no 0] [--page-size 20]

node scripts/gouda-agent.js artifact url \
  --media-type <image|video|audio|document> --content-id "<id-or-url>"

node scripts/gouda-agent.js artifact preview \
  --media-type <image|video|audio> --content-id "<id-or-url>"

node scripts/gouda-agent.js artifact download \
  --media-type <image|video|audio> --content-id "<id-or-url>" \
  --output "<absolute-path>"

node scripts/gouda-agent.js state list
node scripts/gouda-agent.js state show --turn-id "<id>"
```

`--json` 和 `--jsonl` 可作为第一个兼容参数，但不影响输出：普通命令始终是一行 JSON，流式
命令始终是 JSONL。

不要用 `node -e` 重新实现调用，不要把 prompt 或路径拼进 shell 程序，不要从自由文本中抓取
ID；只解析 JSON 字段。

## 流中断

可恢复中断的最后一行：

```json
{"type":"stream_error","conversation_id":"...","turn_id":"...","last_event_id":"...","error":{"code":"STREAM_ENDED_EARLY","message":"..."}}
```

退出码为 50。`state show --turn-id ...` 可读取同一游标。恢复请求的 `messages` 为空，只发送
原 `turnId` 和可选 `lastEventId`。
