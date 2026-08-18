# VivagoAgent CLI Beta 回滚与停止发布演练设计

## 为什么要做这次演练

公开 Beta 发布后，如果某个版本出现高风险问题，不能移动已经发布的 Tag，也不能把
`marketplace` 强推回旧提交。正确做法是取一份确认可用的旧源码，用更高的 Beta 版本重新构建，
再让安装通道通过普通快进提交指向这个安全版本。

首个 `v0.3.0-beta.1` 还没有发布。直接用正式 Tag、Release 或真实 `marketplace` 演练会提前产生
外部安装入口，因此本次使用公司私有仓库中的临时 `drill/*` 分支。演练验证真实 GitHub 写入和
清理能力，但不改变任何正式发布对象。

## 这次怎么演练

### 一句话设计

手动 Workflow 分别从当前候选 SHA 和已通过门禁的安全 SHA 构建两个完整生产包，再把临时
Marketplace 从模拟问题版本快进到更高的安全版本；远端验证完成后自动删除临时分支。

### 执行过程

```text
公司 main 上手动触发演练
  -> 当前候选 SHA 构建 0.3.0-beta.1
  -> 安全 SHA 构建 0.3.0-beta.2
  -> 创建临时 drill/marketplace-<run-id> 产物分支
  -> 推送 beta.1，模拟当前安装通道
  -> 普通快进推送 beta.2，模拟安全版本接管
  -> 校验远端版本、源码 SHA、prod profile 和六平台产物
  -> 上传脱敏报告
  -> 删除临时分支并确认远端不存在
```

`beta.2` 的版本号更高，但源码来自已验证的安全 SHA。这就是正式事故中的“回滚代码、前进版本”。

## Workflow 怎么限制风险

新增的手动 Workflow 只接受公司仓库 `HiDream-ai/vivago-agent-cli` 的 `main`：

- 构建仍使用 `-tags prod`，只包含海外正式环境；
- 安全 SHA 必须是完整 Git SHA，并且是当前候选 SHA 的祖先；
- 模拟问题版本和安全版本必须符合 `X.Y.Z-beta.N`，且安全版本严格更高；
- 远端写入只能使用 `drill/marketplace-<run-id>-<attempt>`；
- 禁止创建或修改 Tag、Release、正式 `marketplace` 和 `production-beta` Environment；
- 临时分支只保存组装后的 Marketplace，不带源码历史；
- 清理 Job 使用 `always()` 执行；分支不存在视为已清理，删除失败则整次演练失败；
- 报告不记录凭证、请求内容、用户标识、预签名 URL 或业务对象 ID。

Workflow 权限按 Job 拆分：构建 Job 只有 `contents: read`，临时分支写入和清理 Job 才使用
`contents: write`。演练不读取生产凭证，也不向 VivagoAgent 提交任务。

## 怎么判断回滚成功

演练从构建 Job 开始计时，在远端临时分支确认安全版本后停止计时。必须同时满足：

1. 两个版本都完成六平台生产二进制构建和 Beta 分发校验；
2. 临时分支先出现模拟问题版本，再通过普通快进提交变为安全版本；
3. 安全版本的 `BUILD_INFO.json` 包含预期版本、安全源码 SHA、`channel=beta` 和 `profile=prod`；
4. 旧提交仍在临时分支历史中，没有强推；
5. 从开始构建到远端安全版本确认不超过 30 分钟；
6. 演练结束后，远端临时分支已经删除；
7. Workflow 没有创建 Tag、Release 或正式 `marketplace`。

演练报告保存版本、源码 SHA、临时提交 SHA、各阶段结果、耗时和清理结果。报告只作为私有
Actions Artifact 保存，不提交生成的二进制或 Marketplace 到源码分支。

## 生产监控怎么用

海外生产 `vivago-agent-system` 的请求日志已经记录 `client_source`、`client_version`、HTTP 状态、
接口路径和耗时；限流日志及指标也记录 `client_source=cli|unknown`。发布观察至少需要下面几类
聚合视图：

- 10 分钟 CLI 请求总量和 5xx 比例；
- 按 `client_version` 统计的版本分布；
- 登录/刷新失败、Project/Conversation/Turn 请求成功率；
- SSE 请求、非主动中断和 `RUN_ERROR`；
- 附件上传、产物下载和限流拒绝。

本次只做只读查询和运行手册，不修改生产告警。原始日志可能包含业务请求信息，演练记录只保存
聚合结果，不复制原始日志。

## 还缺的服务端能力

CLI 已发送 `X-Client-Version`，VivagoAgent 也会把版本写入请求日志，但当前源码中没有找到针对
CLI 高风险版本的拒绝规则。正式公开 Beta 前，需要由 VivagoAgent 或网关负责人确认：

- 阻断规则放在哪个服务；
- 配置由谁维护、如何审批和回滚；
- 命中后返回哪个稳定错误码和用户提示；
- 是否只影响 `X-Source: cli`，并继续保留用户全局限流；
- 如何先对测试版本演练，再用于生产。

这项能力不在 CLI 仓库中临时实现，也不会在未确认责任方和配置来源时直接操作生产。GitHub 演练
和监控查询完成后，工作会停在服务端确认节点。

## 第一轮实施范围

第一轮完成：

- 手动回滚演练 Workflow；
- 参数、分支名、版本递增、普通快进和清理的自动测试；
- 公司私有仓库真实临时分支演练；
- 脱敏报告和生产监控查询手册；
- 在公开 Beta 进度文档中记录结果和剩余阻断项。

第一轮不做：

- 发布 `v0.3.0-beta.1`；
- 创建正式 `marketplace`；
- 修改仓库可见性；
- 修改 VivagoAgent 或网关代码；
- 写入生产版本阻断配置或生产告警。

## 当前决定

采用公司私有仓库临时分支演练。正式事故恢复仍使用“旧安全源码 + 更高 Beta 版本 + Marketplace
普通快进”，不移动 Tag，不强推历史。GitHub 侧演练完成后，由服务端负责人确认版本阻断能力，
再决定第三步是否可以完整验收。
