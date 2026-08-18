# VivagoAgent CLI 公开 Beta 总进度

更新时间：2026-08-18

| 项目 | 当前状态 |
| --- | --- |
| 长期源码分支 | `main` |
| 开发版本 | `0.3.0-dev.8` |
| 首个生产候选 | `0.3.0-beta.1` |
| 环境 | 海外测试（`profile=dev`）和海外生产（`profile=prod`） |
| 是否已经公开发布 | **没有** |
| 当前进行到 | **第 4 步收口：个人 dev CI 已通过，公司 Beta Check 已触发** |

### 2026-08-18 最新状态

VivagoAgent 版本阻断 MR #356 已合并到 `dev`，合并提交为 `8fe5d448…`。海外测试曾临时同步
功能分支验证 `0.0.0-policy-test`，认证只读请求返回 HTTP 426；CLI 已将该响应显示为稳定的
`CLI_VERSION_BLOCKED` 升级提示。验证后海外测试环境已恢复原 revision，Argo Health=Healthy；
没有手动触发新的部署，生产阻断配置仍为空。

CLI 修复已提交到个人 GitHub `main`（`5f75b14`），并随提交 `15f6fc6` 同步到公司 GitHub
`main`。公司 Beta Check 已由该提交触发，目前只执行生产候选构建、插件校验、SBOM 和产物门禁；
Beta Tag、Release 和官方 Beta Marketplace 均尚未创建。

个人 Development CI [#32101640741](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/32101640741)
已通过：默认/prod/race/vet、分发测试、Codex/Claude 插件校验、六平台开发二进制、Marketplace
组装、checksum/provenance/环境边界检查和开发产物上传全部成功；Beta Check 按个人仓库策略跳过。

## 现在到哪一步了

公开 Beta 按五步推进。前 3 步已经完成，现在进入第 4 步收口；仓库公开和 `v0.3.0-beta.1`
发布还没有开始。

| 步骤 | 要完成的事情 | 当前状态 | 已有证据 | 还差什么 |
| ---: | --- | --- | --- | --- |
| 1 | 完成 CLI、插件包、六平台构建和双宿主安装门禁 | **已完成** | L0/L1 为 6/6，L2 为 12/12；`v0.3.0-dev.8` 已发布到个人开发通道 | 无首个 Beta 阻断项 |
| 2 | 用生产候选完成代表平台验收 | **已完成** | macOS ARM64/Codex 已通过生产登录、刷新、退出重登、任务、SSE、附件、产物和 Web 可见性 | 生产六平台真人登录和 Claude Code 模型调用不在本轮范围 |
| 3 | 验证出问题后能否安全恢复并停止继续发布 | **已完成** | 公司 Beta Check 全绿；真实临时分支演练用 170 秒完成普通快进恢复并自动清理；VivagoAgent MR #356 已合并；海外测试命中 HTTP 426 后已恢复 | 生产发布前继续保持阻断配置为空 |
| 4 | 完成公开仓库、法务和发布治理确认 | **进行中** | 个人 Development CI 已通过；公司 Beta Check 已触发；`production-beta` Environment 已准备 | 等待公司 Beta Check 收口，并确认许可证/治理和公开仓库审批 |
| 5 | 发布 `v0.3.0-beta.1` 并观察生产指标 | **未开始** | 发布流水线已经具备生产构建、六平台、双宿主、checksum、SBOM 和 attestation 门禁 | 第 3、4 步通过后，由发布人手动批准 |

### 第 3 步目前做到哪里

回滚演练实现和第一轮真实远端演练已经完成：

- 公司 `main` 手动触发的 `Beta Rollback Drill` Workflow；
- 公司仓库、分支、版本号、安全源码 SHA 和临时分支名校验；
- 用问题版本和更高恢复版本构建两份真实 `prod` Marketplace；
- 只向 `drill/marketplace-*` 临时分支做普通快进提交，结束后自动删除；
- 禁止创建 Tag、Release、正式 `marketplace`，也不读取生产业务凭据；
- 本地回滚脚本和 Workflow 合同测试，目前专项结果为 30/30 PASS。
- Python 全量 129/129、Go 默认/生产、Race、Vet 和官方 Codex 插件校验均已通过。
- 公司 Beta Check [#32092763621](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32092763621)
  在准确源码 `41af5bd` 上全绿，覆盖 6/6 原生平台和 12/12 双宿主生命周期；
- 回滚演练 [#32093162498](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32093162498)
  从开始构建到远端恢复确认耗时 170 秒，低于 1800 秒目标；
- 恢复提交的父提交等于模拟问题提交，证明使用普通快进，没有改写历史；
- 演练结束后临时分支为 0，正式 `marketplace` 不存在，Tag 和 Release 均为 0；
- 公司、个人 GitHub 和 Codeup 的 `main` 均已同步到 `41af5bd`。

第 3 步的 GitHub 恢复链路和服务端版本阻断链路已经验收，服务端责任边界也已确定：由 VivagoAgent 根据
`X-Source: cli` 和 `X-Client-Version` 执行精确版本 denylist，不复用内容投放的
`delivery_targets`，也不把规则放到 Agent Gateway。下面的完成条件中，前六项已有证据，第七项
已完成设计、合并和海外非生产命中/恢复演练：

1. 完整 Python 和 Go 回归通过（已完成）；
2. 实现提交并同步到公司、个人和 Codeup 的 `main`（已完成）；
3. 公司 GitHub 实际创建临时分支，先写入模拟问题版本，再以更高版本恢复到安全源码（已完成）；
4. 从开始构建到远端恢复确认不超过 30 分钟（170 秒，已完成）；
5. 临时分支已删除，正式 Tag、Release 和 `marketplace` 没有变化（已完成）；
6. 生产结构化日志已经能看到 `source=cli` 和 `client_version`；聚合查询模板已写入运行手册（已完成）；
7. VivagoAgent 使用 `VIVAGO_CLI_BLOCKED_VERSIONS` 精确阻断高风险 CLI 版本，命中返回 HTTP 426
   和 `CLI_VERSION_BLOCKED`；清空配置即可解除。MR #356 已合并，海外非生产命中和清空恢复已完成。

详细设计和执行步骤见：

- [Beta 回滚与停止发布演练设计](./2026-08-18-vivago-agent-cli-beta-rollback-drill-design.md)
- [Beta 回滚演练实施计划](./2026-08-18-vivago-agent-cli-beta-rollback-drill-implementation-plan.md)
- [Beta 回滚演练运行手册](../vivago-agent-cli-beta-rollback-runbook.md)

## 接下来做什么，什么时候需要你介入

| 顺序 | 下一项工作 | 谁处理 | 是否需要你现在介入 |
| ---: | --- | --- | --- |
| 1 | 个人 GitHub dev CI 验证 CLI 修复并生成开发产物 | **已完成**；[Development CI #32101640741](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/32101640741) | 无 |
| 2 | 将同一 CLI 提交同步到公司 GitHub `main`，运行 Beta Check | **已完成，Beta Check 运行中** | 同一提交 `15f6fc6` 已推送到公司 `main`，运行 [Beta Check #32102647493](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32102647493) | 等待 CI 结果；不触发发布 |
| 3 | 发布窗口确认海外生产 Loki stream selector | VivagoAgent 发布执行人 | 发布前确认，不阻塞当前代码开发 |
| 4 | 审批仓库公开和首个 Beta 发布 | 公司管理员/发布人 | **必须由你或指定发布人确认** |

## 已经验证了哪些能力（L0–L3）

| 层级 | 主要验证什么 | 当前结果 | 状态 | 关键证据 | 还缺什么 |
| --- | --- | ---: | --- | --- | --- |
| L0 | 六平台交叉编译、Marketplace 组装、checksum、环境地址扫描和静态门禁 | 6/6 | 已通过 | [Development Release #31484366464](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31484366464)、[v0.3.0-dev.8](https://github.com/ChaoXia-Beginer/vivago-agent-cli/releases/tag/v0.3.0-dev.8) | 代码签名和公证不属于首个 Beta 阻断项 |
| L1 | 在真实 OS/CPU Runner 上启动对应二进制，验证 launcher、`version` 和 `doctor` | 6/6 | 已通过 | dev.8 发布门禁的六平台原生报告 | 六个平台均为真实目标 Runner，不使用兼容层代替 |
| L2 | Codex/Claude Code 插件安装、发现、升级、回滚、再升级 | 12/12 | 已通过 | [Development Release #31484366464](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31484366464)，12 份脱敏报告 | 宿主模型主动选择 Skill 另行验证；本轮仅验证 Codex |
| L3 | 通过安装后的插件 CLI 调用真实 VivagoAgent Web API，验证任务、SSE、附件和产物 | Dev 12/12；Prod 1/1 | 代表范围已通过 | [Dev Hosted L3 #31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974)；[Production Attachment Smoke #32024362266](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32024362266) | 生产只验证 macOS ARM64/Codex；Claude Code 模型调用本轮不验 |

这里的计数口径不同：L0/L1 按六个平台计数，L2/L3 按“六个平台 × 两个宿主”计数。

## 六个平台的结果

| 目标平台 | GitHub Runner | 插件 launcher | L0 构建 | L1 原生启动 | L2 Codex/Claude | Dev L3 Codex/Claude |
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

## 开发版 dev.8 验证基线

| 项目 | 当前值 |
| --- | --- |
| 开发版本 | [`v0.3.0-dev.8`](https://github.com/ChaoXia-Beginer/vivago-agent-cli/releases/tag/v0.3.0-dev.8) |
| Marketplace 源码 | `72fb98d5b3d88058033fc1b04d1a262866524468` |
| L3 工作流源码 | `ce633432adf922e31deb28a6fa297ec0831fcc75` |
| Codex CLI | `0.147.0` |
| Claude Code | `2.1.220` |
| API 目标 | `https://dev.vivago.ai`，编译期固定，不提供运行时 `--env` 切换 |
| 请求归属 | `X-Source: cli`、`X-Client-Platform: web` |
| 发布运行 | [Manual Development Release #31484366464](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31484366464) |
| 最终 L3 运行 | [Manual Hosted L3 #31232383974](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31232383974) |
| 个人 main 对齐后 CI | [Development CI #31485750215](https://github.com/ChaoXia-Beginer/vivago-agent-cli/actions/runs/31485750215) |
| 公司 main Beta Check | [Beta Check #31483042861](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/31483042861) |
| 生产候选源码 | `15ba0bc87eb8ad211cb8adf6850a6e925b8f5a93` |
| 生产附件与产物 | [Production Attachment Smoke #32024362266](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32024362266) |

## 2026-08-17 生产 Beta 代表平台验收

生产候选从公司 `main` 的准确 SHA `15ba0bc87eb8ad211cb8adf6850a6e925b8f5a93` 使用
`-tags prod` 构建，版本为 `0.3.0-beta.1`。本轮不发布 Tag、Release 或 Marketplace，只验证生产
环境和代表平台。

| 用例 | 结果 | 证据和边界 |
| --- | --- | --- |
| 首次生产网页登录 | PASS | 生产 `/agent/login` 与随机 loopback Form POST 回调成功，凭证保存至生产 Keychain 命名空间 |
| `auth refresh` | PASS | 强制刷新成功，stdout 只有 `refreshed=true` 与 `backend=keychain` |
| `auth logout` / 重登 | PASS | 退出后状态为未登录，第二次浏览器登录后恢复为已登录 |
| Codex 选择生产插件 | PASS | 隔离 Codex 安装 `vivago-agent-cli@vivago`，完成一条低成本文本 Turn；没有直调业务 API |
| Web 可见性 | PASS | 生产 CLI 创建的项目、请求和回复可在 `vivago.ai` 打开 |
| SSE 断流恢复 | PASS | 在非终态事件后断开，使用同一 Turn 和 cursor 恢复；13 个后续事件、0 个重复事件 ID、1 个 `RUN_FINISHED`，没有重发 prompt |
| 本机附件上传 | PASS | `prod` 构建通过标准环境代理兼容代码完成附件上传、服务端读取、图片生成和 `RUN_FINISHED`；本机 Clash 仅对对象存储域名增加精确直连规则，其他流量仍按原规则代理 |
| Hosted Runner 生产附件 | PASS | 公司 Run `32024362266` 的 macOS ARM64/Codex 识别红绿蓝测试图，证明生产上传凭证和对象存储公网路径可用 |
| 图片生成 | PASS | 同一生产会话生成一张图片并返回已验证产物 |
| 产物预览与下载 | PASS | preview/download 内容一致；脱敏报告记录 `image/jpeg`、447040 字节，不记录对象标识或 URL |
| 一次性凭证治理 | PASS | GitHub 只接收短期 ticket，不含 refresh token；Runner `always()` 清理 Keychain；运行后删除 Environment Secret并确认列表为空 |
| Claude Code 模型调用 | 本轮不验 | 用户明确移出本轮；L2 插件安装生命周期证据仍为 12/12 |
| Beta 发布 | 未执行 | 该 Workflow 只有 `contents: read`，不会创建 Tag、Release、attestation 或更新 Marketplace |

### 本机上传问题与最终处理

历史海外测试本机附件成功、Hosted Runner Dev 12/12 和公司 macOS ARM64 生产附件冒烟都是真实
结果。2026-08-17 的对比还证明 Dev/Prod 返回同一上传 Host，服务端生产上传凭证和对象存储公网路径
可用，因此没有放宽上传器的 SSRF、重定向和公网 DNS 校验。

本机后续定位到两个独立问题。第一，普通 API 已支持 `http.ProxyFromEnvironment`，但附件上传和产物
下载原先固定 `Proxy: nil`，只配置 `HTTP_PROXY`/`HTTPS_PROXY`、没有 TUN 的用户会出现 API 可用而
附件失败。提交 `5754da9` 已让 API、上传和下载统一兼容标准环境代理，同时保留原安全检查。

第二，这台 Mac 的 Clash 把 `storage.googleapis.com` 命中 Google 通用代理规则，两个代理节点都在 TLS
阶段关闭连接。全局直连虽然能访问对象存储，却会中断 Codex，因此最终只在本机增加精确的对象存储
直连规则，其他流量继续走原代理。使用 `-tags prod` 构建的当前 CLI 随后完成附件上传、服务端读取、
SSE、图片生成、`RUN_FINISHED`、preview 和 download；预览与下载字节数一致且文件非空。该 Clash
规则是本机网络配置，不进入插件源码或公开 Beta 包。

## 2026-08-11 dev.8 发布前收口

| 用例 | 结果 | 当前证据和边界 |
| --- | --- | --- |
| `auth refresh` | PASS | Keychain 刷新成功，随后仍为已登录且无需刷新；未输出凭据 |
| `auth logout` | PASS | 退出后立即检查为未登录 |
| 浏览器重新登录 | PASS | 通过海外测试 `/agent/login` 和 loopback 回调恢复 Keychain 登录态 |
| Codex 自然语言选择 Skill | PASS | 全新 Codex 会话主动选择 `vivago-agent-cli`，依次执行诊断、鉴权、项目创建和单次文本任务，Turn 正常结束 |
| Claude Code 自然语言选择 Skill | 本轮不验 | 插件包已升级到 dev.8；宿主模型账号失效后，用户明确将该项移出本轮验收范围，没有提交 VivagoAgent Turn |
| CLI 项目在 Web 可见 | PASS | Web 页面展示同一项目标题、用户请求和 VivagoAgent 回复，证明复用服务端项目与会话历史 |
| 公司 `production-beta` Environment | PASS（有限制） | 已创建并只允许公司 `main`；当前私有仓库套餐不支持 reviewer/wait timer，暂由仓库写权限与手动发布入口承担人工授权 |
| 海外生产登录与 L3 | 当时 BLOCKED/ENV | 2026-08-11 时生产 `/agent/login` 尚未部署；已由上方 2026-08-17 生产验收结果替代 |

本轮在线用例严格使用 dev.8 编译期固定的海外测试环境。没有复用 App API、没有把测试凭据注入生产构建，也没有把项目、Conversation 或 Turn 标识写入仓库文档。

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
| Python 验证器测试 | 118/118 PASS | 包含 Dev/Beta workflow、六平台、双宿主、供应链、生产 Secret边界和 L3 报告契约 |
| Codex 官方本地校验 | PASS | 插件 manifest 和目录结构有效 |
| Claude 插件校验 | PASS | Claude Code 能识别插件结构 |
| 六平台构建 | 6/6 PASS | darwin/linux/windows × arm64/amd64 |
| Marketplace 和 checksum | PASS | 发布产物与 `BUILD_INFO.json` 一致 |
| 环境地址扫描 | PASS | dev 包保持海外测试环境，不混入生产地址 |

`v0.3.0-dev.8` Release 指向 `72fb98d...`，包含一份完整开发 Marketplace；对应运行还上传了 12 份 L2 生命周期报告。

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
- 最新 `v0.3.0-dev.8` 又在 L2 的 12 个原生 Job 中调用了六个平台的 launcher 和 `doctor`，全部为 `doctor_exit=0`。因此当前二进制的原生启动不是只依赖旧版本报告。

## L2：两个宿主的安装、升级和回滚

L2 使用 Codex 和 Claude Code 的官方插件管理命令，不直接复制插件到宿主目录。

### 每个组合实际执行的四个阶段

| 阶段 | 插件版本 | 验证内容 |
| --- | --- | --- |
| 全新安装 | `0.3.0-dev.7` | 从开发 Marketplace 安装，定位宿主隔离目录中的 launcher，运行 `doctor` |
| 升级 | `0.3.0-dev.8` | 更新 Marketplace 和插件，确认加载新版本 launcher |
| 回滚 | `0.3.0-dev.7` | 回退到上一开发版本，确认旧版本仍可运行 |
| 再升级 | `0.3.0-dev.8` | 再次升级并确认最终状态回到候选版本 |

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
| 报告源码 | 全部为 `72fb98d5b3d88058033fc1b04d1a262866524468` |

门禁通过后，流水线才创建 `v0.3.0-dev.8` Prerelease 并更新 `dev-marketplace`。如果任意一个平台或宿主失败，发布步骤不会执行。

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
| `X-Client-Version` | VivagoAgent 请求日志和 dev.8 本机验证 | `0.3.0-dev.5`（Hosted L3）/ `0.3.0-dev.8`（本机收口） |
| Project 持久化 | 海外测试 Mongo | 未直接查询 |
| Conversation 持久化 | 海外测试 Mongo | 未直接查询 |
| Turn 持久化 | 海外测试 Mongo | 未直接查询 |
| Web 页面可见 | 浏览器人工检查 | PASS；CLI 创建的项目、请求和回复可见 |

当前本机 Mongo 只读工具只配置了正式库，没有海外测试库目标。为了避免拿测试 ID 查询正式库或临时拼接数据库凭据，本轮没有直接读取海外测试 Mongo。Web 可见性证明 Project、Conversation 和 Turn 由服务端持久化并可被 Web 复用，但不能代替对 `source` 字段值的数据库只读查询。服务端补齐 `Project / Conversation / Turn.source=cli` 及日志、监控、限流统计由服务端研发确认完成。

## 当前 Beta 还要做什么

以下估时只计算开发和验证时间，不包含账号、权限、证书或跨团队排期等待。

| 优先级 | 工作 | 当前状态 | 预计工作量 | 前置依赖 | 验收标准 | 是否需要你介入 |
| --- | --- | --- | ---: | --- | --- | --- |
| P0 | 代理兼容和回滚演练提交进入公司 `main` | **已完成**；公司、个人和 Codeup 远端 `main` 均为 `41af5bd` | 已完成 | 完整本地门禁和公司 Beta Check | 三个远端 `main` 指向同一已验证提交 | 无 |
| P0 | 海外测试登录、刷新、退出重登 | macOS ARM64 PASS | 其余平台按风险决定是否扩展 | dev.8、海外测试账号 | 当前代表平台流程已闭环 | 当前无需介入 |
| P0 | 宿主模型主动选择 Skill | Codex PASS；Claude Code 本轮移除 | Claude 后续如恢复范围约 0.25 天 | 可用宿主账号 | 自然语言触发、模型主动加载 Skill，不手工执行 launcher | 本轮不需要 |
| P0 | `source/platform` 数据库持久化 | 服务端研发确认完成；日志与 Web 证据已具备，未直接查测试库字段 | 只读补证约 0.25 天，可后置 | 海外测试 Mongo 只读目标 | 精确核对三类对象的 `source=cli` | 需要协调只读权限时再介入 |
| P0 | Web 页面可见性 | PASS | 已完成 | 海外测试 Web 登录 | CLI 项目、请求和回复可在 Web 打开 | 无 |
| P1 | 公司 GitHub Beta 流水线 | **已完成**；[#32092763621](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32092763621) 在 `41af5bd` 全绿 | 已完成 | 回滚演练提交进入公司 `main` | prod profile、checksum、SBOM、attestation、六平台和双宿主门禁全部通过 | 发布时需要最终确认 |
| P1 | `production-beta` 发布边界 | Environment 与 main 限制已完成；reviewer 受 GitHub 套餐限制 | 仓库公开或套餐升级后约 0.25 天补 reviewer | GitHub 计划支持 | Environment 至少一名 reviewer | 届时需要管理员配置/确认 |
| P1 | 海外正式环境受控 Beta | 代表平台 PASS | 发布前只需复核准确候选 SHA | 公司 Beta Check | 登录、刷新、退出重登、任务、SSE、附件和产物均通过 | 发布时需要最终确认 |
| P1 | 回滚与停止发布演练 | **已完成**；真实恢复 170 秒、临时分支已清理、正式对象未变化；MR #356 已合并，海外非生产命中/恢复已完成 | 已完成 | VivagoAgent MR 合并和海外非生产部署窗口 | 30 分钟内恢复安装通道；坏版本命中 HTTP 426；清空配置后恢复 | 无 |
| P2 | macOS 公证、Windows 签名 | 未开始 | 2–5 天 | Apple Developer ID、Windows 代码签名证书 | 安装和首次运行不触发无法解释的 Gatekeeper/SmartScreen 风险 | 需要公司提供证书和签名主体 |

下一轮按以下顺序执行：

1. 验证个人 GitHub `main` 的 dev CI，确认 CLI 修复生成开发产物。
2. 将同一提交同步到公司 GitHub `main`，运行公司 Beta Check。
3. 发布窗口由执行人核对海外生产 Loki stream selector 和监控模板字段。
4. 完成法务和仓库公开审批后，再单独批准 `v0.3.0-beta.1` 发布。

## 哪些结论可以对外说

| 可以确认 | 暂时不能确认 |
| --- | --- |
| 六个平台都能构建并原生运行 CLI | 标准登录已经覆盖六个平台 |
| Codex/Claude Code 都能安装、升级、回滚插件 | Claude Code 模型会主动选择 Skill（本轮明确未验） |
| ticket-only 在线任务在 12 个组合全部通过 | 海外生产标准登录已经覆盖六个平台 |
| 文本、附件、SSE、图片产物、取消和历史已跑真实海外测试环境 | `source/platform` 已由本轮直接查询数据库证明 |
| macOS ARM64 已完成生产登录、刷新、退出重登、Codex 任务、SSE 恢复、附件和产物验证 | 生产代表验证等于六平台都完成真人登录和模型调用 |
| dev.8 在 macOS ARM64 的刷新、退出、重登和 Codex 自然语言调用通过 | `source=cli` 已由本轮直接查询测试数据库证明 |
| CLI 创建的验证项目和对话可在海外测试 Web 页面打开 | 所有 CLI 项目和所有平台的 Web 可见性均已逐一验证 |
| dev.8 Release、公司 Beta Check、生产附件冒烟和报告可追溯 | 公司 GitHub Beta 已经公开发布 |

当前准确说法是：

> VivagoAgent CLI 的 L0/L1/L2 已完成，ticket-only L3 在六平台 × 两宿主上为 12/12；macOS ARM64
> 代表平台已完成海外生产登录、Codex 任务、SSE 恢复、附件和产物验证。第 3 步的 GitHub 回滚
> 演练已用 170 秒完成安全版本普通快进恢复，临时分支已清理，正式发布对象未变化；VivagoAgent
> 的 CLI 精确版本 denylist 已合并并完成海外非生产命中/解除演练。当前等待个人 dev CI 和公司
> 个人 dev CI 已通过，公司 Beta Check 正在收口。仓库尚未公开，
> `v0.3.0-beta.1` 尚未发布，也没有执行部署、Tag、Release 或 Marketplace 发布。

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
| 回滚演练 | `41af5bd` | 增加临时分支回滚演练、自动清理和运行手册 |

方案细节见 [`2026-08-07-vivago-agent-cli-six-platform-two-host-test-design.md`](./2026-08-07-vivago-agent-cli-six-platform-two-host-test-design.md)。
