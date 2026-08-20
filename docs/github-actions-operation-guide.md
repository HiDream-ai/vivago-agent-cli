# GitHub CI/CD 操作手册

当前个人 GitHub 仓库采用“自动 CI、手动发布”的方式：代码 Push 或提交 Pull Request 后自动检查，但不会自动生成用户可安装的新版本。准备发布时，由维护者在 GitHub Actions 页面选择源码分支、输入版本号并手动启动发布。

当前三个 Workflow 的用途如下：

| Workflow | 配置文件 | 怎么触发 | 会不会发布 |
| --- | --- | --- | --- |
| Development CI | `.github/workflows/ci.yml` | Push、Pull Request，或手动运行 | 不会，只上传保留 14 天的 Artifact |
| Manual Development Release | `.github/workflows/dev-release.yml` | 手动运行并输入开发版本号 | 会，更新 `dev-marketplace` 并创建 GitHub Prerelease |
| Manual Hosted L3 | `.github/workflows/hosted-l3.yml` | 准备好测试凭证后手动运行 | 不会，只验证已发布版本的真实 API |

## 平时推送代码后会发生什么

向 GitHub 源码分支 Push，或创建 Pull Request 后，`Development CI` 自动执行：

1. 运行默认配置和 `prod` 配置的 Go 测试；
2. 运行 Race、Vet 和 Python 分发测试；
3. 交叉编译 macOS、Linux、Windows 的 ARM64/x64 六份二进制；
4. 组装 `vivago-dev` Marketplace；
5. 校验 Codex 和 Claude Code 插件；
6. 检查 checksum、版本来源和环境地址；
7. 上传保留 14 天的开发 Artifact。

这一步会构建六个平台，但所有工作主要在 Ubuntu Runner 上完成，不能代替六种目标机器上的原生运行验证。Push 到自动生成的 `dev-marketplace` 分支不会再次触发 CI，避免发布提交形成循环。

查看结果：

1. 打开当前 GitHub 仓库；
2. 点击顶部 **Actions**；
3. 左侧选择 **Development CI**；
4. 打开本次提交对应的 Run；
5. 确认 `Test, validate, and package dev Marketplace` 为绿色。

任何检查失败都不应继续发布。打开失败的 Job 和 Step，可以看到具体测试或构建错误；日志中不得粘贴或输出 ticket、token、Cookie、Authorization Header 和预签名 URL。

## 手动跑六平台原生验证

需要确认六个平台的 launcher 能选择并启动正确二进制时，手动运行 `Development CI`：

1. 进入 GitHub 仓库的 **Actions** 页面；
2. 左侧选择 **Development CI**；
3. 点击右侧 **Run workflow**；
4. 选择需要验证的源码分支，例如 `main`；
5. 再点击绿色 **Run workflow**。

手动触发后，常规 CI 仍会先执行。通过后，GitHub 再启动六个平台的原生 Runner：

| 目标 | GitHub Runner |
| --- | --- |
| macOS ARM64 | `macos-26` |
| macOS x64 | `macos-26-intel` |
| Linux ARM64 | `ubuntu-24.04-arm` |
| Linux x64 | `ubuntu-24.04` |
| Windows ARM64 | `windows-11-arm` |
| Windows x64 | `windows-2025` |

每个平台会解压同一份 Marketplace，检查目标系统和 CPU，并通过 launcher 运行 `version` 和 `doctor`。这能证明六个平台的 CLI 可以原生启动，但不验证 Codex/Claude Code 的完整安装生命周期，也不调用 VivagoAgent 在线接口。

命令行等价操作：

```bash
gh workflow run ci.yml --ref main
```

## 手动发布开发版本

发布会产生用户可安装的新开发版本，不能只因为一次普通 CI 通过就直接跳过发布门禁。

操作步骤：

1. 确认准备发布的代码已经提交并 Push 到 GitHub；
2. 确认该提交对应的 `Development CI` 已经通过；
3. 进入 **Actions**，选择 **Manual Development Release**；
4. 点击 **Run workflow**；
5. 选择要发布的源码分支；
6. 输入不带 `v` 前缀的新版本号，例如 `0.3.0-dev.6`；
7. 点击绿色 **Run workflow**。

命令行等价操作：

```bash
gh workflow run dev-release.yml \
  --ref main \
  -f version=0.3.0-dev.6
```

发布 Workflow 不直接复用普通 CI 的二进制，而是从所选源码提交重新完成以下步骤：

```text
测试、构建和分发校验
        ↓
六平台 × Codex/Claude Code，共 12 个插件生命周期 Job
        ↓
创建或验证不可变 GitHub Prerelease
        ↓
用精确租约更新无父提交的 dev-marketplace 快照
```

12 个插件生命周期 Job 分别验证全新安装、升级、回滚和再次升级。任一平台或宿主失败，发布 Job 都不会执行。

版本号必须满足以下要求：

- 输入 `0.3.0-dev.6`，不要输入 `v0.3.0-dev.6`；
- 每次使用新的版本号；
- 已经存在的 Git Tag 或 Prerelease 不允许覆盖；只有版本、源码 SHA 和资产摘要完全一致时，才允许
  从 Marketplace 步骤继续恢复；
- 当前个人仓库只发布 `vivago-dev`，固定使用海外测试环境，不能通过参数切换到 `prod`。

发布成功后检查：

1. Actions 页面所有 Build、12 个 Host lifecycle 和 Publish Job 都是绿色；
2. GitHub **Releases** 中出现对应的 `v0.3.0-dev.N` Prerelease；
3. `dev-marketplace` 分支的插件版本和源码 SHA 已更新；
4. `dev-marketplace` 的 HEAD 没有父提交，安装分支只保留当前版本快照；
5. 用 Codex 或 Claude Code 刷新 Marketplace 后能安装或升级到该版本。

公司 `Publish Beta` 使用同一个快照脚本，但固定为 `channel=beta`、`branch=marketplace`，并从公司
`main` 使用 `prod` profile 重新构建。个人开发包和二进制不能直接进入公司安装通道。公司仓库为
Public，外部普通用户没有写权限，不能更新或强推 `marketplace`；Fork 也拿不到公司 Workflow 的
写权限和 Environment Secret。公司研发保留现有 Write/Admin 权限，可以更新安装分支。

`Publish Beta` 使用 Job 级 `contents: write` 的 `GITHUB_TOKEN` 和精确 `force-with-lease` 更新快照。
精确租约防止并发任务和过期任务误覆盖，但不限制已经拥有公司仓库写权限的研发。如果以后要增加
人员写入限制，应单独设计 Ruleset 和专用发布身份，不作为当前 Beta 的发布前置。

## 手动跑真实接口 L3

L3 用已发布的开发插件访问 VivagoAgent 海外测试环境，覆盖项目、会话、任务、SSE、附件、产物、取消和历史等在线流程。它不是每次 Push 的必跑项，通常在候选版本发布后执行。

运行前需要确认：

- 待验证版本已经通过 `Manual Development Release` 发布；
- `dev-marketplace` 已指向该版本；
- 已取得该版本对应的完整 40 位源码 SHA；
- GitHub Environment `overseas-test-e2e` 临时配置了一次性 Secret `VIVAGO_E2E_TICKET`；
- 当前 Workflow 只允许从 `main` 分支运行。

不要把 ticket 写进 Workflow、文档、Issue、命令参数或日志。测试结束后应删除临时 Secret；Runner 无论成功还是失败都会执行本地凭证清理步骤。

网页操作：

1. 进入 **Actions**，选择 **Manual Hosted L3**；
2. 点击 **Run workflow**；
3. 选择 `main`；
4. `version` 输入已经发布的版本号，不带 `v`；
5. `source_revision` 输入该版本对应的完整源码 SHA；
6. 点击绿色 **Run workflow**；
7. 等待六个平台串行完成，并检查上传的脱敏报告。

命令行等价操作：

```bash
gh workflow run hosted-l3.yml \
  --ref main \
  -f version=0.3.0-dev.6 \
  -f source_revision=<40位源码SHA>
```

当前 L3 使用一次性 ticket，只验证已登录状态下的业务 API。它不覆盖首次网页登录、token 刷新、退出重登、Codex/Claude 模型是否主动选择 Skill、数据库字段落库和 Web 页面展示。

## 一次开发版本建议怎么走

普通开发只需要 Push 代码并等待自动 CI。准备发布候选版本时，按下面的顺序操作：

1. Push 源码，等待自动 `Development CI` 通过；
2. 如需单独检查六平台原生启动，手动运行一次 `Development CI`；
3. 手动运行 `Manual Development Release`，输入新的 `0.3.0-dev.N`；
4. 确认 12 个插件生命周期 Job 和 Publish Job 全部通过；
5. 有真实在线回归需求并且已准备临时 ticket 时，再运行 `Manual Hosted L3`；
6. 保存脱敏报告和 Run 链接，删除 L3 临时 Secret。

## 失败后怎么处理

| 失败位置 | 结果 | 处理方式 |
| --- | --- | --- |
| 自动 CI 的测试、构建或扫描 | 不发布 | 修复源码后重新 Push |
| 六平台原生冒烟 | 不发布 | 打开失败平台的 Job，检查 Runner、launcher 和二进制输出 |
| 12 个插件生命周期 Job | 不发布 | 根据失败的目标平台和宿主检查安装、升级或回滚阶段 |
| 版本号已存在且源码或资产不同 | 不发布且不覆盖旧版本 | 使用新的开发版本号，不删除或覆盖旧 Tag |
| 版本号、源码和资产完全一致 | 允许恢复未完成的 Marketplace 步骤 | 保持同一源码重跑；若源码已经变化，必须改用新版本 |
| `dev-marketplace` 在发布期间变化 | 精确租约不匹配，快照更新失败 | 确认远端版本和 SHA 后重新运行发布，禁止无租约强推 |
| Hosted L3 的在线接口失败 | 已发布版本不会自动回滚 | 保留脱敏报告，按平台、阶段和请求 ID 排查；必要时停止推广该版本 |

个人 GitHub 的发布流程不会生成正式环境版本。迁移到公司 GitHub 时可以复用测试、六平台构建和插件校验，但公开 Beta 必须使用独立且固定为 `prod` 的发布 Workflow、公司审批和受保护的 Tag，不能复用个人 GitHub 生成的开发二进制。
