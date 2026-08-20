# VivagoAgent CLI Beta 回滚演练运行手册

## 适用范围

本手册用于公司 GitHub 私有仓库中的内部回滚演练，以及公开 Beta 发布后的真实恢复操作。
内部演练只使用 `drill/marketplace-*` 临时分支，不创建正式 Tag、Release 或 `marketplace`。

真实事故恢复遵循同一原则：已经发布的 Tag 和 Release 不覆盖，不把 Marketplace 指回旧问题版本；
从确认可用的旧源码构建一个版本号更高的 Beta，再将当前版本快照更新到安装通道。安装分支本身由
发布机器人使用精确 `force-with-lease` 受控更新，以避免累积多平台二进制历史。

内部 `Beta Rollback Drill` 仍使用临时分支上的普通快进提交，用来证明安全源码能在 30 分钟内构建
更高版本并完成恢复；它不会验证正式 `marketplace` 的快照强推权限。正式通道首次使用无父快照前，
仓库管理员还需确认 GitHub Actions 可以受控改写 `marketplace`，同时人员不能直接强推该分支。
2026-08-20 的只读检查结果为 ruleset 为空、`marketplace` 未保护，因此当前只允许继续代码评审和
Beta Check，不允许用新快照逻辑发布下一版 Beta。

## 演练前检查

执行人先确认：

- 当前操作仓库是 `HiDream-ai/vivago-agent-cli`，触发分支是 `main`；
- 恢复源码是完整的 40 位 Commit SHA，并且属于当前 `main` 的祖先；
- 恢复源码已经通过公司 Beta Check；
- 模拟问题版本与恢复版本属于同一发布线，恢复版本号严格更高；
- 本次操作不需要生产 Ticket、Cookie、Token 或 VivagoAgent 测试账号。

首轮演练使用 `0.3.0-beta.1` 作为模拟问题版本、`0.3.0-beta.2` 作为恢复版本。它们只存在于临时
产物分支，不代表已经对外发布。

## 启动内部演练

在公司仓库 Actions 页面选择 `Beta Rollback Drill`，点击 `Run workflow`，填写：

- `incident_version`：模拟问题版本；
- `recovery_version`：更高的恢复版本；
- `recovery_revision`：已验证安全源码的完整 Commit SHA。

也可以使用 GitHub CLI：

```bash
gh workflow run beta-rollback-drill.yml \
  --repo HiDream-ai/vivago-agent-cli \
  --ref main \
  -f incident_version=0.3.0-beta.1 \
  -f recovery_version=0.3.0-beta.2 \
  -f recovery_revision=<safe-full-commit-sha>
```

工作流会按运行编号生成唯一分支
`drill/marketplace-<run-id>-<attempt>`。不要手工创建同名分支。

## 通过标准

以下条件必须全部满足：

| 检查项 | 通过条件 |
| --- | --- |
| 两份产物 | 六个平台均使用 `prod` profile 构建并通过分发校验 |
| 更新方向 | 恢复版本高于模拟问题版本 |
| Git 历史 | 恢复提交的父提交就是模拟问题提交，没有强推 |
| 远端状态 | 临时分支先指向问题版本，再快进到恢复版本 |
| 恢复时间 | 从开始构建到远端确认不超过 1800 秒 |
| 清理 | 工作流结束后临时分支不存在 |
| 正式对象 | 没有新增正式 Tag、Release 或 `marketplace` 分支 |
| 报告 | Artifact 仅包含版本、Commit SHA、耗时和清理结果 |

报告 Artifact 名称为
`beta-rollback-drill-report-<run-id>-<attempt>`，默认保留 14 天。

## 失败后人工清理

如果 Runner 被强制终止，自动清理可能来不及执行。先从 Workflow 名称或日志中取得准确的
`run-id` 和 `attempt`，再删除对应分支：

```bash
git push origin --delete drill/marketplace-<run-id>-<attempt>
git ls-remote --exit-code --heads origin \
  refs/heads/drill/marketplace-<run-id>-<attempt>
```

第二条命令返回状态码 `2` 表示分支不存在，清理完成。不要使用通配符批量删除，也不要运行
`git push --force`。

随后只读复核：

```bash
gh api repos/HiDream-ai/vivago-agent-cli/git/matching-refs/heads/drill/marketplace-
gh release list --repo HiDream-ai/vivago-agent-cli
git ls-remote --heads origin refs/heads/marketplace
```

只有临时分支清理完成、正式对象未变化，演练才能结束。

## 发布后的聚合监控

CLI 请求已携带 `X-Source: cli` 和 `X-Client-Version`。发布观察只保存聚合结果，不复制原始日志。
运行查询前，由 VivagoAgent 运维负责人确认当前海外生产的 Loki stream selector；下面用
`<vivago-agent-stream-selector>` 表示这个受部署配置管理的选择器。

10 分钟 CLI 请求量：

```logql
sum(
  count_over_time(
    <vivago-agent-stream-selector> | json | client_source="cli" [10m]
  )
)
```

10 分钟 CLI 5xx 比例：

```logql
sum(count_over_time(
  <vivago-agent-stream-selector> | json
  | client_source="cli" | status_code >= 500 [10m]
))
/
sum(count_over_time(
  <vivago-agent-stream-selector> | json | client_source="cli" [10m]
))
```

按 CLI 版本统计请求量：

```logql
sum by (client_version) (
  count_over_time(
    <vivago-agent-stream-selector> | json | client_source="cli" [10m]
  )
)
```

实际字段名如果与当前日志 schema 不一致，应由 VivagoAgent 运维负责人更新查询模板；不要在发布
窗口临时猜字段。观察至少覆盖请求量、5xx、登录或刷新失败、Project/Conversation/Turn、SSE、
附件与产物、限流拒绝。原始 Prompt、用户标识、凭证、业务对象 ID 和预签名 URL 不得写入演练报告。

## 真实事故时的额外步骤

版本阻断由 VivagoAgent 负责。服务端通过海外环境 ConfigMap 的
`VIVAGO_CLI_BLOCKED_VERSIONS` 配置完整版本号 denylist，只对 `X-Source: cli` 且
`X-Client-Version` 精确命中的请求返回 HTTP 426、`CLI_VERSION_BLOCKED` 和升级提示。缺失版本、
未命中版本及 Web/App 请求继续放行。

CLI 只解析该受控的 `426 + CLI_VERSION_BLOCKED` 错误契约，机器输出保持
`error.code=CLI_VERSION_BLOCKED`，并使用业务错误退出码 `30`。其他非成功 HTTP 响应继续按既有
脱敏规则处理，不透出原始响应、凭证或授权头。

启用前先在海外非生产环境写入一个测试版本，确认命中后将配置清空并重新发布，验证请求恢复。
真实事故解除封禁同样通过清空该配置完成。GitHub 安装通道恢复和服务端版本阻断必须分别留证；
任何演练都不得把真实已发布版本写入生产 denylist。

恢复版本发布后还要核验：新 Release 指向准确安全源码，`marketplace` HEAD 没有父提交，
`BUILD_INFO.json` 指向新的更高版本，并且旧 Release 仍可读取。不要用旧 Release 直接覆盖当前
安装分支；旧资产只用于审计、兼容性验证和人工排查。
