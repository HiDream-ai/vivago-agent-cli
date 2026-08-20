# VivagoAgent CLI GitHub 开发 CI 设计

## 目标

为个人 GitHub 建立可重复的开发构建、校验和手动预发布闭环，并让同一套底层流水线以后可以直接迁移到公司 GitHub。开发流水线只生成 `dev` 制品；个人仓库没有任何切换到海外正式环境或发布正式版本的入口。

本期完成：

- Push、Pull Request 和手动触发的只读质量检查；
- 默认与 `prod` Go 单元测试、Race、Vet；
- 六个平台二进制构建和 `vivago-dev` Marketplace 组装；
- Codex、Claude Code 插件校验；
- checksum、版本来源和环境地址扫描；
- GitHub Actions Artifact 上传；
- 手动输入 `0.3.0-dev.N` 创建 GitHub Prerelease，并以精确 `force-with-lease` 将
  `dev-marketplace` 更新为当前版本的无父提交快照。

本期不完成：公司公开 Beta、海外正式环境冒烟、正式 Release、Hosted MCP、标准 OAuth、macOS 公证和 Windows 签名。

## 方案选择

### 方案 A：只上传 Actions Artifact

权限最小，但每次都需要人工下载、解压、提交 Marketplace 和创建 Prerelease，容易产生版本、来源提交和二进制不一致。

### 方案 B：自动 CI 与手动开发发布分离（采用）

自动 CI 永远只读；手动开发发布重新执行完整门禁，成功后创建 Prerelease 并更新 `dev-marketplace`。写权限只存在于发布 Job，版本和环境均由代码约束。

### 方案 C：每次合并自动发布开发版本

反馈最快，但需要自动决定版本号，也容易产生无意义版本和无法控制的外部更新，不适合当前阶段。

## 工作流结构

### `ci.yml`

触发方式：

- Pull Request；
- 推送到源码分支；
- 手动运行。

权限固定为 `contents: read`。流水线运行质量检查，构建六平台开发二进制，组装 Marketplace，完成两个宿主的静态校验和安全扫描，最后上传有保留期限的 Actions Artifact。它不创建 Tag、Release，不提交任何分支。

### `dev-release.yml`

只允许 `workflow_dispatch`。调用者输入符合 SemVer 的 `0.3.0-dev.N`，源码固定为启动工作流时选择的提交。发布前重新执行与自动 CI 相同的门禁，不信任其他工作流遗留的二进制。

发布 Job 使用最小的 `contents: write` 权限，并满足以下约束：

- 版本必须包含 `-dev.`，拒绝 Beta、RC 和稳定版本；
- 二进制必须是默认 `dev` profile，包含海外测试登录入口；
- 拒绝海外正式、国内环境地址和测试凭证之外的可疑敏感标记；
- GitHub Release 必须标记为 Prerelease；
- 只允许更新 `dev-marketplace`；
- 使用并发锁串行化开发发布，只允许发布机器人以准确旧 SHA 的 `force-with-lease` 更新快照；
- 已存在的 Tag/Release 不允许覆盖；
- Marketplace 提交记录版本和完整源码 SHA。

## 个人与公司 GitHub 复用

工作流和构建脚本不硬编码个人 GitHub Owner、仓库 URL或本地目录，统一使用 GitHub 上下文和当前仓库远端。

未来公司 GitHub 增加独立的 `beta-release.yml`：

- 复用相同的测试、六平台构建、插件校验、checksum 和环境扫描步骤；
- 发布入口固定 `profile=prod`，而不是允许用户在个人开发工作流中选择 profile；
- 版本固定为 `vX.Y.Z-beta.N`，Marketplace 名称固定为 `vivago`；
- 只接受公司仓库、受保护 Tag 和 GitHub Environment 审批；
- 由公司 CI 从源码重新构建，不复用个人 GitHub Artifact；
- 增加 SBOM、Artifact Attestation、正式账号冒烟和公司发布机器人权限。

因此，底层 CI 可以直接复用，但个人 `dev-release.yml` 不会被改造成一个可选择 `prod` 的万能发布按钮。

## 失败与恢复

- 任一测试、构建、校验、checksum 或环境扫描失败，均不得进入发布 Job。
- Marketplace 每版创建无父提交快照；如果远端在构建期间发生变化，精确租约使推送失败并由
  操作者确认远端状态后重新运行，不允许无租约强推或覆盖。
- Release 和 Marketplace 发布应保留清晰的来源 SHA。出现部分完成时允许安全重试，但不覆盖已有 Tag 或资产。
- 工作流日志不得输出登录凭证、Authorization Header、Cookie、预签名 URL 或完整敏感环境变量。

## 测试策略

先增加工作流契约测试，并确认它在 `.github/workflows/` 不存在时失败。测试至少约束：

- 自动 CI 的触发器和只读权限；
- 手动发布的输入、并发锁和最小写权限；
- 默认、prod、Race、Vet 和现有 Python 分发测试命令；
- 六目标构建、Marketplace 组装、两个插件校验器、checksum 和环境扫描；
- Artifact 上传、Prerelease 创建和 `dev-marketplace` 更新；
- 不存在自动正式发布、运行时 profile 输入和硬编码个人仓库。

实现后运行仓库全部 Go/Python 测试、官方 Codex 插件校验，并对工作流 YAML 做解析和契约检查。

## 后续待办

1. 通过新流水线发布永久的 `0.3.0-dev.4`。
2. 在 macOS ARM64 补完首次登录、退出重登、SSE 恢复、产物下载预览等双宿主验证。
3. 完成六平台乘两个宿主的真实安装矩阵。
4. 确认公司 GitHub 仓库、许可证、审批人、Tag 和 Marketplace 规则。
5. 在公司 GitHub 增加固定 `prod` profile 的 Beta 发布入口，并完成海外正式受控冒烟。

VivagoAgent 服务端 `Project`、`Conversation`、`Turn.source=cli` 落库以及日志、监控和限流归因已经完成，不再列为待办。
现有 API 功能用例已经 12/12 通过；待完成的 12 组合是六个平台乘 Codex、Claude Code 两个宿主的安装矩阵，两者不能混为一项。
