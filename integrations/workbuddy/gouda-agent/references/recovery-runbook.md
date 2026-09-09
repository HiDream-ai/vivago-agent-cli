# 任务恢复手册

用于处理视频长任务、宿主超时、SSE 中断、WorkBuddy 重启和上下文压缩。

## 独立状态文件

脚本自动把恢复信息写入：

```text
~/.workbuddy-skills/gouda-agent/state.json
```

查看任务：

```bash
node scripts/gouda-agent.js state list
node scripts/gouda-agent.js state show --turn-id "<turn-id>"
```

每条状态只包含 `project_id`、`conversation_id`、`turn_id`、`last_event_id`、`status` 和时间。
prompt、完整消息和服务端响应不写入本地，因此不会形成第二份 transcript。

## 视频后台执行

视频 Turn 常见需要 15–40 分钟，可能超过 WorkBuddy 单次 Bash 调用的前台等待时间。优先使用
宿主提供的后台执行能力；没有专用能力时，可把 JSONL 写到当前工作目录的临时日志：

```bash
node scripts/gouda-agent.js ask \
  --project-id "<project-id>" --prompt "<brief>" \
  > "./gouda-turn-<timestamp>.jsonl" 2>&1 &
```

从首行读取 `session`，之后只转述阶段变化。日志是临时运行输出，不是永久记录；处理终态后删除，
不得把它升级成新的聊天历史库。若宿主不保证后台进程存活，依赖状态文件中的 Turn ID 和游标恢复，
不能重复提交 prompt。

## SSE 中断恢复

长任务可能多次断开。退出 50 或 `stream_error` 是继续信号，不是远端失败：

```bash
node scripts/gouda-agent.js resume \
  --turn-id "<turn-id>" --last-event-id "<last-event-id>"
```

持续使用最新 `last_event_id`，按 `event_id` 去重，直到看到 `RUN_FINISHED` 或 `RUN_ERROR`。
连续数次立即断开时降低恢复频率，至少间隔 30 秒，并告诉用户远端任务仍可能在运行。任何情况
都不能用重新提交原 prompt 来检查任务。

## 重新进入 WorkBuddy

1. 运行 `state list`，找到 `running` 或 `interrupted` 状态。
2. 有 Conversation ID 时运行 `history --conversation-id "<conversation-id>"` 判断当前状态。
3. 仍在运行：使用保存的 Turn ID 和游标继续 `resume`。
4. 已经完成：从收尾消息和 `project assets` 恢复 `content_id`，再按交付手册预览和验证。
5. 已失败：向用户说明服务端终态；除非用户确认，不重新提交任务。

## Project Conversation 冲突

`PROJECT_CONVERSATION_CONFLICT` 表示该 Project 已经关联多个 Conversation，当前 prompt 尚未
提交且没有因此消耗生成额度。可以从状态或历史中选择明确的 Conversation，使用
`ask --conversation-id ...` 继续；或者在用户同意后创建新 Project。不要重试同一 Project ID。

## 取消

只在用户明确要求时运行：

```bash
node scripts/gouda-agent.js cancel \
  --conversation-id "<conversation-id>" --turn-id "<turn-id>"
```

接口返回只表示取消请求被受理。看到终态前不得把状态报告为已经停止。
