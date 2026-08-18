# Vivago Agent CLI 坏版本封禁实施计划

## 目标

在 VivagoAgent 服务端增加只针对 `X-Source: cli` 的精确版本 denylist，命中时以 HTTP 426 阻止请求，同时保持 Web、App 和未命中 CLI 请求不变。

## 实施步骤

1. 配置解析红灯
   - 为 `VIVAGO_CLI_BLOCKED_VERSIONS` 编写空值、去空白和去重测试。
   - 运行目标测试并确认因功能不存在而失败。

2. 配置解析绿灯
   - 在 `src/config/` 增加不可变设置模型与加载函数。
   - 使用标准库解析，不引入第三方依赖。

3. 请求策略红灯
   - 使用最小 FastAPI 测试应用覆盖非 CLI、缺失版本、未命中和命中四类请求。
   - 确认命中用例在实现前失败。

4. 请求策略绿灯
   - 增加单一职责中间件。
   - 命中时返回 HTTP 426、`CLI_VERSION_BLOCKED` 和升级提示。
   - 将中间件接入生产应用，并确保现有请求日志仍能包裹封禁响应。

5. 回归验证
   - 运行新增测试。
   - 运行相关 client-source/middleware 测试。
   - 运行全量 pytest、ruff 和 mypy。

6. 交付记录
   - 更新部署配置说明，记录 ConfigMap 环境变量示例和回滚方式。
   - 提交独立分支，不合并、不部署生产，交由现有 VivagoAgent 发布流程处理。

7. 海外非生产演练
   - 先增加部署配置测试，使用临时 `0.0.0-policy-test` 哨兵演练，perf/prod 保持为空。
   - 更新 overseas dev 配置并让测试转绿；演练结束后清空 dev 哨兵并恢复基线镜像。
   - 功能分支临时部署后，使用编译版本为哨兵值的一次性 CLI 调用真实 Web API。
   - 记录命中 HTTP 426 的证据；随后清空 dev 配置、重新部署并记录恢复证据。

## 回滚

紧急解除封禁时，将 `VIVAGO_CLI_BLOCKED_VERSIONS` 置空并重新发布配置。代码回滚只需移除中间件注册和配置模块，不涉及数据迁移。

## 实施结果

- 已增加精确版本 denylist 配置加载器和 CLI 专用请求中间件。
- 已接入 overseas dev、perf、prod ConfigMap 输入，三处默认值均为空，不会在部署后自动封禁版本。
- 已增加 6 个策略测试；红灯首先因策略模块不存在而失败，随后实现转绿。
- 新增测试、client-source/request-log 回归、ruff 和 mypy 均通过。
- 仓库级回归在排除一个 `origin/dev` 已存在的 perf image 数量断言后为 `700 passed, 6 skipped, 1 deselected`。该基线失败与本改动无关，本分支未修改 perf image 配置。
- 已在海外 dev 临时部署功能分支，使用已认证的一次性 CLI 验证 `0.0.0-policy-test` 返回 HTTP 426、`CLI_VERSION_BLOCKED`。
- 已清空 dev 测试哨兵并恢复部署前的基线镜像；perf/prod 配置保持为空，未写入真实用户版本。
- CLI 已补齐受控的 `426 + CLI_VERSION_BLOCKED` 响应映射，机器输出保留稳定错误码和升级提示，其他 HTTP 错误仍保持脱敏。

## 当前进度（2026-08-18）

| 阶段 | 状态 | 证据/说明 |
| --- | --- | --- |
| 配置解析与精确匹配 | 已完成 | 空值、空白、去重、精确版本测试通过 |
| 请求中间件与应用接入 | 已完成 | 仅 `source=cli` 命中时返回 426 |
| 海外 dev 临时演练 | 已完成 | 功能分支镜像 `b521` 临时上线，真实只读请求命中 426 |
| 测试哨兵清理 | 已完成 | dev 配置恢复为空，镜像恢复 `b511` 基线，Argo 健康 |
| CLI 错误契约展示 | 已完成 | 输出 `CLI_VERSION_BLOCKED`，退出码 30 |
| 合并到 `dev` | 待执行 | 需基于清理后的功能分支创建/更新 MR 并完成评审 |
| 生产封禁配置 | 未执行 | 生产配置保持为空，不在本次合并中启用真实版本 |
