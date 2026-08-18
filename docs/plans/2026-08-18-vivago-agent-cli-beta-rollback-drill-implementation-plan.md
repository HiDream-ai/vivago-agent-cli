# VivagoAgent CLI Beta 回滚演练实施计划

## 实施目标

在不创建正式 Tag、Release 或 `marketplace` 的前提下，使用公司私有仓库的临时 `drill/*` 分支完成
一次真实远端回滚演练。演练需要证明：安全源码可以重新构建为更高 Beta 版本，安装通道通过普通
快进提交完成替换，全过程不超过 30 分钟，临时分支最终被删除。

设计依据见
[`2026-08-18-vivago-agent-cli-beta-rollback-drill-design.md`](2026-08-18-vivago-agent-cli-beta-rollback-drill-design.md)。

## 实施顺序

### 1. 先定义输入校验

新增 `tests/test_beta_rollback_drill.py`，先确认测试因为校验脚本缺失而失败，再实现
`scripts/validate_beta_rollback_drill.py`。

输入校验覆盖：

- 公司仓库和 `main`；
- 完整的候选 SHA 和安全 SHA；
- 安全 SHA 不能等于候选 SHA；
- 模拟问题版本和安全版本均符合 Beta SemVer；
- 安全版本严格高于问题版本；
- 临时分支必须符合 `drill/marketplace-<run-id>-<attempt>`；
- 30 分钟耗时上限。

脚本只输出 JSON Envelope；诊断写 stderr，不输出环境变量、Token 或远端 URL。

### 2. 先定义 Workflow 安全约束

在 `tests/test_github_workflows.py` 增加失败测试，再实现
`.github/workflows/beta-rollback-drill.yml`。测试至少证明：

- 只能手动触发；
- 只允许公司 `main`；
- 构建 Job 为只读，写权限只出现在临时分支 Job；
- 使用现有生产构建和分发校验脚本；
- 安全 SHA 必须是当前 SHA 的祖先；
- 只推送 `drill/marketplace-*`；
- 更新使用普通快进，不包含 `--force`；
- Cleanup Job 使用 `always()` 并删除同一临时分支；
- 不出现 `gh release create`、`git tag`、`HEAD:marketplace`、生产 Secret 或
  `production-beta` Environment；
- 所有第三方 Action 固定完整 Commit SHA。

### 3. 构建两份真实生产包

Workflow 在公司 `main` 上运行：

1. 当前 `GITHUB_SHA` 作为模拟问题源码，构建 `0.3.0-beta.1`；
2. 手动输入的安全 SHA 必须是当前提交祖先；
3. 在独立 Git worktree 中从安全 SHA 构建 `0.3.0-beta.2`；
4. 两份包都执行六平台构建、`verify_beta_distribution.py` 和归档；
5. 把构建开始时间写入内部元数据，供后续计算恢复耗时。

首轮演练使用已经通过公司 Beta Check 的 `26ed642bdf88855c01fd716f616896e24769bb21`
作为安全 SHA。

### 4. 在临时远端分支完成两次提交

写入 Job 创建 orphan 产物分支：

1. 写入模拟问题 Marketplace，提交并推送；
2. 读取现有 `BUILD_INFO.json`，使用 `validate_beta_marketplace_update.py` 校验版本递增；
3. 用安全 Marketplace 完整替换分支内容，产生第二个提交；
4. 以普通快进推送并读取远端引用；
5. 校验第二个提交的父提交是第一个提交，安全包版本、源码 SHA、profile 和 channel 正确；
6. 计算从构建开始到远端确认的耗时，超过 1800 秒则失败。

### 5. 无论成功失败都清理

Cleanup Job 使用确定性分支名，不依赖前序 Job 输出：

- 远端分支存在时执行删除；
- 分支不存在时记录为无需清理；
- 删除后再次查询，仍存在则失败；
- 上传隐私安全的结果报告；
- 源码仓库、正式 Tag、Release 和 `marketplace` 保持不变。

如果 Runner 被强制终止导致 Cleanup 没有执行，运行手册给出按准确分支名人工删除和复核的命令。
运行手册位于
[`vivago-agent-cli-beta-rollback-runbook.md`](../vivago-agent-cli-beta-rollback-runbook.md)。

### 6. 验证和记录结果

本地先运行：

```bash
python -m unittest tests.test_beta_rollback_drill tests.test_github_workflows -v
python -m unittest discover -s tests -q
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
```

提交并同步三个 `main` 后，手动触发公司 Rollback Drill Workflow。演练完成时记录：

- Workflow URL、准确源码 SHA 和安全 SHA；
- 模拟问题/安全版本；
- 两个临时 Marketplace 提交；
- 恢复耗时；
- 临时分支删除结果；
- 正式 Tag、Release、`marketplace` 未变化的只读检查；
- 生产 CLI 聚合日志可查询的证据。

GitHub 演练通过后停止继续操作，向 VivagoAgent 或网关负责人确认 CLI 版本阻断的责任服务、配置
来源、错误码、回滚方式和测试办法。该确认完成前，第三步不能标记为全部完成。

## 第一轮执行结果

2026-08-18 已完成第一轮真实演练：

| 项目 | 结果 |
| --- | --- |
| 演练源码 | `41af5bd033ec30ab8bec66e03c3f54465a56250f` |
| 安全源码 | `26ed642bdf88855c01fd716f616896e24769bb21` |
| 模拟问题版本 | `0.3.0-beta.1` |
| 恢复版本 | `0.3.0-beta.2` |
| 公司 Beta Check | [#32092763621](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32092763621)，PASS |
| 回滚演练 | [#32093162498](https://github.com/HiDream-ai/vivago-agent-cli/actions/runs/32093162498)，PASS |
| 恢复耗时 | 170 秒，低于 1800 秒目标 |
| Git 历史 | 恢复提交父提交等于模拟问题提交，普通快进成立 |
| 清理 | `cleanup=deleted`，远端 `drill/marketplace-*` 为 0 |
| 正式对象 | `marketplace` 不存在，Tag 0，Release 0 |
| 远端同步 | 公司、个人 GitHub 和 Codeup 的 `main` 均为 `41af5bd` |

GitHub 侧验收已完成。当前按计划停在服务端确认点：需要 VivagoAgent 运维负责人确认海外生产
Loki stream selector，并由 VivagoAgent 或网关负责人确认 CLI 版本阻断的责任服务、配置来源、
稳定错误码、用户提示、回滚和非生产演练方式。
