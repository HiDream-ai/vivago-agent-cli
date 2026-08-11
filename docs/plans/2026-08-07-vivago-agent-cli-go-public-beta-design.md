# VivagoAgent Go CLI 与六平台插件公开 Beta 设计

正式版上线门槛和后续工作见
[`2026-08-07-vivago-agent-cli-public-ga-gap-analysis.md`](2026-08-07-vivago-agent-cli-public-ga-gap-analysis.md)。
公司 GitHub、个人 Dev 通道、生产 Beta CI、公开仓库门禁和回滚设计见
[`2026-08-11-vivago-agent-cli-public-beta-release-design.md`](2026-08-11-vivago-agent-cli-public-beta-release-design.md)。
前端登录页的参数、Form POST 和联调范围见
[`2026-08-07-vivago-agent-login-frontend-integration.md`](2026-08-07-vivago-agent-login-frontend-integration.md)。

## 背景

当前 `vivago-agent-cli` 已经验证了 `Codex / Claude Code → Skill → 本地 CLI → VivagoAgent REST/SSE` 这条路径。项目、会话、Turn 和历史仍由 VivagoAgent 保存，插件只负责把宿主的粗粒度任务交给 VivagoAgent，不暴露内部业务 MCP 工具。

现有 Pilot 使用 Python CLI 和独立的 `vivago-client`，通过 PyInstaller 打成 macOS Apple Silicon 运行时。这套方式适合内部验证，但要交给外部普通用户使用，会遇到三个实际问题：只覆盖一个平台、插件包里存在两套 Python 运行时、现有 CLI 登录仍使用固定 `50366` 端口并把凭证放在回调 URL 中。

公开 Beta 改为 Go 实现，在插件中内置六个 OS/CPU 目标的二进制：macOS、Linux 和 Windows 均支持 ARM64 与 x64。开发和测试阶段可以使用个人 GitHub 和海外测试环境；开始对外发布 Beta 后，安装源切换到公司 GitHub，公开二进制只访问海外正式环境。用户第一次使用时完成一次 Vivago 网页登录，不需要安装 Go、Python、pip、`vivago-agent` 或 `vivago-client`。

## 方案概述

### 一句话设计

用一个内置登录能力的 Go CLI 替换现有 Python CLI 和 `vivago-client`，插件启动器按用户的操作系统和 CPU 选择对应二进制。开发包固定访问海外测试环境，公开 Beta 包由公司 GitHub 重新构建并固定访问海外正式环境。

### 运行链路

```text
Codex / Claude Code
  → VivagoAgent Skill
  → 插件启动器识别 OS/CPU
  → 对应平台的 vivago-agent Go 二进制
      ├─ 网页登录、刷新和本地凭证存储
      └─ 当前构建对应环境的 REST/SSE、上传和产物下载
  → VivagoAgent 保存项目、会话、Turn 和历史
```

公开插件不包含 Python Runtime、`vivago-client`、Hosted MCP Server 或任何业务 MCP 工具，也不在本地保存第二份会话历史。

## 开发测试和公开 Beta 使用不同环境

环境和发布仓库按阶段隔离。开发人员不能通过运行时参数切换环境，公开 Beta 也不能复用个人 GitHub 构建出来的二进制。

| 阶段 | 代码和插件来源 | API 环境 | 使用范围 |
|---|---|---|---|
| 开发、联调和完整 E2E | 个人 GitHub 或本地开发仓库 | 海外测试环境（现有 `overseas-dev`） | 研发、QA 和内部测试账号 |
| 公开 Beta 候选包 | 公司 GitHub，由公司 CI 重新构建 | 海外正式环境 | 发布前受控冒烟 |
| 公开 Beta | 公司 GitHub Release 和 Marketplace | 海外正式环境 | 外部普通用户 |

个人 GitHub 可以发布带 `dev` 标识的开发插件和预发布包，开发 Marketplace 使用 `vivago-dev` 等明显不同的名称，不能占用 `vivago` 正式名称，也不能生成对外 Beta Tag。待发布代码通过 PR、镜像同步或固定 commit 进入公司 GitHub，最终以公司仓库中经过评审的 commit 为准。

发布入口按仓库固定：个人 GitHub 的手动 Release Workflow 只接受 `v0.3.0-dev.N` 并更新
`dev-marketplace`；公司 GitHub 的手动 Release Workflow 只接受 `v0.3.0-beta.N`，使用
`prod` profile 重新构建，并在生产审批后更新 `marketplace`。普通 Push 和 Pull Request 只运行
只读检查，不发布可安装版本。两条 Release Workflow 都不提供 profile、环境地址、Marketplace
名称或 channel 输入，仓库身份不匹配时直接失败。

同一份源码保留两套构建配置，不提供运行时 `--env`：

- 开发/测试构建显式选择 `dev` profile，只编入海外测试环境地址，凭证命名空间使用 `vivago-agent/dev`。
- 公司 Beta 构建显式选择 `prod` profile，只编入海外正式环境地址，凭证命名空间使用 `vivago-agent/prod`。
- 没有选择 profile 或同时选择两个 profile 时构建失败，避免研发本机默认打出指向正式环境的包。
- 海外测试地址通过本地未跟踪配置或个人 GitHub 的受保护 CI 配置注入，不进入公开 Beta 插件包。
- 公司 GitHub CI 不接受外部上传的二进制，只从公司仓库的受保护 Tag 重新构建六个平台产物。

公开 Beta 固定使用以下地址：

```text
Web/API:  https://vivago.ai
登录页:   https://vivago.ai/agent/login
刷新接口: https://vivago.ai/prod-api/user/apikey2token
图片:     https://storage.vivago.ai
视频音频: https://media.vivago.ai
```

实现要求：

- 删除全局 `--env` 参数和所有环境选择逻辑。
- 删除 `VIVAGO_AGENT_BASE_URL` 等运行时 Origin 覆盖能力。
- 开发和 Beta 构建都在编译时确定 profile，运行后不能切换。
- Beta 二进制和插件包中不包含海外测试、国内开发和国内正式域名。
- 单元测试通过构造函数注入本地 Mock Server，不为测试在公开二进制中保留环境切换入口。
- API 重定向只允许同 Origin；跨 Origin 时绝不转发 `Authorization`。
- 上传和下载 URL 只允许 HTTPS，并拒绝 loopback、私网、链路本地地址以及利用重定向绕过检查的请求。
- 保留 `X-Source: cli` 和 `X-Client-Platform: web`，增加不含个人信息的 `X-Client-Version` 和版本化 `User-Agent`。

开发凭证和正式凭证使用不同的系统凭证条目，任何一方都不迁移、读取或覆盖另一方。这样既能在海外测试环境完成开发和完整 E2E，也能避免海外正式凭证被误发到测试或国内环境。

## Go CLI 怎么拆

Go 工程按职责拆分，避免把登录、协议映射和命令处理重新写成一个大文件：

```text
cmd/vivago-agent       命令入口
internal/cli           参数、机器输出和退出码
internal/auth          登录、刷新和 AuthProvider
internal/credential    系统凭证库与 Linux 文件降级
internal/client        VivagoAgent REST/SSE 请求与响应映射
internal/attachment    本地附件格式、数量、大小和文件类型校验
internal/upload        预签名 URL 的安全流式 PUT
internal/sse           SSE 解析和终态识别
internal/artifact      产物 URL 校验和本地落盘
```

`AuthProvider` 继续保留为 Go interface。开发构建只链接海外测试登录配置，公开 Beta 构建只链接 `ProductionWebAuthProvider`；两者由编译 profile 决定，不能在运行时切换。后续如果引入标准 OAuth，可以替换这一层，不需要修改项目、会话和 Turn 协议。

## CLI 来源如何传到服务端

`platform` 继续表示 Web、iOS、Android 等产品数据范围，`source` 表示这次请求从哪个入口发起。CLI 请求固定使用：

```http
X-Source: cli
X-Client-Platform: web
X-Client-Version: <semver>
User-Agent: vivago-agent-cli/<semver> (<os>; <arch>; <host>)
```

不能把 `platform` 改成 `cli`。VivagoAgent 当前按 `platform=web` 读取 Web 项目和资产；如果把 CLI 当成一个新平台，CLI 创建的内容可能无法在 Web 端看到。`source=cli` 只用于来源归因，不改变项目、会话和产物的 Web 可见性。

### VivagoAgent 怎么读取来源

VivagoAgent 增加统一的 `get_client_source(request)`，只在一个位置读取和规范化 `X-Source`：

- 去掉首尾空白并转成小写；
- 第一版只识别 `cli`；
- Header 缺失时返回空值，保持现有 Web/App 请求行为；
- 未识别值不参与授权、计费或数据过滤，只记录一个低基数的 `unknown` 监控计数；
- `X-Source` 是客户端自报信息，可以用于统计和排障，不能作为用户身份、权限或套餐判断依据。

`X-Client-Platform` 仍走现有平台规范化逻辑。CLI 必须发送 `web`，服务端落库时也必须保持 `platform=web`。

### 哪些数据增加 source

`source` 只记录 Agent 主链路的入口来源，第一版增加到三个 Mongo collection：

| Mongo collection | source 的写入时机 | CLI 写入值 |
|---|---|---|
| `projects` | 创建项目时 | `cli` |
| `conversations` | 创建会话时 | `cli` |
| `turns` | 每次提交 Turn 时 | `cli` |

Project 和 Conversation 记录创建来源，之后不会因为用户换入口而覆盖。Turn 按每次请求记录来源：同一 Conversation 可以由 CLI 创建，之后在 Web 端继续，此时新 Turn 使用 Web 请求对应的来源，不继承旧 Turn 的 `source=cli`。

`platform` 保持当前逻辑不变。CLI 创建 Project 和 Turn 时仍写入 `platform=web`；Conversation 当前没有 `platform`，只增加 `source`。ProjectAsset、UserAsset 和 CustomWorkflow 不增加 `source`：资产来源可以通过已有的 `project_id`、`conversation_id` 和 `turn_id` 追溯，CustomWorkflow 不在 CLI 公开 Beta 主链路中。

旧 Project、Conversation 和 Turn 缺少 `source` 时按“历史来源未知”读取，不做全量迁移。第一版不在公开 API 增加按 `source` 筛选项目或资产的参数，也不为尚未存在的查询提前增加索引；运营或排障需要长期按来源查库时，再根据真实查询补充索引。

### 日志、监控和限流怎么记录

- 请求完成日志增加规范化后的 `client_source`、CLI 版本和 request ID，不记录 Prompt、Token、Cookie、Authorization、文件内容或完整预签名 URL。
- VivagoAgent 的项目创建、会话创建、Turn 提交、SSE 终态、恢复、取消和资产访问指标增加低基数 `client_source=cli|unknown` 标签。网页登录和 Token 刷新发生在 Web/用户服务，由对应服务单独统计，不归到 VivagoAgent 指标中。
- 限流命中、拒绝和放行指标记录 `client_source`，但现有按用户执行的全局限流键不按来源拆分，避免用户通过切换 Web/CLI 绕过并发和配额限制。
- 后续如果需要给 CLI 单独设置限流，必须同时执行用户全局限制和 CLI 来源限制，最终取更严格的结果。

### 兼容和验收

这项改造不改变现有 REST/SSE 请求体、响应体和错误码。验收至少覆盖：

1. CLI 创建的 Project、Conversation 和 Turn 均落库 `source=cli`。
2. CLI 创建的 Project 和 Turn 仍为 `platform=web`，项目和产物可以从 Web 端正常列出和打开。
3. 同一 Conversation 从 CLI 切换到 Web 后，新 Turn 不会错误继承 `source=cli`。
4. 不带 `X-Source` 的 Web/App 请求保持现有行为，历史无 `source` 数据可以正常读取。
5. 日志和指标能按 `client_source=cli` 统计，且不包含凭证、Prompt 或文件内容。
6. 修改或伪造 `X-Source` 不能改变用户身份、数据权限、套餐和全局限流结果。
7. ProjectAsset 和 UserAsset 不新增 `source`，仍能通过 Project、Conversation 和 Turn 标识追溯到入口来源。

### 命令兼容

除删除 `--env` 外，保留现有命令：

```text
version
doctor
auth login|status|logout
project create|list|assets|link
ask
resume
cancel
history
artifact url|download|preview
```

兼容规则：

- 保留 `--json`、`--jsonl`、JSON Envelope 和现有退出码。
- stdout 只输出 JSON/JSONL；诊断、浏览器提示和人工操作说明写 stderr。
- `RUN_FINISHED` 返回 0，`RUN_ERROR` 返回 30。
- SSE 断流返回 50，并输出 `conversation_id`、`turn_id`、`last_event_id`。
- 断流后只能对原 Turn 执行 `resume`，禁止自动重新提交原 Prompt。
- `input_required` 由 Skill 向用户补充提问，之后在同一 conversation 中提交下一轮消息。

### 联网图片搜索

VivagoAgent Web v2 Chat 已支持按 Run 开启联网图片和视觉素材搜索。CLI 在 `ask` 命令增加显式
`--image-search` 开关，并严格映射为请求体顶层的 `imageSearchEnabled: true`：

- 该能力是图片/视觉参考搜索，不宣传为通用网页文字检索或事实搜索。
- 默认关闭；关闭时省略请求字段，保持旧客户端行为和服务端默认值。
- 开关按新 Run 生效。使用 `--project-id` 创建首个 Turn，以及使用 `--conversation-id` 在原会话
  创建后续 Turn 时都可以显式开启。
- `resume` 只恢复同一 Turn 的 SSE，不接受也不发送图片搜索开关。
- `imageSearchEnabled` 只能位于 Chat 请求顶层，不能放入 `state`、`forwardedProps` 或 Skill 参数。
- Skill 只在用户明确要求搜索在线图片、视觉参考，或明确授权联网寻找视觉素材时添加开关；不能因为
  最终产物是图片或视频就自动开启。

本地验收覆盖默认省略、显式开启、同会话新 Turn、断流恢复不重复提交，以及真实海外测试环境中能够
观察到联网视觉搜索行为。该功能不进入 Hosted Runner 的账号测试矩阵，避免把外部搜索波动作为发布
流水线稳定性依赖。
- ticket、refresh token、Cookie、Authorization header 和完整预签名 URL不得进入 stdout、stderr、异常或测试快照。

Go 版 `ask` 使用 `--jsonl ask --prompt <text>`，并且必须且只能选择
`--project-id` 或 `--conversation-id` 之一。按项目发起时，CLI 先调用 Web v1
`/project/detail`：没有会话才携带 `projectId` 创建会话，只有一个会话时改为携带该
`threadId`，多个会话时在提交 SSE 前返回 `PROJECT_CONVERSATION_CONFLICT`。每条用户消息使用
安全随机生成的 UUID v4，正文按 Web v2 的结构化文本 content 发送，不携带业务工具定义。

`resume` 使用 `--jsonl resume --turn-id <turn>`，可选 `--last-event-id <cursor>`；请求体的
`messages` 必须为空，只携带原 `turnId` 和游标。服务端没有重复返回 Turn 响应头时，CLI 继续使用
调用方提供的原 `turn_id`。非 EOF 的底层 SSE 读取错误也只输出固定的可恢复错误，不把网络库原始错误
写入机器输出，避免凭证或 URL 通过异常文本泄漏。

`project assets`、`cancel` 和 `history` 继续调用 Web v1/v2 既有接口。资产列表的 `offset` 可省略，
省略时请求体显式发送 `null` 以保持 Pilot 契约；提供时必须是非负整数。项目列表、资产列表和历史列表的
`page_size` 统一限制为 1～100，页码不能为负。`cancel` 必须同时携带 conversation 和 turn 标识，
不会根据本地状态猜测当前 Turn。

`doctor` 不再检查 Python 和 `vivago-client`，改为输出：

- 当前 OS/CPU 是否有匹配二进制；
- CLI 版本、Git SHA 和构建目标；
- 当前构建渠道和目标环境；公开 Beta 必须显示为公司构建、海外正式；
- 系统凭证库是否可用；
- Linux 是否正在使用 `0600` 文件降级；
- 当前登录状态，但不显示 Token 或用户隐私信息。

### 项目链接不能由 Skill 自己拼

生产用户最终看到的项目链接必须由 CLI 根据编译时 profile 生成，不能让 Skill 在
`dev.vivago.ai` 和 `vivago.ai` 之间自行判断。否则即使 API 和登录地址已经通过 `prod` build tag
固定，宿主 Agent 仍可能从 Markdown 示例中选错域名，把测试环境链接返回给生产用户。

第一版增加本地命令：

```text
project link --project-id <project-id> --conversation-id <conversation-id>
```

该命令不访问服务端，只使用编译时固定的 Web 域名生成完整 `deep_link`。机器输出继续使用 JSON
Envelope，返回 `project_id`、`conversation_id`、`deep_link` 和编译 profile。Skill 在交付结果时只能
原样展示 CLI 返回的 `deep_link`，不得读取 Markdown 中的域名映射，也不得手工替换 origin。

`Profile` 除 `APIBaseURL` 和 `LoginURL` 外增加独立的 `WebBaseURL`：开发构建固定为
`https://dev.vivago.ai`，`prod` 构建固定为 `https://vivago.ai`。三类地址都由 build tag 决定，运行时
不提供覆盖参数或环境变量。

插件内的 `SKILL.md` 和 references 使用环境无关描述，不出现 `dev.vivago.ai`、`overseas-test` 等
开发环境字面量。开发包和生产包共用同一份 Skill 文档，具体环境只由内置二进制决定。

## 登录怎么改

### 登录入口

公开 Beta 使用独立的 VivagoAgent CLI 登录页，不改造旧 `/login-cli`，也不兼容旧 `vivago-client` 回调：

| 构建 profile | 登录入口 |
|---|---|
| `dev` | `https://dev.vivago.ai/agent/login` |
| `prod` | `https://vivago.ai/agent/login`，由海外 Web 团队在正式发布前确认并上线 |

新页面复用 Vivago 现有邮箱、Google、Apple、Discord 等登录能力，但参数校验和登录结果回调按 CLI 专用协议实现。公开 Beta 不建设新 OAuth Server，不要求用户中心新增接口，也不修改现有账号体系和 `/prod-api/user/apikey2token`。

### 新登录流程

1. Go CLI 先在 `127.0.0.1` 监听一个系统分配的随机端口。
2. CLI 使用安全随机数生成 32 字节 `state`。
3. CLI 打开当前编译 profile 对应的登录页。公开 Beta 的地址为：

   ```text
   https://vivago.ai/agent/login
     ?client=vivago-agent-cli
     &callback_port=<port>
     &state=<state>
   ```

4. 用户继续使用现有 Vivago 登录方式。已经登录的用户直接进入回调流程，未登录用户完成登录后进入相同流程。
5. 登录成功后，Web 页面只能向以下固定地址提交回调：

   ```text
   http://127.0.0.1:<callback_port>/callback
   ```

6. Web 页面通过 HTML Form POST 提交：

   ```text
   ticket=<ticket>
   refresh_token=<refresh_token>
   state=<state>
   ```

7. Go CLI 校验请求来自 loopback、Method 为 POST、Path 为 `/callback`、Body 不超过 64 KiB，并使用常量时间比较 `state`。
8. `state` 只能消费一次；校验成功后立即停止监听。
9. CLI 返回一个不包含凭证的本地成功或失败页面，保存凭证，然后继续用户原来的任务。

登录页不能接收任意 callback URL。它只接受合法数字端口，Host 固定为 `127.0.0.1`，Path 固定为 `/callback`。登录 URL 中只有端口和 `state`，没有任何凭证，因此浏览器无法自动打开时可以安全地把 URL输出到 stderr 让用户手动复制。

登录等待时间为 5 分钟，支持 Ctrl+C 取消。登录失败、端口异常、回调不合法或 `state` 不匹配时，CLI 必须停止当前命令，不创建项目、不上传文件、不提交任务。

### Web 页面和 CLI 各自负责什么

- Web 校验 `client`、`callback_port` 和 `state`，只允许向固定格式的 `http://127.0.0.1:<port>/callback` 提交。
- Web 使用普通 HTML Form POST，不使用 `fetch`、iframe 或 `postMessage`，不读取 callback 响应，也不维护本地处理状态。
- Web 防止登录成功事件重复提交，并保证凭证不进入 URL、控制台、埋点、Sentry 或错误信息。
- CLI 校验 Method、Path、Body 大小、必填字段和一次性 `state`，负责凭证保存、本地结果页面、超时和终端退出码。
- `/agent/login` 的上线和回滚不影响站内旧登录页；Go CLI 不调用 `/login-cli`。

### Token 刷新与退出

ticket 在过期前 60 秒视为需要刷新，继续使用现有接口：

```text
GET /prod-api/user/apikey2token
Refresh-Token: <refresh_token>
```

刷新遇到瞬时网络错误时重试一次；服务端确认 refresh token 无效后，清除本地凭证并重新打开浏览器。业务写请求不能因为刷新或网络错误自动重试，避免重复创建项目或提交任务。

`auth logout` 第一版只删除本地凭证。现有服务没有 refresh token 撤销接口，因此服务端撤销不放在本期；如果后续面向企业用户发布，需要补充撤销能力。

## 凭证存在哪里

优先使用操作系统凭证库：

- macOS：Keychain
- Windows：Credential Manager
- Linux：Secret Service

Go 客户端使用固定版本 `github.com/zalando/go-keyring v0.2.8` 作为系统凭证库适配器。选择该实现是为了保持六个平台 `CGO_ENABLED=0` 的静态构建：macOS 通过系统自带的 `/usr/bin/security -i` 访问 Keychain，凭证写入子进程 stdin，不进入命令行参数；Windows 通过 WinCred API；Linux 通过 Secret Service D-Bus。CLI 在自己的 `SystemKeyring` 边界内统一错误语义，不能把依赖错误中的凭证内容输出到 stdout 或 stderr。

开发和正式凭证使用不同标识：

```text
开发包：service=ai.hidream.vivago-agent.dev  account=overseas-dev
Beta 包：service=ai.hidream.vivago-agent      account=overseas-prod
```

Linux 或 WSL 没有 Secret Service 时，允许降级到：

```text
~/.config/vivago-agent/credentials-dev.json
~/.config/vivago-agent/credentials-prod.json
```

降级文件所在目录权限为 `0700`，文件权限为 `0600`，并使用同目录临时文件加原子替换写入。`auth status` 和 `doctor` 要明确提示当前正在使用文件存储，但不能输出凭证内容。

文件降级只适用于 Linux 和 WSL。macOS 必须使用 Keychain，Windows 必须使用 Credential Manager；系统凭证库被禁用、锁定或不可访问时，CLI 返回可操作的依赖错误，不得静默把凭证改写到普通文件。第一版支持 macOS 13+ 的 Intel/Apple Silicon、Windows 10/11 的 x64/ARM64，以及 Linux、WSL2 的 x64/ARM64。

登录和刷新使用跨平台文件锁，避免多个 Codex/Claude 会话同时打开浏览器或覆盖 refresh token。

跨进程锁固定使用 `github.com/gofrs/flock v0.13.0`。开发和正式 profile 使用不同锁文件 `auth-dev.lock`、`auth-prod.lock`，锁文件不保存凭证。macOS/Linux 的锁目录权限为 `0700`、锁文件权限为 `0600`；Windows 使用用户 `%AppData%` 下的配置目录和 Windows 文件锁，不套用无效的 POSIX mode 校验，但仍拒绝符号链接、目录和非普通文件。登录在持锁期间完成浏览器打开、回调等待和凭证保存；刷新在持锁后必须重新读取凭证，若其他进程已经刷新则直接复用新 ticket，不再次请求刷新接口。

Go CLI 不迁移 Python Pilot 或 `vivago-client` 的本地凭证。已有 Pilot 用户第一次使用 Go 版本时重新登录，避免读取旧文件格式、扩大凭证访问范围和引入只服务内部用户的迁移代码。开发包不读取正式凭证，Beta 包也不读取 `overseas-dev`、`domestic-dev` 和 `domestic-prod` 凭证；两个渠道首次使用时分别登录自己的环境。

## REST、SSE、上传和产物下载

### 请求处理

- 使用 Go `net/http` 和系统证书库，强制 TLS 校验。
- 普通 API 设置连接、响应 Header 和响应体超时。
- SSE 不设置整个任务的总时长，但连接异常结束且没有收到终态时必须输出恢复游标。
- 业务写请求不自动重试；只允许刷新 Token、查询状态和恢复原 Turn。
- API 401/403 不能在错误信息中携带请求 Header。

### 附件上传

- 保留现有图片、视频、音频、文档和字幕格式。
- 保留当前数量与大小限制，并为图片增加 50 MiB 上限。
- 使用流式上传，不能把最大 300 MiB 视频完整读入内存。
- 使用 `Lstat` 拒绝符号链接、目录、设备文件和其他非普通文件。
- 预签名上传 URL 必须是 HTTPS；DNS 解析和每次重定向都要执行私网地址检查。

Go 实现先对全部 `--file` 做完校验，再执行项目预检和任何网络请求。支持 Pilot 已有的
JPG/JPEG/PNG、MP4、MP3、DOC/DOCX/TXT/MD/PDF 和 SRT/VTT/ASS/SSA；数量上限为图片 9、
视频 1、音频 1、文档 4，且同一种文档后缀只能出现一次。大小上限为图片 50 MiB、视频
300 MiB、音频 15 MiB、文档 1 MiB。通过 `Lstat` 只接受普通文件，拒绝符号链接、目录、设备和
其他特殊文件，并在真正 PUT 前再次校验文件类型与大小，降低校验后替换风险。

上传凭证继续从 Web `/prod-api/user/google_key/{bucket}` 获取；Authorization 只发送给 Vivago
域名，预签名 URL 的 PUT 只携带 Content-Type 和 Content-Length。文件以 `os.File` 流式发送，
不把 300 MiB 视频整体读入内存。上传 URL 只允许 HTTPS 443、无 userinfo/fragment、实际拨号时
全部 DNS 结果必须是公网地址，并禁用环境代理和所有上传重定向；预签名 URL 永不进入 Chat 请求体、
stdout、stderr 或错误文本，Chat 中只保存 OSS key、媒体类型和安全的文件 basename。

### 产物下载

- 图片固定从 `storage.vivago.ai` 解析，视频和音频固定从 `media.vivago.ai` 解析。
- 如果服务端事件直接返回 URL，也必须执行协议、域名、DNS 和重定向检查，不能把任意 URL直接交给下载器。
- 下载先写同目录临时文件，成功后原子落盘，不覆盖已有文件。
- 默认下载上限：图片 100 MiB、音频 500 MiB、视频 5 GiB。
- 校验 Content-Type；失败时删除临时文件。

Go 实现对现成 URL 采用与媒体类型绑定的域名白名单：图片只能使用
`storage.vivago.ai`，视频和音频只能使用 `media.vivago.ai`，只允许 HTTPS 443 且拒绝
userinfo、fragment 和跨域/降级重定向。下载连接绕过环境代理并在实际 Dial 时重新解析 DNS；任一解析结果
属于 loopback、私网、链路本地、未指定或非全局单播地址时整体拒绝，避免“校验后再解析”的 DNS rebinding。
下载体使用流式大小上限，先写目标同目录的 `0600` 临时文件，再通过不覆盖的硬链接原子发布；目标已经存在、
Content-Type 不匹配、超过大小或中途失败时都不留下目标文件，预览文件使用独立随机临时目录。

## 插件怎么打包

`main` 分支保存 Apache-2.0 Go 源码，`marketplace` 分支由 CI 生成可安装包：

```text
.agents/plugins/marketplace.json
.claude-plugin/marketplace.json
plugins/vivago-agent-cli/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
├── skills/vivago-agent-cli/
├── bin/
│   ├── darwin-arm64/vivago-agent
│   ├── darwin-amd64/vivago-agent
│   ├── linux-arm64/vivago-agent
│   ├── linux-amd64/vivago-agent
│   ├── windows-arm64/vivago-agent.exe
│   └── windows-amd64/vivago-agent.exe
├── scripts/
│   ├── vivago-agent
│   └── vivago-agent.cmd
├── checksums.txt
├── SBOM.spdx.json
└── BUILD_INFO.json
```

POSIX 启动器使用 `uname` 区分 macOS/Linux 与 `arm64/aarch64/x86_64`；Windows CMD 启动器根据系统架构选择 ARM64 或 x64 二进制。没有匹配二进制时返回退出码 40，并给出当前 OS/CPU 和支持范围。

启动器不修改用户的 PATH、Shell、Git 配置和其他仓库，不动态下载文件。安装、升级和回滚以完整插件包为单位，避免 Skill 和 CLI 版本不一致。

Marketplace 名称由 `vivago-private` 改为 `vivago`。用户安装方式为：

```bash
codex plugin marketplace add https://github.com/hidreamai/vivago-agent-cli.git --ref marketplace
codex plugin add vivago-agent-cli@vivago
```

```bash
claude plugin marketplace add 'https://github.com/hidreamai/vivago-agent-cli.git#marketplace'
claude plugin install vivago-agent-cli@vivago
```

插件内置六份二进制意味着每位用户都会下载完整平台包。公开 Beta 将插件总大小控制在 100 MiB 以内；如果后续超过这个预算，再评估按平台下载，不在第一版同时维护两种安装方式。

## GitHub 怎么发布

开发阶段允许使用个人 GitHub 跑测试和生成 `dev` 插件，但个人仓库只承担开发反馈，不是公开发布源。进入公开 Beta 前按下面的顺序晋级：

```text
个人 GitHub + 海外测试环境
  → 固定通过测试的 source commit
  → PR 或同步到公司 GitHub 并完成评审
  → 公司 CI 使用 prod profile 重新构建
  → 海外正式环境受控冒烟
  → 公司 GitHub Beta Release 和 Marketplace
```

公司 GitHub 的 Beta tag `vX.Y.Z-beta.N` 触发 GitHub Actions：

1. 运行 Go 单元测试、race test、vet、`govulncheck` 和 Secret Scanning。
2. 强制选择 `prod` profile，并检查工作流运行在公司仓库和受保护 Tag 上。
3. 固定 Go 版本，使用 `CGO_ENABLED=0`、`-trimpath` 构建六个 OS/CPU 目标。
4. 使用仓库固定的 Go `1.25.12` 或同一 `1.25.x` 系列中更新且通过 `govulncheck` 的安全补丁版本，注入版本、Git SHA、构建时间、`channel=beta` 和公司仓库标识。
5. 扫描完整插件包，包括二进制、启动脚本、`SKILL.md` 和 references，确认不存在海外测试、国内
   环境地址、`dev` profile 标记及测试凭证；不能只扫描可执行文件。
6. 生成 SHA256、SPDX SBOM 和 GitHub Artifact Attestation。
7. 在对应系统执行 `version`、`doctor` 和启动器选择测试。
8. 校验 Codex、Claude Code Manifest。
9. 使用内部正式账号完成海外正式环境的受控冒烟。
10. 创建不可覆盖的 GitHub prerelease。
11. 由发布机器人更新公司仓库 `marketplace` 分支中的完整插件包和版本。

公司 `marketplace` 分支不能接收个人 GitHub、开发机或其他流水线直接上传的二进制。Tag 和 Release 不允许覆盖，GitHub Actions 使用固定版本或 commit SHA。个人 GitHub 的测试结果可以作为评审证据，但公司 CI 必须独立重跑发布门禁。

公开 Beta 暂不把 Apple 公证和 Windows 签名作为发布阻断项，但必须提供 checksum、SBOM、构建来源证明和受保护 Tag。后续扩大到大量普通用户或企业用户前，再补 macOS Developer ID/Notarization 和 Windows Authenticode。

插件不实现自更新，统一使用 Codex/Claude Code Marketplace 更新能力。登录凭证存放在用户凭证库中，插件升级、卸载或回滚不得覆盖或删除凭证。

公开仓库增加 Apache-2.0 `LICENSE`、第三方依赖 `NOTICE`、`SECURITY.md`、安装文档和漏洞报告入口。

## 怎么验证

### 自动化测试

- 使用 Mock Server 覆盖全部 REST Path、请求字段、Header 和响应映射。
- 使用 Golden Test 对比 Python 与 Go 的 JSON、JSONL、退出码和 SSE 行为。
- SSE 覆盖分块、UTF-8、多行 data、心跳、提前断流和终态后断流。
- 登录覆盖成功、超时、取消、端口冲突、错误 Path、错误 Method、state 不匹配、重复 callback 和超大 Body。
- 凭证覆盖 Keychain、Credential Manager、Secret Service、Linux 文件降级和并发刷新。
- 文件覆盖格式、数量、大小、符号链接、流式上传和失败清理。
- 产物覆盖 SSRF、私网 DNS、跨域重定向、错误 Content-Type、文件超限和禁止覆盖。
- 所有测试扫描 stdout、stderr 和快照，确保没有凭证或预签名 URL。

### 双宿主 E2E

开发和测试阶段在海外测试环境完成 6 个 OS/CPU 目标 × 2 个宿主，共 12 个安装组合：

| OS/CPU | Codex | Claude Code |
|---|---:|---:|
| macOS ARM64 | 必测 | 必测 |
| macOS x64 | 必测 | 必测 |
| Linux ARM64 | 必测 | 必测 |
| Linux x64 | 必测 | 必测 |
| Windows ARM64 | 必测 | 必测 |
| Windows x64 | 必测 | 必测 |

1. 从个人 GitHub 的开发 Marketplace 安装 `dev` 插件。
2. 从未登录状态完成海外测试网页登录。
3. 创建项目并提交文本任务，收到 `RUN_FINISHED`。
4. 上传至少一种本地附件。
5. 处理 `input_required` 并继续同一 conversation。
6. 人为断开 SSE，使用原 `turn_id` 和 `last_event_id` 恢复。
7. 验证取消和历史查询。
8. 下载并本地预览图片、音频或视频产物。
9. 重启宿主后确认登录态仍有效。
10. 升级和回滚后确认登录态仍有效。
11. logout 后再次调用会重新登录。
12. 通过 `project link` 获取项目链接，并确认开发包返回 `dev.vivago.ai`；公司 `prod` 候选包必须返回
    `vivago.ai`，且完整插件包扫描不到任何开发环境地址。

完成 12/12 后，把确定的源码 commit 晋级到公司 GitHub。公司 CI 使用 `prod` profile 重新构建候选包，并在海外正式环境完成登录、创建项目、文本任务、SSE 终态和 logout 的受控冒烟；不得把个人 GitHub 的测试二进制直接作为候选包。

公开 Beta 的发布门槛：

- 海外测试环境 12/12 组合完成安装、登录和文本任务。
- 公司 GitHub 重新构建的 Beta 候选包通过海外正式环境受控冒烟。
- Critical/High 安全问题为 0。
- 六个平台 checksum 与构建来源一致。
- 插件总大小不超过 100 MiB。
- 发布包中不存在开发、国内环境入口。
- 生产项目链接由 CLI 返回，Skill 和 references 不包含开发域名，也不自行拼接项目地址。
- 开发和正式凭证命名空间完全隔离。
- CLI E2E 创建的 Project、Conversation 和 Turn 均落库 `source=cli`；Project 和 Turn 同时保持 `platform=web`，项目和产物仍可从 Web 端查看。
- 自动化测试、插件校验和秘密扫描全部通过。

首批邀请 20～50 名外部用户使用两周。期间主要观察安装、登录、任务提交、SSE 恢复和产物下载，不在客户端采集 Prompt、Token 或本地文件内容。

## 实施顺序和工作量

按一名研发全职使用 Codex 估算：

| 工作 | 预计时间 |
|---|---:|
| 固化 Python/Go 兼容契约和测试夹具 | 1～2 人日 |
| Go CLI、REST、SSE、附件和产物 | 3～4 人日 |
| Go 登录、凭证库和本地 callback | 3～4 人日 |
| 海外 Web 新增 `/agent/login` | 1～2 人日 |
| VivagoAgent Project/Conversation/Turn 的 `source=cli` 落库、日志、指标和限流归因 | 2～3 人日 |
| 六平台启动器与构建矩阵 | 2～4 人日 |
| 个人/公司 GitHub 分阶段构建、Marketplace、Release 和 SBOM | 2～3 人日 |
| 12 组合 E2E 与问题修复 | 3～5 人日 |

合计约 17～27 人日；测试账号、六个平台机器和 GitHub 权限准备充分时，公开 Beta 预计需要 14～21 个工作日。

实施顺序：

1. 先为现有 Python CLI 补齐兼容测试和录制式协议夹具。
2. Go 实现与 Python 并存，逐个命令通过兼容测试。
3. VivagoAgent 为 Project、Conversation 和 Turn 增加 `source=cli` 落库、日志、监控和限流归因，并保持现有 `platform` 行为。
4. 海外测试 Web 发布新的 `/agent/login` 页面，不改造 `/login-cli`。
5. 使用个人 GitHub 开发包完成 Go 登录、来源落库和海外测试 API E2E。
6. 把插件启动入口切换到 Go 二进制。
7. 删除插件中的 Python Runtime、PyInstaller 构建和 `vivago-client`。
8. 把通过测试的源码同步到公司 GitHub，建立公司 Release 和 `marketplace` 分支发布流水线。
9. 公司 CI 使用 `prod` profile 重新构建，通过环境扫描和海外正式受控冒烟后发布公开 Beta。

## 第一版不做什么

- 公开 Beta 不支持海外测试、国内开发和国内正式环境；海外测试只供开发和测试构建使用。
- 不建设 Hosted MCP、MCP Tasks/MRTR、标准 OAuth 或 OIDC。
- 不要求用户中心新增服务或接口。
- 不暴露 VivagoAgent 内部业务 MCP 工具和 Skill。
- 不提供独立 CLI 安装渠道或 CLI 自更新。
- 不在第一版申请 Codex/Claude 官方目录审核。
- 不在第一版增加服务端 refresh token 撤销接口。
- 不把 Apple 公证和 Windows 代码签名作为公开 Beta 阻断项。
- 不兼容旧 `/login-cli` 回调，不迁移 Python Pilot 或 `vivago-client` 凭证。

## 插件品牌素材

Codex 和 Claude Code 使用同一个插件分发目录，并携带设计确认的 512×512 浅色 Logo、512×512
深色 Logo 和 128×128 小图标。每种素材同时保留 SVG 源文件和 sRGB PNG。设计稿的白色、黑色背景
属于正式画面的一部分，不生成透明替代版，也不由客户端动态改色。

品牌文件统一放在插件根目录的 `plugin/assets/`，Codex manifest 使用 `./assets/...` 引用；不将
插件品牌文件放入单个 Skill 的目录，也不在 Skill 元数据中重复维护 Logo 路径。

Codex 插件清单配置 `composerIcon`、`logo`、`logoDark` 和品牌主色 `#574DFF`；Skill 的
`agents/openai.yaml` 同步配置大小图标和品牌色。Claude Code 清单只使用其官方支持的元数据字段，
不为了显示 Logo 添加未知字段，但分发包仍包含完整素材。详细规范见
[`2026-08-10-plugin-brand-assets-design.md`](2026-08-10-plugin-brand-assets-design.md)。

## 开工和发布前还要确认什么

以下事项已经确认，可以直接按此开发：

- 海外测试使用新的 `https://dev.vivago.ai/agent/login`，不改造 `/login-cli`，不兼容旧 `vivago-client`。
- 登录使用随机 loopback 端口、一次性 `state` 和普通 HTML Form POST；Web 与 CLI 的责任以前端配合说明为准。
- CLI 固定发送 `X-Source: cli` 和 `X-Client-Platform: web`；VivagoAgent 只为 Project、Conversation 和 Turn 增加 `source`。
- 开发构建访问海外测试环境，公开 Beta 构建只访问海外正式环境。
- 公开 Beta 可以暂不做 macOS 公证和 Windows 签名，但 checksum、SBOM 和构建来源证明必须齐全。
- macOS 13+ 和 Windows 10/11 必须使用系统凭证库；只有 Linux/WSL2 在 Secret Service 不可用时允许降级到权限为 `0600` 的文件。支持架构为 macOS Intel/Apple Silicon、Windows x64/ARM64、Linux/WSL2 x64/ARM64。

以下事项不阻塞本地编码，但必须在对应阶段前确认：

| 最晚确认时间 | 事项 |
|---|---|
| 登录真实 E2E 前 | 海外测试 `/agent/login` 已上线；CSP `form-action` 允许提交到 `http://127.0.0.1:*`；Chrome、Safari、Edge 的 loopback Form 行为完成验证 |
| 推送个人开发仓库和启用 CI 前 | 个人 GitHub 登录恢复，开发仓库地址和 Actions 权限可用 |
| 对外公开源码前 | 公开仓库许可证是否采用 Apache-2.0，第三方依赖许可证检查完成 |
| 公司 Beta 候选包构建前 | 公司 GitHub 仓库、源码同步方式、评审人、`marketplace` 分支、Beta Tag 和发布机器人权限 |
| 海外正式冒烟前 | 正式入口确认为 `https://vivago.ai/agent/login` 并上线；海外正式受控冒烟账号可用 |
| 公开 Beta 发布前 | 六个平台真实 E2E 环境和海外测试账号准备完成，12/12 安装与任务用例通过 |

Firefox 是否纳入公开 Beta 浏览器范围可以由产品和前端在登录联调前确认，不阻塞 CLI 核心开发。

本方案不改变 VivagoAgent 的项目、会话、Turn 和历史语义，只为 Project、Conversation 和 Turn 增加可选 `source` 元数据。现有 `platform`、资产和 CustomWorkflow 数据模型保持不变。开发和完整测试继续走海外测试环境；交给外部用户的六平台公开插件只由公司 GitHub 生成，并且只访问海外正式环境。

## 当前实施状态（2026-08-07）

功能分支已经完成 Go CLI 的系统凭证、随机 loopback 登录、Token 刷新、`version/doctor/auth`、
项目与会话控制、`ask/resume` JSONL、SSE 游标恢复、附件校验与流式上传、产物 URL 与安全下载。
默认构建固定海外测试，`prod` tag 固定海外正式；默认/生产测试、race、vet 和六个
`CGO_ENABLED=0` 目标均已通过。开发 staging 组装器能够生成 `vivago-dev` 双 Marketplace，内置六份
二进制、平台启动器、SHA256 和 BUILD_INFO；一次真实本机组装结果约 40 MiB，低于 100 MiB 预算。

2026-08-07 的海外测试实测已经覆盖以下内容：

- 最新开发包版本为 `0.3.0-dev.2`，源码 revision 为
  `9c4b82643df48e7023a59ceeffd8a3d09960f78e`；本机使用包内 macOS ARM64 启动器运行，
  没有依赖 PATH 中的旧 CLI。
- 已登录、首次未登录和 logout 后重新登录三条 `/agent/login` 流程均已完成；凭证保存在 macOS
  Keychain。logout 后 `auth status` 返回未登录，重新登录后恢复为 `logged_in=true` 且
  `needs_refresh=false`。
- `0.3.0-dev.3` 已在原 ticket 仍为 `needs_refresh=false` 时完成一次真实强制刷新。命令只返回
  `refreshed=true` 和 `backend=keychain`；刷新后的登录状态正常，Web 项目列表只读请求返回应用
  `code=0`。API 功能批次最新状态为 12/12 PASS；这不等同于尚未执行的“六平台 × 两宿主”安装矩阵。
- 真实图片任务完成了项目创建、`ask`、SSE 中断、同一 Turn 的 `resume`、`RUN_FINISHED`、历史查询
  和本地产物预览。服务端历史只有一个 Turn，恢复过程没有重复提交 prompt。
- 附件与取消 E2E 已通过：CLI 上传 JPEG 后创建一个 Turn，`cancel` 返回成功，服务端历史状态变为
  `cancelled`，原 SSE 随后收到 `RUN_ERROR: Task cancelled by user`。取消是异步操作，本次下游进度
  继续到约 38% 才收到终态，因此产品提示和监控不能把“取消接口成功”解释为已经即时停止计费任务。
- 测试库已经确认同一次任务的 Project 为 `platform=web, source=cli`，Conversation 为
  `source=cli`，Turn 为 `platform=web, source=cli`，且 Turn 状态为 `completed`。
- OpenAI `plugin-creator` 本地校验和 Claude Code 2.1.89 的 `plugin validate` 均已通过。
- Go 全包测试、构建脚本测试和双插件校验已经通过。实测证据只写入 `/tmp`，没有把账号信息、Token、
  签名 URL 或测试产物提交到仓库。

当前源码分支只维护 Go CLI，插件源码和 Skill 位于根目录 `plugin/`。旧 Python Pilot 已从
源码树移除；历史源码和三个旧发布提交在 Codeup 通过 `archive/*` Tag 保留，不再维护长期
Pilot 分支。日常源码开发收敛到 `main`，个人 GitHub 暂时保留 `dev-marketplace` 作为开发安装和
回滚通道。完整迁移设计见
[`2026-08-11-vivago-agent-cli-branch-convergence-design.md`](2026-08-11-vivago-agent-cli-branch-convergence-design.md)。

由于当前仓库的祖先历史包含旧 Pilot，未来公开的公司 GitHub 仓库从评审后的 Go 源码树建立
干净初始历史，不直接镜像当前仓库的完整历史或个人 GitHub 的开发二进制。接下来还要做：

1. 使用个人 GitHub 开发 Marketplace 完成 6 平台 × 2 宿主的 12/12 安装、登录、任务、升级和回滚用例。
2. 确认许可证和公司 GitHub 权限后，实现 prod 构建、SBOM、attestation、受控冒烟和公开 Beta。
