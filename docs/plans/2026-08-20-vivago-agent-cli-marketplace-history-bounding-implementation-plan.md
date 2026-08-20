# VivagoAgent CLI Marketplace 历史控制实施计划

## 目标

在不改变安装包内容、安装命令和运行方式的前提下，让 `dev-marketplace` 与 `marketplace` 每次发布
后都只保留一个无父提交的当前版本快照，并通过精确 `force-with-lease` 防止并发覆盖。

对应设计：
[Marketplace 历史控制设计](2026-08-20-vivago-agent-cli-marketplace-history-bounding-design.md)。

## 当前进度

| 阶段 | 状态 | 结果 |
|---|---|---|
| 1～2 共享脚本和测试 | 已完成 | 本地 Git 集成覆盖首次创建、连续替换、幂等、旧版本、过期租约、远端复核和调用仓库认证 |
| 3 个人 Dev 工作流 | 已完成 | Release 先于快照更新，支持内容完全一致的部分发布恢复 |
| 4 个人双版本实测 | 已完成 | `dev.9` 安全恢复；`dev.10` 完整 Actions 发布成功，12/12 宿主通过 |
| 5 公司 Beta 工作流 | 已完成 | 快照代码已进入 `main`；公开仓库默认权限满足“外部普通用户不可写”要求 |
| 6 文档和回归 | 进行中 | 待简化权限说明、全量回归和下一次 PR |

## 实施原则

- 测试先于实现；
- Dev 和 Beta 复用同一快照发布脚本；
- 先验证个人 Dev 通道，再允许公司 Beta 使用；
- Tag、Release 和证明材料继续不可变；
- 不在命令输出中暴露 Token、Authorization Header 或含凭证的远端地址。

## 阶段 1：建立快照发布脚本的失败测试

新增：

- `tests/test_marketplace_snapshot_publish.py`

测试使用临时裸 Git 仓库和小型假 Marketplace，不访问网络。先覆盖：

1. 远端分支不存在时创建一个无父提交快照；
2. 连续发布第二个版本后，分支仍只有一个可达提交；
3. 第二次发布后可达 Blob 只属于新快照；
4. 候选文件的可执行位得到保留；
5. 同版本、同来源、同内容重试不产生新提交；
6. 同版本但来源或内容不同失败关闭；
7. 旧版本不能覆盖新版本；
8. 远端 SHA 在读取后发生变化时，过期租约发布失败且远端不变；
9. 首次创建时发生竞争，后发任务不能覆盖已创建分支；
10. 错误输出不包含远端凭证。

先运行并记录预期失败：

```bash
python -m unittest tests.test_marketplace_snapshot_publish -v
```

## 阶段 2：实现共享快照发布脚本

新增：

- `scripts/publish_marketplace_snapshot.py`

必要行为：

- 参数包括候选 Marketplace、远端、分支、通道、版本和完整源码 SHA；
- 从候选 `BUILD_INFO.json` 再次核对参数、通道和 profile；
- 使用 `git ls-remote` 读取准确远端 SHA；
- 只抓取目标分支，不抓取全部远端历史；
- 校验现有版本与候选版本的单调关系；
- 在临时仓库创建无父提交，并保留文件模式；
- 比较候选树与现有树，实现安全幂等；
- 推送使用带准确旧 SHA 的 `force-with-lease`；
- 推送后重新读取远端并核验；
- 机器可读结果写 stdout，诊断写 stderr；
- 不回显可能含凭证的远端 URL 或 Git 环境变量。

根据复用情况，将
`scripts/validate_beta_marketplace_update.py` 的通用版本比较逻辑抽到共享模块；保留现有入口或同步
迁移调用方，避免发布恢复测试失效。

通过标准：阶段 1 的 10 类测试全部通过。

## 阶段 3：接入个人 Dev 发布流水线

先修改失败的工作流契约测试：

- `tests/test_github_workflows.py`

再修改：

- `.github/workflows/dev-release.yml`

改造点：

- 删除内联的 fetch、worktree、普通提交和普通 push；
- 调用共享快照发布脚本更新 `dev-marketplace`；
- 明确传入 `channel=dev`、候选版本和 `${GITHUB_SHA}`；
- 保留发布并发锁；
- 不允许 Workflow 输入远端、分支、profile 或环境地址；
- 调整顺序，确保不可变 Prerelease 已创建或已验证可恢复后，才改变安装通道；
- 为 Dev 增加与 Beta 同等级的“Release 已创建但 Marketplace 未更新”安全重试判断，避免部分发布。

本地验证：

```bash
python -m unittest tests.test_marketplace_snapshot_publish tests.test_github_workflows -v
python -m unittest tests.test_go_build_matrix tests.test_go_distribution tests.test_dev_distribution_verifier -v
```

## 阶段 4：个人 GitHub 双版本实测

在个人仓库先发布两个新的 `-dev.N` 版本；版本号以执行时个人仓库已有最高 Dev 版本为基线，严格
递增，不预先硬编码。每版完成现有六平台构建和宿主生命周期门禁。

第二版发布后验证：

```bash
git clone --single-branch --branch dev-marketplace <personal-repository> <temporary-directory>
git -C <temporary-directory> rev-list --count HEAD
git -C <temporary-directory> rev-list --parents -n 1 HEAD
```

验收结果：

- 提交数为 `1`；
- HEAD 没有父提交；
- 当前版本、源码 SHA、六平台文件和 checksum 正确；
- 隔离 Codex 配置完成全新安装、Marketplace 刷新和插件升级；
- Claude Code 自动化生命周期用例完成 Marketplace 更新和插件升级；
- 上一版 Release 资产仍可下载并用于回滚验证；
- 不运行 VivagoAgent 业务生成任务，不消耗生产资源。

如果任一宿主不能跟随被改写的分支升级，停止公司 Beta 接入，保留原快进发布方式并重新评估独立
Marketplace 仓库或按平台下载方案。

实际执行结果：

- `0.3.0-dev.9` 的不可变 Release 已创建，首次 Marketplace 推送失败后使用原始 Release 资产安全补齐；
- 新源码重跑同一版本被 Release 源码 SHA 校验拒绝，没有覆盖旧 Tag 或资产；
- `0.3.0-dev.10` 从新源码完成构建、12/12 宿主生命周期、Prerelease 和 Marketplace 自动更新；
- 切换前 `dev.8` 为 6 个可达提交、252,698,711 字节可达 Blob；切换后 `dev.10` 为 1 个无父
  提交、42,395,079 字节可达 Blob；
- `dev.9` 和 `dev.10` Release 均保留，安装命令和六平台自包含包没有变化。

## 阶段 5：接入公司 Beta 发布流水线

前置条件：阶段 4 全部通过，并确认外部普通用户没有公司仓库写权限。公司研发继续沿用现有
Write/Admin 权限，不额外限制其更新安装分支。

修改：

- `.github/workflows/beta-release.yml`
- `tests/test_github_workflows.py`
- `tests/test_beta_release_resume.py`

改造点：

- 保留现有 Beta Release 恢复和版本单调校验；
- 使用共享脚本替换内联快进更新；
- 固定 `channel=beta`、`branch=marketplace`，禁止作为手动输入；
- Release 已存在的安全恢复路径只能更新与该 Release 内容一致的快照；
- 精确租约冲突必须失败，不能自动重试为无租约强推；
- 发布后核验远端快照 SHA、版本和构建来源。

不在此阶段实际发布新的生产 Beta；先通过 Pull Request、Beta Check 和个人通道证据完成代码门禁。

快照工作流和契约测试已经通过 PR 进入公司 `main`。公司仓库为 Public，外部普通用户没有 Write
权限，不能直接更新或强推 `marketplace`；公司研发可以更新安装分支，符合当前确认的权限要求。
因此不新增 Deploy Key、Actions Secret 或 Ruleset，也不修改现有 Workflow 认证。下一次真实 Beta
继续验证六平台、双宿主、Release、attestation、单提交快照和生产观察。

## 阶段 6：回归、文档和交付

更新：

- `docs/github-actions-operation-guide.md`
- `docs/go-dev-marketplace.md`
- `docs/vivago-agent-cli-beta-rollback-runbook.md`
- `docs/plans/2026-08-08-vivago-agent-cli-public-beta-validation-progress.md`
- 对应 `historical_prompts/` 记录
- 一个 `changelog.d/` Markdown 片段

运行：

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
python -m unittest discover -s tests -v
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py plugin
```

最终报告至少包含：

- 修改前后的安装分支提交数和可达 Blob 体积；
- Dev 两次发布的脱敏 Workflow 证据；
- Codex/Claude Code 安装与升级结果；
- 精确租约冲突和幂等重试结果；
- 公司分支规则是否满足上线条件；
- 明确说明尚未实际发布新的生产 Beta。

## 预计工作量

| 阶段 | 预计 |
|---|---:|
| 共享脚本与 Git 集成测试 | 0.5 天 |
| Dev Workflow、恢复路径和本地回归 | 0.5 天 |
| 个人 GitHub 双版本验证 | 0.5 天 |
| Beta Workflow、文档和全量回归 | 0.5 天 |
| 合计 | 1～2 天 |

外部等待时间主要来自六平台 Workflow，不计入纯开发时间。
