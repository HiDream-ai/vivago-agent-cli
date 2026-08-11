# VivagoAgent CLI 从公开 Beta 到正式版的差距分析

日期：2026-08-07
关联方案：[`2026-08-07-vivago-agent-cli-go-public-beta-design.md`](2026-08-07-vivago-agent-cli-go-public-beta-design.md)

## 结论

设计中的 Go 公开 Beta 解决的是“外部用户能安装、能登录、能调用”的问题，距离可以长期、大范围运营的正式版，还缺五类核心能力：服务端安全闭环、可信软件供应链、完整兼容性、线上运维体系和公开服务配套。

Hosted MCP 和标准 OAuth 不是 GitHub 正式版的硬门槛。我们可以继续采用“Skill + 本地 Go CLI + VivagoAgent Web API”，也可以继续使用改造后的海外 Web 登录。只要登录链路经过安全加固、凭证可撤销、发布物可信、服务可运营，这条架构可以作为正式方案。

需要先说明当前状态：截至本文日期，对外公开入口尚未发布；长期源码开发已经收敛到 `main`，
旧 Python Pilot 只通过 Codeup 的 `archive/*` Tag 保留，不再维护 Pilot 源码或发布分支。Go 版本已经完成
登录/凭证、Web REST/SSE、项目与会话命令、断流恢复、附件流式上传、产物安全下载、真实网页登录和
海外测试 API E2E，并能生成六平台开发 Marketplace 包。六平台 × 两宿主的完整安装矩阵、公司 GitHub
生产构建和正式环境受控冒烟仍未完成。因此仍存在两段工作：

1. 完成 Go 公开 Beta 剩余工作，预计 9～15 人日。
2. 再完成本文列出的 GA 加固，预计 27～48 人日。

从当前分支走到 GitHub 正式版，合计约 36～63 人日。一名研发全职使用 Codex、且 Web、服务端、
法务和证书事项能及时配合时，日历周期约 7～12 周。证书采购、外部审计和平台审核的排队时间不计入研发人日。

## “正式版”有两种含义

这两种目标需要分开评审，不能把它们混成一份上线清单。

| 目标 | 用户如何安装 | 是否必须 Hosted MCP | 是否必须标准 OAuth | 当前判断 |
|---|---|---:|---:|---|
| GitHub 自定义 Marketplace 正式版 | 用户先添加我们的 GitHub Marketplace，再安装插件 | 否 | 否 | 应作为第一阶段 GA 目标 |
| Codex / Claude 平台目录收录 | 用户在平台维护的目录中发现并安装 | 不一定 | 不一定 | 属于额外审核和适配工作 |

Codex 和 Claude Code 都正式支持 Git 仓库形式的自定义 Marketplace。它不是临时旁路，而是一种官方提供的插件分发方式。它与平台目录的主要区别是：插件发现、自动更新、平台背书和审核责任不同，不是核心调用协议不同。

## 公开 Beta 已经覆盖什么

以下是公开 Beta 的完整目标；其中 Go CLI 核心和六平台开发包组装已在功能分支实现，真实双宿主 E2E、
服务端来源落库、公司构建与公开发布仍未完成：

- Go 重写 CLI，并把登录能力合并进同一个二进制。
- macOS、Linux、Windows 的 ARM64 和 x64，共六个 OS/CPU 目标。
- Codex 和 Claude Code 共 12 个宿主/平台组合的基础 E2E。
- 开发和测试使用个人 GitHub 和海外测试环境；公开 Beta 由公司 GitHub 重新构建并只访问海外正式环境。
- 开发包与 Beta 包使用不同的编译 profile 和凭证命名空间，公开二进制不提供环境切换入口。
- 独立的 `/agent/login` 页面、随机 loopback 端口、`state` 校验和 Form POST 登录回调，不复用旧 `/login-cli`。
- 系统凭证库，Linux/WSL 在不可用时降级到权限为 `0600` 的本地文件。
- checksum、SBOM、构建来源证明和受保护 Release Tag。
- GitHub Release 与自定义 Marketplace 分发。
- 不暴露业务 MCP 工具，不在本地保存第二份会话历史。

这些能力足以支撑 20～50 名外部用户的公开 Beta，但不能单独证明产品可以无边界扩量。

## GitHub 正式版必须补齐的能力

### 1. 登录和会话必须形成服务端安全闭环

公开 Beta 的网页登录解决了回调地址固定、凭证出现在 URL、`state` 缺失等本地安全问题，但设计中仍明确暂缓了服务端 refresh token 撤销。这意味着 `logout` 主要清理本机凭证，不能保证已经泄露或被复制的长期凭证立即失效。

GA 前需要补齐：

- refresh token 服务端撤销，`logout` 后旧凭证不可继续刷新。
- refresh token 轮换；旧 token 被重复使用时触发重放检测。
- 为每次 CLI 登录建立设备会话，用户可以查看并下线某个设备，也可以全量退出。
- 登录、刷新和验证码接口具备限流、失败锁定、异常 IP/设备告警。
- access token 保持短有效期，服务端校验用户、环境和资源权限，不能只相信客户端传入的 ID。
- 凭证失效、账号禁用和密码修改后的行为有清晰契约与自动化测试。

这些工作可以沿用现有海外登录体系实现，不要求先建设 OAuth Server。标准 OAuth 是后续平台原生连接或 Hosted MCP 的可选升级，不应阻塞当前 GitHub GA。

### 2. VivagoAgent Web API 要从“能调用”升级为“可长期兼容”

CLI 会长期存在于用户电脑中，服务端不能假设所有用户都立即升级。

GA 前需要补齐：

- CLI/API 版本兼容策略：请求携带 CLI 版本，服务端声明最低支持版本和强制升级条件。
- 至少保留一个稳定版本的向后兼容窗口，并为废弃字段和错误码提供迁移期。
- 项目创建、会话创建、Turn 提交等写请求支持幂等键，网络重试不能生成重复项目或重复扣费任务。
- “一个项目一个会话”等约束由数据库唯一约束或原子事务保证，不能只依赖客户端预检查。
- SSE 断线恢复、`last_event_id`、取消、超时和 `input_required` 在服务端有稳定状态机。
- 项目、会话、Turn、附件和产物下载全部执行租户级权限校验，防止通过猜测 ID 越权访问。
- 上传、下载和重定向有大小、类型、域名、超时和并发限制；签名 URL 有短有效期。
- 限流、配额、计费、滥用防护和内容安全策略覆盖 `source=cli` 来源；CLI 数据仍保持 `platform=web`，确保可以在 Web 端继续使用。

### 3. 发布物要获得操作系统信任

checksum 和 SBOM 能证明文件有没有被改动，但普通用户仍会看到 macOS Gatekeeper 或 Windows SmartScreen 的未知开发者提示。公开 Beta 可以接受这种摩擦，正式版不宜长期依赖用户绕过安全提示。

GA 前需要补齐：

- macOS ARM64/x64 使用 Developer ID 签名并完成 Apple Notarization。
- Windows ARM64/x64 使用 Authenticode 代码签名；根据下载信誉情况评估普通证书或 EV 证书。
- Linux 至少发布签名 checksum、SBOM 和可验证的构建来源证明。
- GitHub Actions 第三方 Action 固定到 commit SHA，Release Tag 受保护，正式发布至少两人审批。
- 六个平台二进制由干净 CI 环境构建，不允许研发本机手工替换 Release 附件。
- 个人 GitHub 只承担开发和测试；所有公开 Beta/GA Release 必须由公司 GitHub 从评审后的源码重新构建。
- 公司流水线扫描 Beta/GA 包，阻断包含海外测试地址、国内地址、测试凭证或 `dev` profile 标识的产物。
- Release、Marketplace manifest、插件版本和二进制版本保持一一对应。
- 保留上一个稳定版本，支持一键回滚；发现高危问题时可以暂停分发或阻断最低版本。
- 评估可复现构建；无法完全复现时，也必须保存编译器版本、依赖锁定文件和构建证明。

### 4. Go 重写后要重新做一次安全审计

Python Pilot 的测试结论不能自动覆盖 Go 版本。登录、网络、文件和更新链路都发生了变化，安全审计应在 Go 实现基本稳定后进行。

审计范围至少包括：

- 插件 Skill 是否可能诱导宿主执行越权 Shell 命令或泄露本地数据。
- CLI 是否把 token、Cookie、Authorization、登录表单或用户 Prompt 写入 stdout、stderr、日志和崩溃信息。
- loopback 回调的 CSRF、`state`、端口抢占、恶意网页请求和回调重放。
- refresh token 存储、迁移、注销和 Linux 文件降级。
- HTTP 重定向、DNS rebinding、SSRF、私网地址、代理和证书校验。
- 上传文件的符号链接、路径穿越、超大文件、类型伪造和内存占用。
- 产物文件名、覆盖策略、下载 URL 和本地落盘路径。
- Release 流水线、GitHub 权限、依赖投毒和 Marketplace 更新链路。

GA 门槛是 Critical/High 为 0；登录、文件和发布链路中的 Medium 问题不得以“后续再看”直接放行，必须修复或由安全负责人书面接受风险并设定到期时间。

### 5. 测试要覆盖真实用户环境，而不只是 12 个基础组合

12 个宿主/平台组合是最低冒烟矩阵。正式版还要验证这些常见场景：

- macOS Intel 与 Apple Silicon 的主流系统版本。
- Windows x64、Windows ARM64，以及 Claude Code/Codex 实际支持方式下的 PowerShell、CMD 和 WSL。
- Linux x64/ARM64 的至少两个主流发行版，含桌面 Secret Service 和无桌面环境。
- 普通用户权限、只读目录、带空格/中文路径、超长路径和剩余磁盘不足。
- 企业代理、自签 CA、弱网络、DNS 失败、SSE 中断和机器休眠恢复。
- 登录取消、浏览器未安装、端口被占用、系统时间偏差和凭证库不可用。
- 插件首次安装、升级、降级、回滚、卸载、重装和 Go 凭证格式跨版本兼容。
- 文本、图片、音频、视频、附件、取消、恢复、`input_required` 和历史查询。
- 新 CLI 对旧服务端、旧 CLI 对新服务端的兼容测试。

其中不能全部依赖 Mock。六个平台至少各保留一台真实或稳定托管的 E2E 环境，完整兼容测试在海外测试环境执行；公司 GitHub 重新构建候选包后，再使用海外正式受控账号做最小冒烟。

### 6. 线上必须可观测、可止损、可支持

GA 不要求采集用户 Prompt、Token 或本地文件内容，但必须能回答“哪个版本、在哪一步、为什么失败”。

需要建设：

- 每个请求携带不含个人信息的 CLI 版本、`X-Source: cli`、宿主来源和 request ID。
- 服务端看板按低基数 `client_source` 标签覆盖登录成功率、刷新失败率、任务受理率、SSE 恢复率、产物下载率和错误码分布。
- `vivago-agent doctor --report` 生成可由用户主动提交的脱敏诊断报告。
- 客户端错误信息区分认证失败、网络失败、服务端拒绝、任务失败和产物失败。
- P0/P1 告警、值班联系人、事故处理流程、服务状态页和用户公告渠道。
- 最低支持版本、强制升级、远程停用高危版本和服务端回滚能力。
- 支持邮箱或工单入口，以及明确的响应时间。

### 7. 面向普通用户的法律和服务材料要齐全

公开 GitHub 仓库不等于已经满足面向普通用户运营的要求。正式发布前至少需要：

- Apache-2.0 LICENSE、NOTICE 和完整第三方依赖许可证清单。
- 公共产品网站、安装文档、卸载文档、支持入口和故障排查文档。
- Privacy Policy：说明登录信息、Prompt、上传文件、生成产物、诊断数据的用途、存储区域和保留时间。
- Terms of Service：说明账号、付费、内容责任、可用性和服务终止条件。
- `SECURITY.md`：漏洞报告渠道、支持版本和响应流程。
- 明确标注插件会执行本地二进制、访问哪些域名、读取哪些用户主动选择的文件。
- 删除仓库、Release、测试夹具、文档和日志中的内部域名、测试账号和密钥。

### 8. 要用真实运行数据证明可以扩量

下面是建议的内部 GA 门槛，不是 Codex 或 Claude 的官方数字：

- 公开 Beta 至少稳定运行 30 天，覆盖 100 名以上真实外部用户。
- 12/12 基础组合全部通过，扩展兼容矩阵无阻断问题。
- 干净机器安装成功率不低于 98%。
- 网页登录成功率不低于 98%。
- 排除明确业务拒绝后的任务受理成功率不低于 99.5%。
- 可恢复网络中断下的 SSE 恢复成功率不低于 99%。
- CLI 无崩溃会话比例不低于 99.5%。
- 连续 30 天无 P0/P1，未解决 P2 有明确负责人和期限。
- 升级、回滚和高危版本停用至少各演练一次。

达到这些指标后再把版本号升级到 `1.0.0`，比只看“测试通过”更能说明已经具备正式运营条件。

## 进入平台维护目录还要额外做什么

这一部分不阻塞 GitHub GA。

### Codex 公共目录

OpenAI 当前把公共插件发布到 ChatGPT 和 Codex 共用的 universal plugin directory；Git 仓库 Marketplace 仍是单独的本地、仓库和团队分发渠道。官方提交流程允许 Skills only、MCP only、Skills + MCP，因此进入目录并不天然要求 Hosted MCP。

提交前还需要：

- 在 OpenAI Platform 完成个人或企业身份验证。
- 提供公开的网站、支持地址、隐私政策、服务条款、品牌信息和发布说明。
- 准备至少五个正向用例和三个负向用例，以及审核可复现的测试账号或夹具。
- 通过 Skill 扫描和人工审核，确保输出不暴露个人数据、认证信息或内部调试字段。
- 预先向 OpenAI 确认“Skill 调用插件内置的六平台本地二进制”是否适合 universal directory。该目录同时服务 ChatGPT 和 Codex，而我们的本地 CLI 架构只适用于具备本地执行能力的宿主，不能假定一定会被接受。

官方资料：

- [OpenAI：Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [OpenAI：Submit plugins](https://developers.openai.com/plugins/deploy/submission)

如果本地二进制形态不符合公共目录审核要求，再评估 Hosted MCP + 标准 OAuth。这个决策应由实际审核反馈或明确的平台约束触发，不需要现在预付全部开发成本。

### Claude Code 社区和官方目录

Claude Code 支持用户添加 GitHub 自定义 Marketplace，也支持按 tag、branch 或 commit SHA 固定版本。第三方插件可以提交到 Anthropic 维护的 community marketplace，进入前会经过自动校验和安全筛查；官方 Marketplace 是否收录由 Anthropic 自行决定，公开提交通道默认进入的是社区目录，不是官方目录。

额外工作包括：

- 确保 Claude plugin manifest、Marketplace 版本和 Release Tag 一致。
- 按要求固定 source commit SHA，提供公开源码、许可证和安全说明。
- 通过 Anthropic 的自动校验和安全筛查。
- 对内置可执行文件的来源、签名、权限和网络行为提供可验证材料。
- 验证更新后当前会话的 reload 行为，以及第三方 Marketplace 默认不自动更新时的用户提示。

官方资料：

- [Claude Code：Discover and install plugins](https://code.claude.com/docs/en/discover-plugins)
- [Claude Code：Create and distribute a plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces)

## 工作量估算

以下估算以 Go 公开 Beta 已完成为起点；多项工作可以并行，但不能因为使用 Codex 就省略真实平台验证、外部审计和运营准备。

| 工作 | 主要责任方 | 预计时间 |
|---|---|---:|
| 服务端会话撤销、轮换和风控 | 海外登录/Web 后端 | 5～9 人日 |
| API 版本、幂等、原子约束和权限加固 | VivagoAgent 后端 | 5～9 人日 |
| macOS/Windows 签名和发布供应链 | CLI/DevOps | 3～6 人日 |
| Go CLI、Skill、登录和流水线安全审计及修复 | CLI + 安全 | 5～9 人日 |
| 扩展兼容矩阵和真实环境 E2E | CLI/QA | 4～7 人日 |
| 指标、告警、诊断和回滚体系 | 服务端/CLI/运维 | 3～5 人日 |
| 法律、隐私、支持和公开文档 | 产品/法务/研发 | 2～3 人日 |
| **GitHub GA 合计** |  | **27～48 人日** |

进入平台维护目录另计 8～15 人日，外加平台审核等待时间。若审核后决定引入 Hosted MCP + 标准 OAuth，应作为独立项目重新估算，初步预留 20～40 人日以上，不包含在本方案中。

## 推荐实施顺序

### 阶段 A：完成公开 Beta

按关联设计完成 Go 重写、六平台二进制和两套编译 profile。在个人 GitHub 开发包上使用海外测试环境完成 12 组合 E2E，再把源码晋级到公司 GitHub，由公司 CI 使用 `prod` profile 重新构建并完成海外正式受控冒烟。随后用 20～50 名外部用户验证安装和调用。

### 阶段 B：加固为 GitHub GA

优先处理服务端凭证撤销、API 幂等与权限、代码签名、安全审计和止损能力。这些项目完成后扩大到 100 名以上外部用户，连续运行 30 天并收集 GA 指标。

### 阶段 C：发布 1.0.0

全部 GA 门槛通过后，发布签名的 `1.0.0` Release 和稳定 Marketplace channel，同时保留 Beta/preview channel。完成回滚和高危版本停用演练后，再对外宣布正式版。

### 阶段 D：评估平台目录

GitHub GA 不等待平台目录。正式版稳定后分别提交 OpenAI 公共目录和 Anthropic 社区目录；先确认内置六平台二进制的审核可接受性，再决定是否需要 Hosted MCP 和标准 OAuth。

## GA Go/No-Go 清单

- [ ] Go 公开 Beta 设计已经全部实现，不再依赖 Python Runtime 和 `vivago-client`。
- [ ] 六个平台、两个宿主的基础 12/12 E2E 通过。
- [ ] 开发/测试包只访问海外测试环境，公开包只访问海外正式环境，运行时不能切换。
- [ ] 开发和正式凭证使用不同命名空间，无法互相读取或迁移。
- [ ] Beta/GA 由公司 GitHub 从评审后的源码重新构建，没有复用个人 GitHub 二进制。
- [ ] refresh token 可撤销、可轮换，并通过重放测试。
- [ ] 写请求具备幂等和数据库原子约束。
- [ ] 租户权限、上传下载和产物访问经过安全测试。
- [ ] macOS 完成签名和公证，Windows 完成代码签名。
- [ ] Release 包具备 checksum、SBOM、构建证明和完整许可证清单。
- [ ] 安全审计 Critical/High 为 0，关键 Medium 已修复或完成正式风险接受。
- [ ] 安装、升级、回滚、卸载和 Go 凭证格式跨版本兼容在扩展矩阵通过。
- [ ] 线上指标、告警、状态页、诊断报告和高危版本停用可用。
- [ ] Privacy Policy、Terms、SECURITY.md、支持入口和用户文档公开。
- [ ] 100 名以上外部用户稳定运行 30 天，达到约定的 GA 指标。
- [ ] `1.0.0` 发布和回滚演练完成。

## 最终判断

当前方向没有落伍，也不需要为了“看起来正式”立刻改成 Hosted MCP。最合理的路线是：先把 Go + 六平台 + GitHub Marketplace 的公开 Beta 做出来，再补服务端安全闭环、代码签名、安全审计、兼容性和运营能力，形成 GitHub GA；平台目录作为后续独立目标。

真正决定能不能叫正式版的，不是有没有 MCP，而是凭证能否失效、请求能否安全重试、二进制能否被信任、线上问题能否定位和止损，以及是否有真实用户稳定运行证据。
