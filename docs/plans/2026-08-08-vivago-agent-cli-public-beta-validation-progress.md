# VivagoAgent CLI 公开 Beta 验证进度（L0–L3）

更新时间：2026-08-08

当前长期源码分支：`main`

当前开发版本：`0.3.0-dev.5`

验证环境：海外测试环境（`profile=dev`、`environment=overseas-test`）

当前可以确认：六平台构建、原生 CLI、Codex/Claude Code 插件生命周期和 ticket-only 在线业务验证已经跑通。L0 为 6/6，L1 为 6/6，L2 为 12/12，ticket-only L3 为 12/12。

这还不是“完整公开 Beta 验收完成”。标准登录、Codex/Claude 模型主动选择 Skill、海外测试库中的 `source/platform` 持久化和 Web 页面可见性仍需单独验证。

## 当前进度总表

| 层级 | 主要验证什么 | 当前结果 | 状态 | 关键证据 | 还缺什么 |
| --- | --- | ---: | --- | --- | --- |
| L0 | 六平台交叉编译、Marketplace 组装、checksum、环境地址扫描和静态门禁 | 6/6 | 已通过 | [Development CI #31198528727](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31198528727)、[v0.3.0-dev.5](https://github.com/ChaoXia-Beginer/vivago-agent-cli/releases/tag/v0.3.0-dev.5) | 代码签名、公证和公司 GitHub 发布流程不属于本轮 L0 |
| L1 | 在真实 OS/CPU Runner 上启动对应二进制，验证 launcher、`version` 和 `doctor` | 6/6 | 已通过 | [Development CI #31187868757](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31187868757)；dev.5 的 L2 也再次启动了六平台二进制 | 专用 L1 报告的版本较早，当前 dev.5 由更强的 L2 结果补充证明 |
| L2 | Codex/Claude Code 插件安装、发现、升级、回滚、再升级 | 12/12 | 已通过 | [Development Release #31198629029](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31198629029)，12 份脱敏报告 | 不调用 Codex/Claude 模型，不证明模型会主动选 Skill |
| L3 | 通过安装后的插件 CLI 调用真实 VivagoAgent Web API，验证任务、SSE、附件、产物、取消和历史 | 12/12 | 已通过（ticket-only 范围） | [Hosted L3 #31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974)，6 份双宿主脱敏报告 | 登录/刷新/退出重登未跑；模型调用、数据库落库和 Web UI 未直接验证 |

这里的计数口径不同：L0/L1 按六个平台计数，L2/L3 按“六个平台 × 两个宿主”计数。

## 六个平台的结果

| 目标平台 | GitHub Runner | 插件 launcher | L0 构建 | L1 原生启动 | L2 Codex/Claude | L3 Codex/Claude |
| --- | --- | --- | --- | --- | --- | --- |
| macOS ARM64 | `macos-26` | `vivago-agent` | PASS | PASS | 2/2 PASS | 2/2 PASS |
| macOS x64 | `macos-26-intel` | `vivago-agent` | PASS | PASS | 2/2 PASS | 2/2 PASS |
| Linux ARM64 | `ubuntu-24.04-arm` | `vivago-agent` | PASS | PASS | 2/2 PASS | 2/2 PASS |
| Linux x64 | `ubuntu-24.04` | `vivago-agent` | PASS | PASS | 2/2 PASS | 2/2 PASS |
| Windows ARM64 | `windows-11-arm` | `vivago-agent.cmd` | PASS | PASS | 2/2 PASS | 2/2 PASS |
| Windows x64 | `windows-2025` | `vivago-agent.cmd` | PASS | PASS | 2/2 PASS | 2/2 PASS |

当前验证没有用 WSL 代替 Windows，也没有用 Rosetta 代替 macOS x64。Windows ARM64 使用真实 `windows-11-arm` Runner。

## L0、L1、L2、L3 分别代表什么

| 层级 | 怎么执行 | 通过标准 | 能证明什么 | 不能证明什么 |
| --- | --- | --- | --- | --- |
| L0 | 在 CI 中交叉编译六个平台，组装 Marketplace，并做静态扫描和单元测试 | 六个二进制和插件包结构完整；checksum 匹配；没有错误环境地址或占位值；测试和校验器通过 | 代码和发布产物可以被正确构建 | 二进制不一定能在真实目标机器运行 |
| L1 | 在六种真实 Runner 上调用对应 launcher 的 `version` 和 `doctor` | Runner OS/CPU 与目标一致；launcher 选择正确二进制；输出协议正确 | 六个平台的 CLI 可以原生启动 | 不证明 Codex/Claude 能安装插件，也不调用在线业务 |
| L2 | 在每个平台分别安装 Codex 和 Claude Code，通过官方插件命令做安装、升级、回滚和再升级 | 12 个组合的四个阶段都找到正确插件缓存和 launcher，`doctor_exit=0` | 插件包能被两个宿主正确安装和维护 | 不登录宿主模型，也不提交 VivagoAgent 业务任务 |
| L3 | 向 Runner 注入一次性 VivagoAgent ticket，安装插件后直接调用其 launcher 提交真实任务 | 两个宿主路径均完成任务、附件、SSE 恢复、产物、取消、历史和重启检查 | 插件 CLI 到 VivagoAgent 的真实在线业务路径可用 | 本轮不证明标准登录、模型自动选 Skill、数据库字段持久化或 Web UI 展示 |

## 当前验证基线

| 项目 | 当前值 |
| --- | --- |
| 开发版本 | [`v0.3.0-dev.5`](https://github.com/ChaoXia-Beginer/vivago-agent-cli/releases/tag/v0.3.0-dev.5) |
| Marketplace 源码 | `eb7fa926609d64c9647a3f0b3951b460c4e23b0d` |
| L3 工作流源码 | `ce633432adf922e31deb28a6fa297ec0831fcc75` |
| Codex CLI | `0.147.0` |
| Claude Code | `2.1.220` |
| API 目标 | `https://dev.vivago.ai`，编译期固定，不提供运行时 `--env` 切换 |
| 请求归属 | `X-Source: cli`、`X-Client-Platform: web` |
| 发布运行 | [Manual Development Release #31198629029](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31198629029) |
| 最终 L3 运行 | [Manual Hosted L3 #31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974) |
| 最终文档前 CI | [Development CI #31233657351](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31233657351) |

## L0：构建和发布产物

L0 先回答“六个平台的包能不能稳定构建出来”。它不依赖登录，也不调用 VivagoAgent 在线任务。

### 验证过程

1. 运行 Go 默认配置和 `prod` build tag 的完整测试。
2. 运行 `go test -race ./...` 和 `go vet ./...`。
3. 运行 Python 验证器测试、Codex 官方插件校验器和 Claude 插件校验器。
4. 构建 macOS、Linux、Windows 的 ARM64/x64 六个二进制。
5. 组装 `vivago-dev` Marketplace，校验 `BUILD_INFO.json`、manifest 和 checksum。
6. 扫描开发包，防止混入生产环境地址、占位值或错误 profile。
7. 上传开发 Marketplace artifact；手动发布门禁通过后创建 Prerelease。

### 当前结果

| 检查项 | 结果 | 说明 |
| --- | --- | --- |
| Go 默认测试 | PASS | `go test ./...` |
| Go prod 测试 | PASS | `go test -tags prod ./...` |
| Race | PASS | `go test -race ./...` |
| Vet | PASS | `go vet ./...` |
| Python 验证器测试 | 45/45 PASS | 包含 workflow、六平台、双宿主和 L3 报告契约 |
| Codex 官方本地校验 | PASS | 插件 manifest 和目录结构有效 |
| Claude 插件校验 | PASS | Claude Code 能识别插件结构 |
| 六平台构建 | 6/6 PASS | darwin/linux/windows × arm64/amd64 |
| Marketplace 和 checksum | PASS | 发布产物与 `BUILD_INFO.json` 一致 |
| 环境地址扫描 | PASS | dev 包保持海外测试环境，不混入生产地址 |

`v0.3.0-dev.5` Release 指向 `eb7fa92...`，包含一份完整开发 Marketplace；对应运行还上传了 12 份 L2 生命周期报告。

## L1：六平台原生 CLI

L1 重点是排除“交叉编译成功，但目标机器实际跑不起来”的情况。

### 验证过程

1. 六个原生 Runner 下载同一份 Marketplace 构建产物。
2. 验证 Runner 的 OS 和 CPU 与声明目标一致。
3. 检查压缩包是否存在路径穿越、链接或异常大文件。
4. 调用当前平台 launcher 的 `version` 和 `doctor`。
5. 核对 launcher 实际选择了本平台二进制，避免 ARM 机器借助兼容层误跑 x64。
6. 上传六份不含凭据的 JSON 报告。

### 当前结果和证据

- 专用 L1 运行： [Development CI #31187868757](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31187868757)，6/6 PASS。
- 专用 L1 报告基于较早的 `0.0.0-dev.8`，源码为 `8f4de330a914b58fe3183eefcaec5cff3f5c3fdc`。
- 最新 `v0.3.0-dev.5` 又在 L2 的 12 个原生 Job 中调用了六个平台的 launcher 和 `doctor`，全部为 `doctor_exit=0`。因此当前二进制的原生启动不是只依赖旧版本报告。

## L2：两个宿主的安装、升级和回滚

L2 使用 Codex 和 Claude Code 的官方插件管理命令，不直接复制插件到宿主目录。

### 每个组合实际执行的四个阶段

| 阶段 | 插件版本 | 验证内容 |
| --- | --- | --- |
| 全新安装 | `0.3.0-dev.4` | 从开发 Marketplace 安装，定位宿主隔离目录中的 launcher，运行 `doctor` |
| 升级 | `0.3.0-dev.5` | 更新 Marketplace 和插件，确认加载新版本 launcher |
| 回滚 | `0.3.0-dev.4` | 回退到上一开发版本，确认旧版本仍可运行 |
| 再升级 | `0.3.0-dev.5` | 再次升级并确认最终状态回到候选版本 |

### 当前结果

| 指标 | 结果 |
| --- | --- |
| 平台数 | 6 |
| 宿主数 | 2 |
| 总组合数 | 12 |
| 成功报告 | 12/12 |
| Codex 版本 | `0.147.0` |
| Claude Code 版本 | `2.1.220` |
| 每份报告的四个阶段 | 全部 PASS |
| `doctor_exit` | 全部为 `0` |
| 报告环境 | `profile=dev`、`environment=overseas-test` |
| 报告源码 | 全部为 `eb7fa926609d64c9647a3f0b3951b460c4e23b0d` |

门禁通过后，流水线才创建 `v0.3.0-dev.5` Prerelease 并更新 `dev-marketplace`。如果任意一个平台或宿主失败，发布步骤不会执行。

L2 不调用 Codex 或 Claude 模型。它证明的是官方插件命令能安装和维护插件，不证明模型拿到自然语言请求后会主动读取 Skill 并调用 `vivago-agent`。

## L3：ticket-only 在线业务验证

最终 L3 运行时间为 2026-08-08 09:19:40 至 09:46:43（北京时间）。六个平台严格串行执行，每个平台先后验证 Codex 和 Claude Code，最终 6 个平台 Job 和 12 个宿主 case 全部成功。

### ticket 怎么进入 Runner

| 步骤 | 实际处理 | 安全限制 |
| --- | --- | --- |
| 1. 获取凭据 | 从本机现有 VivagoAgent 登录态换出短期 ticket | 不读取或上传 refresh token |
| 2. 临时存放 | 写入个人 GitHub 仓库 `overseas-test-e2e` Environment 的 `VIVAGO_E2E_TICKET` | 只允许 `main` 使用 |
| 3. Runner 注入 | `vivago-e2e-auth seed` 写入对应系统的原生凭据存储 | 要求 ticket 至少还有 45 分钟有效期 |
| 4. 在线验证 | 安装插件并直接调用插件 launcher | stdout 不输出 ticket、Cookie 或 Authorization |
| 5. Job 清理 | 每个 Job 通过 `if: always()` 执行 `vivago-e2e-auth clear` | 失败、取消和成功都会清理 |
| 6. 最终删除 | 整轮结束后删除 GitHub Environment Secret | 删除后再次列表查询，结果为空 |

### 每个宿主执行了哪些在线用例

| 检查项 | 实际验证 | 结果 |
| --- | --- | --- |
| 插件安装和发现 | 使用宿主官方命令安装、列出插件并定位隔离目录 | PASS |
| 凭据加载 | `doctor` 和 `auth status` 能读取一次性凭据 | PASS |
| 文本任务 | 创建项目，提交文本任务并收到 `RUN_FINISHED` | PASS |
| 本地附件 | 生成确定性的三色 PNG、上传并让 VivagoAgent 识别 `red, green, blue` | PASS |
| 同会话继续 | 后续任务保持相同 Conversation | PASS |
| 自动澄清 | Agent 先提出澄清问题，再在同一 Conversation 接收回答并继续 | `PASS_AUTOMATED_CLARIFICATION_ROUND_TRIP` |
| SSE 中断恢复 | 在可恢复检查点主动中断，再用同一 Turn 和游标恢复到 `RUN_FINISHED` | PASS |
| 图片生成 | 完成一条真实图片生成任务并取得成功 artifact | PASS |
| 产物预览和下载 | 预览、下载并验证本地文件存在、字节数大于 0、内容类型为图片 | PASS |
| 取消任务 | 等到 `RUN_STARTED` 后取消真实图片任务，收到 `RUN_ERROR` | PASS |
| 历史状态 | 历史中能找到完成 Turn 和 `cancelled` Turn | PASS |
| 宿主重启 | 新宿主进程重新发现相同插件并读取凭据状态 | PASS |
| 项目链接 | `project link` 使用编译期固定的 `dev.vivago.ai` | PASS |
| 首次登录 | 本轮按要求不执行 | `NOT_RUN` |
| 刷新 | 本轮没有 refresh token，不执行 | `NOT_RUN` |
| 退出重登 | 本轮按要求不执行 | `NOT_RUN` |
| 升级回滚 | 引用同版本已通过的 L2 门禁 | `PASS_IN_L2_RELEASE_GATE` |

报告中的 `input_required` 检查实际是“自动澄清问题 → 回答 → 同会话继续”的往返验证。它没有在 Codex 或 Claude 的交互 UI 中暂停等待真人输入，因此不能替代宿主界面的人工 `input_required` 验收。

### 六份报告怎么审计

| 审计项 | 结果 |
| --- | --- |
| 报告数量 | 正好 6 份 |
| 平台集合 | 正好是 darwin/linux/windows × arm64/amd64 |
| 宿主集合 | 每份正好包含 `codex` 和 `claude-code` |
| 运行结果 | 全部 `ok=true` |
| 版本和源码 | 全部为 `0.3.0-dev.5` / `eb7fa92...` |
| 环境 | 全部为 `profile=dev` / `environment=overseas-test` |
| 终态 | 完成任务全部为 `RUN_FINISHED`，取消任务在历史中为 `cancelled` |
| 产物 | 12 个 case 的 artifact 字节数均大于 0，内容类型均为图片 |
| 敏感字段 | 没有 URL、ticket、token、Authorization、Cookie、prompt、artifact ID 或 content ID |
| Runner 清理 | 六个 Job 的凭据清理步骤全部成功 |
| GitHub Secret | 最终已删除，Environment Secret 列表为空 |
| 本机 Go CLI | `logged_in=false`、`needs_refresh=false` |

### 为什么不需要 Codex/Claude 账号

自动化会真实安装 Codex CLI 和 Claude Code，但只调用它们的插件管理命令。在线任务由安装后的 `vivago-agent` launcher 直接提交到 VivagoAgent，未调用 OpenAI 或 Anthropic 模型，所以 GitHub Runner 不需要登录两个宿主账号。

这也是当前结果的限制：L3 能证明“宿主可安装插件 + 插件 CLI 在线业务可用”，不能证明“宿主模型读懂用户请求后会主动选择插件 Skill”。

## 整体验证过程

| 顺序 | 时间/版本 | 动作 | 结果 | 证据 |
| ---: | --- | --- | --- | --- |
| 1 | `eb7fa92` | 完成 L3 验证器和 ticket-only Workflow | 本地 Codex/Claude 两个 case 通过 | 本地 attempt 21 脱敏报告 |
| 2 | 2026-08-08 前 | 运行 dev.5 Development CI | 测试、构建、插件校验和安全扫描通过 | [#31198528727](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31198528727) |
| 3 | `v0.3.0-dev.5` | 运行六平台 × 两宿主发布门禁 | L2 12/12，通过后创建 Prerelease | [#31198629029](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31198629029) |
| 4 | 2026-08-08 09:09 | 首次远程 L3，`max-parallel=2` | macOS ARM64 成功；其他并行 Job 遇到 503，运行被取消 | [#31231962090](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31231962090) |
| 5 | `ce63343` | 将 L3 矩阵改为 `max-parallel=1` | 契约测试和 Development CI 通过 | [#31232328504](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232328504) |
| 6 | 2026-08-08 09:19–09:46 | 串行重跑六平台 ticket-only L3 | 6/6 平台、12/12 case 全部成功 | [#31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974) |
| 7 | L3 结束后 | 删除 GitHub Secret，并复查本机和 Runner 凭据 | Environment 为空，本机未登录，六个 Runner 清理成功 | Secret 列表、`auth status` 和 Job steps |
| 8 | `399c760` | 记录 L3 结果并运行最终 CI | CI 通过 | [#31233657351](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31233657351) |

## 验证中遇到的问题

| 阶段 | 现象 | 根因 | 修复 | 回归证据 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| L1 / Windows | Windows x64/ARM64 launcher 没有机器可读 stdout | Python 把整条批处理调用拼成一个参数，破坏了 `cmd.exe` 参数边界 | 分开传递 `call`、launcher 和 CLI 参数；提交 `8f4de33` | [#31187868757](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31187868757) Windows 两平台通过 | 已解决 |
| L2 / Windows | 复制旧 Marketplace 后无法清理目录 | 把只读 `.git` object 一并复制进隔离目录 | 复制 Marketplace 时排除 `.git`；提交 `1cea0d4` | dev.4、dev.5 的 Windows 双宿主生命周期通过 | 已解决 |
| L3 / SSE | 恢复流偶尔没有 Conversation 响应头 | 恢复请求沿用原 Turn，响应不保证重复返回所有初始 header | 要求恢复流命中原 Turn，并用 history 反查同一 Conversation，不重新提交 prompt | `710c29e` 后本地和六平台 L3 通过 | 已解决 |
| L3 / 附件 | 文本文档上传成功，但 Agent 无法稳定读取其内容 | 当前测试环境没有稳定物化该文档内容 | 改为确定性三色 PNG，并要求模型返回颜色顺序 | 12/12 case 附件识别通过 | 已解决测试不稳定性；文档附件不是本轮覆盖项 |
| L3 / 消息解析 | 一个 Turn 可能出现多个 assistant message ID | 流式消息不能假设只有一个 message ID | 按 message ID 分组拼接 delta 后再判断结果 | 本地和远程 L3 全部通过 | 已解决 |
| L3 / 取消 | 只创建 session 就取消会得到 `Run is not active`，纯文本任务又可能结束太快 | 取消时机早于 `RUN_STARTED`，或任务生命周期过短 | 使用真实图片任务，等到 `RUN_STARTED` 后立即取消 | 12/12 case 的取消和历史状态通过 | 已解决 |
| L3 / 产物 | 图片 artifact 既可能是 `j_`，也可能是 `p_` | 服务端存在两种有效图片产物 ID 前缀 | 只接受已验证 `succeeded` 的 `j_`/`p_` 结果，不把 ID写入报告 | 预览和下载 12/12 通过 | 已解决 |
| L3 / 首次远程运行 | 多个平台首个文本任务显示 `TRANSPORT_ERROR` | CLI 对非鉴权 HTTP 错误做统一脱敏；Loki 证实实际为 `/conversation/chat` HTTP 503，测试账号 `parallel_num=1` | 不对会创建 Turn 的命令自动重试，矩阵改为 `max-parallel=1`；提交 `ce63343` | [#31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974) 六平台全绿 | 已解决 |

第一次远程 L3 被取消后，六个 Job 的 `Clear the runner credential` 都执行成功。失败报告也没有保留 ticket、URL 或业务 prompt。

## source 和 platform 目前验证到哪里

服务端开发已经补齐 `Project / Conversation / Turn.source=cli`，并把来源写入日志、监控和限流统计。本次运行从 Loki 确认了请求侧字段：

| 字段 | 当前证据 | 结果 |
| --- | --- | --- |
| `X-Source` | VivagoAgent 请求日志 | `cli` |
| `client_source` | VivagoAgent 结构化日志 | `cli` |
| `X-Client-Platform` | VivagoAgent 请求日志 | `web` |
| `X-Client-Version` | VivagoAgent 请求日志 | `0.3.0-dev.5` |
| Project 持久化 | 海外测试 Mongo | 未直接查询 |
| Conversation 持久化 | 海外测试 Mongo | 未直接查询 |
| Turn 持久化 | 海外测试 Mongo | 未直接查询 |
| Web 页面可见 | 浏览器人工检查 | 未验证 |

当前本机 Mongo 只读工具只配置了正式库，没有海外测试库目标。为了避免拿测试 ID 查询正式库或临时拼接数据库凭据，本轮没有直接读取海外测试 Mongo。日志可以证明请求归属已经识别，不能单独证明数据库字段已经落盘。

## 后续还需要做什么

以下估时只计算开发和验证时间，不包含账号、权限、证书或跨团队排期等待。

| 优先级 | 工作 | 当前状态 | 预计工作量 | 前置依赖 | 验收标准 | 是否需要你介入 |
| --- | --- | --- | ---: | --- | --- | --- |
| P0 | 标准登录、刷新、退出重登 | 本轮 `NOT_RUN` | 代表平台 0.5–1 天；六平台完整覆盖 1–2 天 | 可操作浏览器、测试账号、必要时处理 MFA/验证码 | 首次未登录、登录成功、刷新、退出、重新登录均通过；不使用 App API 或 token 绕过 | 需要，在出现浏览器登录或验证码时介入 |
| P0 | Codex/Claude 模型主动选择 Skill | 未验证 | 0.5 天 | 两个宿主各自可用账号 | 分别用自然语言发起一次任务，模型主动加载 Skill 并调用插件，不手工执行 launcher | 需要提供或登录两个宿主账号 |
| P0 | `source/platform` 数据库持久化 | 只有日志证据 | 0.5 天 | 海外测试 Mongo 只读目标，或服务端研发提供查询结果 | 按 L3 报告 ID 核对 Project、Conversation、Turn 的 `source=cli`，涉及 `platform` 的表保持 `web` | 需要协调只读权限或服务端研发 |
| P0 | Web 页面可见性 | 未验证 | 0.25 天 | 海外测试 Web 登录 | CLI 创建的项目、Conversation、任务历史和产物可以在 Web 中打开 | 需要登录 Web 时介入 |
| P1 | 公司 GitHub Beta 流水线 | 未开始 | 2–3 天 | 公司仓库权限、License 决策、Tag/分支规则 | 公司 CI 用正式 profile 重建；生成 checksum、SBOM 和构建证明；只发布海外正式环境包 | 需要确认公司仓库和发布规则 |
| P1 | 海外正式环境受控 Beta | 未开始 | 0.5–1 天 | 公司 GitHub Beta 包、海外正式测试账号 | 在正式环境完成安装、登录、文本任务、附件、SSE 和产物下载的受控 smoke | 需要确认正式测试账号和发布时间 |
| P2 | macOS 公证、Windows 签名 | 未开始 | 2–5 天 | Apple Developer ID、Windows 代码签名证书 | 安装和首次运行不触发无法解释的 Gatekeeper/SmartScreen 风险 | 需要公司提供证书和签名主体 |

如果只安排下一轮验证，建议顺序是：

1. 先补海外测试 Mongo 的只读证据和 Web 页面可见性，这两项不需要重新跑六平台生成任务。
2. 再用真实 Codex/Claude 账号各做一次模型主动调用。
3. 登录流程有人能处理浏览器和验证码时再跑，先做代表平台，再决定是否扩到六平台。
4. 上述 P0 完成后，再迁移到公司 GitHub，构建只连接海外正式环境的 Beta 包。

## 哪些结论可以对外说

| 可以确认 | 暂时不能确认 |
| --- | --- |
| 六个平台都能构建并原生运行 CLI | 标准登录已经覆盖六个平台 |
| Codex/Claude Code 都能安装、升级、回滚插件 | Codex/Claude 模型会主动选择 Skill |
| ticket-only 在线任务在 12 个组合全部通过 | refresh token 和退出重登已经验证 |
| 文本、附件、SSE、图片产物、取消和历史已跑真实海外测试环境 | `source/platform` 已由本轮直接查询数据库证明 |
| 一次性 ticket 已删除，Runner 和本机没有残留临时登录态 | Web 页面已经人工确认所有 CLI 项目可见 |
| dev.5 Release 和报告可在个人 GitHub 追溯 | 公司 GitHub 和海外正式环境 Beta 已经发布 |

当前准确说法是：

> VivagoAgent CLI 的 L0、L1、L2 已完成，ticket-only L3 在六平台 × 两宿主上为 12/12；距离完整公开 Beta 验收还差标准登录、宿主模型主动调用、数据库持久化、Web 可见性，以及公司 GitHub/海外正式环境发布准备。

## 相关提交

| 阶段 | 提交 | 内容 |
| --- | --- | --- |
| L1 | `8846b7f` | 增加六平台原生 smoke |
| L1 | `8f4de33` | 修复 Windows launcher 参数边界 |
| L2 | `658ec0b` | 增加六平台 × 两宿主发布门禁 |
| L2 | `1cea0d4` | 排除生命周期复制中的 `.git` 元数据 |
| L3 | `2d77f43` | 增加 ticket-only Hosted L3 矩阵 |
| L3 | `9ccd77b` | 扩充文本、附件、续聊、SSE、取消和历史用例 |
| L3 | `710c29e` | 加固在线用例和恢复解析 |
| L3 | `e6c8d26` | 增加自动澄清和真实产物校验 |
| L3 | `eb7fa92` | 完成 dev.5 L3 发布基线 |
| L3 | `ce63343` | 按账号限制将 Hosted L3 改为串行 |
| 文档 | `399c760` | 记录 ticket-only L3 最终结果 |

方案细节见 [`2026-08-07-vivago-agent-cli-six-platform-two-host-test-design.md`](./2026-08-07-vivago-agent-cli-six-platform-two-host-test-design.md)。
