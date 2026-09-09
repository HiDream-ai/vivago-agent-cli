---
name: gouda-agent
display_name: 够搭 Agent
display_name_en: Gouda Agent
description: 当用户明确要求够搭 Agent 完成图片、视频或其他创意生产任务，或者要求继续、恢复、取消、查询够搭 Agent 任务时使用。通过国内够搭服务委派完整任务，不暴露内部工具。
description_zh: 够搭 Agent 是一站式 AI 创意生产引擎，可将文字与参考素材快速转化为高质量图片、视频等内容，支持复杂任务持续执行、断点恢复与成果交付，让创意从灵感到成品一步完成
description_en: Gouda Agent is an end-to-end AI creative production engine that turns prompts and reference assets into high-quality images and videos, with long-running task continuation, recovery, and result delivery
category: 创意工具
version: 1.0.0
author: HiDream.ai
allowed-tools: Bash
---

# 够搭 Agent 任务委派

使用本 Skill 自带的 `node scripts/gouda-agent.js ...` 作为唯一集成边界。不要搜索、安装或
调用 Go CLI、六平台二进制和 npm 依赖，不要自行拼接 HTTP 请求，也不要调用、枚举或猜测
够搭 Agent 内部的 MCP 工具和 Skill。

脚本固定连接国内正式环境。以脚本配置的 API、登录地址和返回链接为准，不增加环境切换参数，
不改写 origin，也不调用未配置的接口。回复用户时使用用户当前使用的语言；命令、标识符和文件
路径保持原样。

详细流程放在本文件旁边的 `references/`，到对应阶段再读取：

- @references/brief-guide.md — 编写图片和视频 brief 前读取
- @references/recovery-runbook.md — 视频后台执行、流中断、任务恢复或重新进入时读取
- @references/output-shapes.md — 解析命令 JSON/JSONL 输出和查找最终产物时读取
- @references/delivery-playbook.md — 收到终态后校验、预览和交付产物时读取
- @references/capability-limits.md — 用户要求字幕、音效、指定 TTS 声音或其他边界能力时读取
- @references/commands.md — 需要确认命令、参数和退出码时读取
- @references/authentication.md — 需要登录、刷新、退出或排查认证问题时读取
- @references/api-contract.md — 排查协议或国内外接口差异时读取
- @references/security-and-privacy.md — 涉及凭证、本地文件、数据范围或安全说明时读取

## 运行环境检查

本 Skill 需要 Node.js 18 或更高版本。首次使用先运行：

```bash
node scripts/gouda-agent.js doctor
```

登录依赖当前设备上的默认浏览器和本机 `127.0.0.1` 回调。如果 WorkBuddy 运行在容器、远程
沙箱或无法打开用户本机浏览器的环境，不要降级成 curl 或要求用户复制凭证；说明必须在本地
桌面版 WorkBuddy 中完成登录。

## 前置检查

1. 运行 `node scripts/gouda-agent.js auth status`。
2. 如果未登录，先告诉用户即将打开够搭登录页，再运行
   `node scripts/gouda-agent.js auth login`。若 stderr 返回手动登录 URL，只把它交给当前用户
   打开；不要代填账号，不要要求用户复制 ticket 或 refresh token。
3. 登录成功后立即告知用户并继续原任务，不要停在登录结果。
4. 运行 `node scripts/gouda-agent.js state list`。如果存在未完成 Turn，先说明发现的状态并
   优先恢复，不要重复提交原 prompt。

WorkBuddy 的登录和任务状态保存在独立命名空间，不读取或修改现有 Go CLI 的凭证与状态。

## 提交前

- 在线图片搜索是每个新 Turn 的显式能力。只有用户要求查找在线图片、视觉参考，或明确授权
  在线视觉素材发现时才增加 `--image-search`。生成图片或视频本身不构成搜索授权。
- 一次性确认真正影响结果的硬约束：视频总时长、比例或目标平台、参考图片或素材、配音和字幕
  需求。不要替用户发明硬约束；用户不指定时，说明采用的默认值。
- 视频会消耗真实额度，常见耗时约 15–40 分钟。提交前用一条消息概括总时长、比例、场景数和
  关键内容；发生 `RUN_ERROR` 后再次提交也要重新概括并取得用户确认。
- 按 @references/brief-guide.md 编写 brief。视频分镜使用编号场景，不写逐场景时间戳；总时长
  只在整体要求中写一次；有参考图时写清外观锁定；配音逐句写出。
- 图片任务走轻量流程，不询问视频时长、分镜、配音等无关参数。

## 创建并提交任务

用户没有提供 Project ID 时，创建一个名称简短且不含敏感信息的 v3 Project：

```bash
node scripts/gouda-agent.js project create --name "<简短名称>"
```

提交新任务：

```bash
node scripts/gouda-agent.js ask --project-id "<project-id>" --prompt "<完整任务>"
```

当前 Turn 获得在线视觉搜索授权时增加：

```bash
node scripts/gouda-agent.js ask --project-id "<project-id>" \
  --image-search --prompt "<完整任务>"
```

每个用户授权的本地附件单独增加一个 `--file "<绝对路径>"`。不要把本地路径写进 prompt
代替附件，也不要扩大到用户未授权的工作区文件。附件只使用脚本内置的阿里云 OSS STS
流程上传，不自行替换上传接口。

脚本执行一 Project 一 Conversation 约束。如果退出 30 且错误为
`PROJECT_CONVERSATION_CONFLICT`，说明 prompt 尚未提交、没有因此消耗生成额度；按
@references/recovery-runbook.md 处理，不要继续重试同一 Project ID。

`ask` 第一条 JSONL 记录为 `session`。脚本会立即把 Project、Conversation、Turn 和游标写入
独立状态文件，不需要另建聊天记录或把 prompt 写入本地 ledger。

视频 Turn 应使用 WorkBuddy/Bash 支持的后台执行方式，避免宿主命令超时中断前台对话；具体
方式和恢复规则见 @references/recovery-runbook.md。图片任务通常约一分钟，可以前台执行。
提交视频后立即告诉用户任务已经开始，并给出预计时间范围。

## 运行期间

- 只在阶段变化时转述里程碑，例如分镜完成、片段生成进度、开始合成。不要转发内部工具名、
  原始事件或重复快照，长任务也不要一直沉默。
- 发现面向用户的问题时立即询问用户，不得自行回答。用户答复后，在同一 Conversation 中创建
  新 Turn。
- 用户询问状态时，根据最后一条事件和本地状态回答；不要为查询状态创建新 Turn、重提 prompt
  或执行取消。
- 用户中途修改需求时，先判断是否会使当前产物失效。只有用户明确要求取消时才调用 `cancel`；
  否则让当前 Turn 完成后在同一 Conversation 迭代。

## 校验和交付

只有看到 `RUN_FINISHED` 才能报告成功，`RUN_ERROR` 是业务失败。远端完成摘要不是交付证据；
按 @references/delivery-playbook.md 校验最终文件是否符合 brief。

拿到图片、视频或音频 `content_id` 后，先创建本地预览：

```bash
node scripts/gouda-agent.js artifact preview \
  --media-type <image|video|audio> --content-id "<content-id>"
```

只有用户要求保存到明确位置时才使用：

```bash
node scripts/gouda-agent.js artifact download \
  --media-type <image|video|audio> --content-id "<content-id>" \
  --output "<绝对路径>"
```

优先展示最终产物，过程图片、分镜和被淘汰候选只在用户要求时展示。图片有多个候选时全部展示，
由用户选择。宿主不能内联渲染时，如实提供本地路径，不要声称已展示，也不要把远程 URL 当成
主要预览。

最终同时提供国内 Project 深链：

```bash
node scripts/gouda-agent.js project link \
  --project-id "<project-id>" --conversation-id "<conversation-id>"
```

交付时主动说明可以在同一 Conversation 复用已有镜头继续修改，并提供 Project 深链供协作。

## 继续、恢复和取消

- 修改成品时使用 `ask --conversation-id "<conversation-id>"`，并指出可复用的既有素材；不要
  为普通修改创建新 Project。
- 退出 50 或最后一行为 `stream_error` 表示本地 SSE 中断，远端可能仍在运行。使用同一
  `turn_id` 和已保存的 `last_event_id` 恢复，绝不重新提交原 prompt。
- 重新进入 WorkBuddy 后先运行 `state list`，再结合 `history`、`resume` 和 `project assets`
  恢复；完整步骤见 @references/recovery-runbook.md。
- 只有用户明确要求时才执行 `cancel`。取消响应只是异步受理，看到终态前不要声称已经停止；
  已消耗的生成额度不会退回。
- 服务端拥有完整历史。本地只保存恢复需要的标识符、游标、状态和时间，不维护第二份 transcript。

## 输出和错误

普通命令输出一条 JSON envelope，`ask` 和 `resume` 输出 JSONL。按
@references/output-shapes.md 解析字段，不从自由文本抓取 ID。

- 退出 10：参数错误，修正命令后再执行。
- 退出 20：认证失效，告知用户将打开浏览器并重新登录。
- 退出 30：服务端业务失败；说明错误，不得自行重试或重复消耗额度。
- 退出 40：Node.js 或本地依赖不可用；展示 `doctor` 结果。
- 退出 50：流或网络中断；按原 Turn 游标恢复，不能重提 prompt。

已知能力限制及宿主侧补救见 @references/capability-limits.md。任何情况下都不得输出 ticket、
refresh token、Cookie、Authorization、阿里云 AccessKey、STS token、签名 URL 或本地凭证
文件内容。
