# VivagoAgent CLI 生产附件 Hosted Runner 验证实施计划

日期：2026-08-17

关联设计：
[`2026-08-17-vivago-agent-cli-production-attachment-smoke-design.md`](2026-08-17-vivago-agent-cli-production-attachment-smoke-design.md)

## 阶段一：凭证 profile

1. 在 `internal/e2eauth` 测试中建立能区分 Keychain service/account 的内存实现。
2. 先写失败测试，证明 `prod` 的 seed/load/clear 不会访问 `dev` 凭证命名空间。
3. 给 options 和 clear 增加受限 profile，使用已有 `auth.ResolveCredentialProfile`。
4. 在 `cmd/vivago-e2e-auth` 中给 `seed`、`clear`、`publish` 增加 `--profile`，默认 `dev`。
5. 验证非法 profile 失败，输出不包含 ticket。

## 阶段二：生产单宿主验证器

1. 先扩展 `tests/test_hosted_l3_verifier.py`，约束 profile 映射、Codex 单宿主和生产报告。
2. 最小改造 `scripts/verify_hosted_l3.py`：默认行为保持 Dev/双宿主，显式生产调用使用
   `--expected-profile prod --host codex`。
3. Marketplace、plugin ID、channel、project link profile 和环境报告均从受限映射生成。
4. 报告删除项目、会话、Turn 和对象标识，只保留脱敏验收字段。

## 阶段三：独立生产 Workflow

1. 先在 `tests/test_github_workflows.py` 增加失败合同测试。
2. 新增 `.github/workflows/production-attachment-smoke.yml`。
3. Workflow 重建六目标生产包，但只在 macOS ARM64 安装和运行 Codex。
4. 使用 `production-beta` Environment 的一次性 ticket，始终清理 Runner 凭证。
5. 上传脱敏报告；不执行发布、Tag 或 Marketplace 更新。

## 阶段四：本地门禁

按顺序运行：

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
python -m unittest discover -s tests -v
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py plugin
```

同时扫描 Workflow、报告 fixture、文档和 Git diff，确认不存在真实 ticket、refresh token、
Authorization header、Cookie 或预签名 URL。

## 阶段五：受控线上验证

1. 使用生产 CLI 刷新本机 ticket，确认剩余有效期满足 Workflow。
2. 通过辅助命令把短期 ticket 写入公司仓库 `production-beta` Environment Secret。
3. 推送已审计的公司 `main`，手动触发生产附件 Workflow。
4. 等待 macOS ARM64/Codex Case 结束，下载并检查脱敏报告。
5. 无论成功失败，删除 GitHub Environment Secret。
6. 更新公开 Beta 进度文档和 Case 记录；只有附件及产物闭环全 PASS 才解除当前环境阻断。
