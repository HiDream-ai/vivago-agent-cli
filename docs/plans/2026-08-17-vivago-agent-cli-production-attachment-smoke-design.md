# VivagoAgent CLI 生产附件 Hosted Runner 验证设计

日期：2026-08-17

## 背景

生产候选 `0.3.0-beta.1` 已在本机完成登录、刷新、退出、重新登录、Codex 文本调用、Web
可见性和 SSE 断流恢复。附件上传在当前 Mac 上被本机网络、VPN 或代理出口阻断：生产和开发
环境返回相同上传 Host，当前均无法通过 CLI 的安全直连上传器完成 PUT。历史本机验证和 GitHub
Hosted Runner 海外测试验证曾成功，因此不能据此放宽上传器的 SSRF 边界。

## 已确认要求

- 使用公司 GitHub Hosted Runner 的干净公网出口验证生产附件和产物闭环。
- 新增独立生产验证 Workflow，不把测试环境 `hosted-l3.yml` 改成环境可切换入口。
- 本轮只验证 macOS ARM64 和 Codex，不运行 Claude Code，也不触发 Beta 发布。
- 使用生产登录产生的短期 ticket；不得上传 refresh token。
- 凭证只进入受保护的 `production-beta` GitHub Environment Secret，运行后删除。
- 仓库未来公开后，普通用户可以看到 Secret 名称和 Workflow，但不能看到 Secret 值。

## 方案比较

### 方案 A：独立生产附件验证 Workflow（采用）

新增只允许公司仓库 `main` 手动触发的 Workflow。它从当前 SHA 重建生产 Beta Marketplace，
只在 macOS ARM64 上安装 Codex，注入一次性 ticket，并验证附件识别、图片生成、预览和下载。

优点是生产和测试入口隔离、权限最小、审计清楚，失败不会触发 Tag、Release 或 Marketplace 更新。

### 方案 B：扩展现有 Hosted L3

给 `hosted-l3.yml` 增加 profile、平台和宿主输入。复用率更高，但会产生运行时环境选择入口，容易
混淆个人 Dev 与公司 Beta 边界，也与编译时 profile 原则相冲突。

### 方案 C：继续使用本机

切换本机网络或 VPN 后重试。成本低，但结果依赖当前电脑出口，不能证明公开 Beta 用户在标准公网
环境中的表现。

## 架构与数据流

1. 本机生产凭证保留在 macOS Keychain。
2. 发布辅助命令以显式 `prod` profile 读取本机 ticket，校验 JWT 剩余有效期。
3. 辅助命令通过标准输入调用 `gh secret set`，把 ticket 写入公司仓库的
   `production-beta` Environment Secret；stdout/stderr 不包含 ticket。
4. 手动 Workflow 只在 `HiDream-ai/vivago-agent-cli` 的 `main` 运行，权限为
   `contents: read`。
5. Workflow 从准确 SHA 使用 `-tags prod` 组装 Beta Marketplace，拒绝开发和国内地址。
6. macOS ARM64 Runner 把一次性 ticket 保存到隔离的生产凭证命名空间，refresh token 使用不可刷新
   哨兵值。
7. Codex 插件安装完成后，通过已组装的生产 CLI 完成：附件上传和识别、图片生成、产物预览和下载。
8. 报告只保留 PASS/FAIL、版本、SHA、平台、宿主和脱敏检查项；不保留项目、会话、Turn、对象存储
   Key、预签名 URL 或凭证。
9. Job 无论成功失败都清理 Runner 凭证。本机在运行结束后删除 Environment Secret。

## 安全边界

- Secret 不写入 Git、Workflow YAML、命令参数、构建产物或测试报告。
- 不在 PR、push 或 fork 事件中运行，仅允许公司 `main` 的 `workflow_dispatch`。
- 第三方 Action 固定完整 Commit SHA。
- Job 不授予写仓库、发布、OIDC 或证明权限。
- Secret 仅含短期 access ticket，不含 refresh token；失效后不能续期。
- GitHub 的日志掩码是辅助保护，不依赖日志掩码掩盖主动泄漏；验证器自身必须拒绝敏感字段。
- 拥有公司仓库写权限的人仍可能修改 `main` 上的 Workflow。仓库公开或套餐支持后，为
  `production-beta` 增加 required reviewer；在此之前由公司写权限、手动触发和仓库/分支硬校验
  共同承担授权边界。

## 组件改动

### 一次性凭证辅助工具

`cmd/vivago-e2e-auth` 的 `seed`、`clear` 和 `publish` 增加受限 `--profile dev|prod` 参数，默认
保持 `dev` 以兼容现有测试 Workflow。`internal/e2eauth` 接收 profile 并调用已有
`auth.ResolveCredentialProfile`，不接受 URL 或自定义凭证路径。

### Hosted L3 验证器

保留现有 Dev/双宿主默认行为，新增受限的预期 profile 和宿主选择：生产 Workflow 只能传
`prod` 与 `codex`。Marketplace 名称、插件 ID、channel、Web profile 和报告环境均由受限 profile
映射产生，不接受任意字符串。

### 独立 Workflow

新增 `production-attachment-smoke.yml`：

- 输入只包含符合 `X.Y.Z-beta.N` 的版本号；
- 固定公司仓库、`main`、生产 profile、macOS ARM64 和 Codex；
- 使用 `production-beta` Environment 和 `VIVAGO_E2E_TICKET`；
- 重建并校验生产 Marketplace；
- 运行附件和产物闭环；
- 上传脱敏 JSON 报告，保留 14 天；
- 不创建 Release、Tag、attestation 或 Marketplace 分支提交。

## 错误处理

- ticket 缺失、格式无效或剩余有效期不足：发布或 Runner seed 立即失败，错误不包含 ticket。
- 仓库、分支、版本或生产构建信息不匹配：在业务请求前失败。
- 上传失败：记录为生产附件验证失败，不自动改用代理、不重发 prompt、不触发发布。
- 图片生成或预览下载失败：停止当前 Case，不把部分结果认定为通过。
- 清理步骤始终运行；GitHub Secret 由本机在读取运行结果后删除。

## 测试与验收

- Go 单元测试证明 dev/prod 凭证命名空间相互隔离，非法 profile 失败关闭。
- 命令测试证明三个子命令支持受限 profile 且错误输出不含凭证。
- Python 测试证明验证器的生产 Marketplace、Codex 单宿主和脱敏报告逻辑。
- Workflow 合同测试证明手动、公司 main、只读权限、生产 Environment、无 refresh token、无
  Claude Code、无发布命令、Action SHA 固定。
- 本地完成 default/prod/race/vet、Python、分发和官方插件校验。
- Hosted Runner 最终以附件识别和产物 preview/download 全部 PASS 为验收；若失败，保留脱敏报告
  并继续区分生产存储问题和本机网络问题。

## 非目标

- 不修改上传器的直连、DNS 公网校验、TLS、端口和禁重定向策略。
- 不增加运行时环境或 URL 开关。
- 不运行 Claude Code、六平台矩阵、标准 OAuth、Hosted MCP 或正式 Beta 发布。
- 不把生产凭证长期留在 GitHub。
