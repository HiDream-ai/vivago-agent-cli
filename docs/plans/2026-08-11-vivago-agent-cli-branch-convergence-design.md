# VivagoAgent CLI 分支收敛设计

日期：2026-08-11

## 目标

把当前分散在 Codeup 和个人 GitHub 的源码分支收敛到 `main`，为公司 GitHub 的公开
Beta 开发建立稳定、可审计的分支模型。清理过程必须先建立可恢复的归档 Tag，再切换默认
分支，最后删除旧分支；不得通过强推或重写历史完成清理。

## 审计结论

- `feature/go-public-beta` 是当前 Go CLI 和插件的完整源码线，应成为新的 `main`。
- Codeup 的 `master` 和 `zijian` 没有相对当前源码线的独有提交。
- Codeup 的 `pilot-marketplace` 保存三个旧 Python Pilot 发布提交，需要先用不可变 Tag
  归档，之后才能删除分支。
- 个人 GitHub 的 `dev-marketplace` 是开发版安装与回滚通道，在公司 Beta 上线前继续保留。
- 旧 Pilot 提交已经存在于当前仓库的祖先历史中。删除分支不会把这些提交从完整历史中
  移除，因此未来公开的公司仓库不能直接镜像当前仓库的全部历史。

## 执行结果

2026-08-11 已完成本设计中的现有仓库收敛：

| 检查项 | 结果 |
|---|---|
| Codeup 默认分支 | `main` |
| 个人 GitHub 默认分支 | `main` |
| 两个远端迁移基线 | 同一提交 `f02b509` |
| GitHub Development CI | `main` Push 门禁通过 |
| Codeup 长期分支 | 仅 `main` |
| 个人 GitHub 长期分支 | `main`、`dev-marketplace` |
| Codeup Pilot 恢复点 | 四个 `archive/*` Tag 均已验证 |
| 本地分支 | 仅 `main` |
| Codex detached worktree | 保留，未修改 |

首次把多个远端 Push 串联执行时，Codeup SSH 没有返回输出。该进程被安全中止后，改为按远端
分别执行，并仅对本仓库当前命令设置 `BatchMode` 和连接超时；所有 Push 随后成功。过程中没有
修改 Git 全局配置、系统凭证助手或其他仓库配置。

## 目标分支模型

| 仓库 | 长期分支 | 临时分支 | 说明 |
|---|---|---|---|
| Codeup | `main` | `feature/*`、必要时 `release/0.3` | 内部源码协作和备份 |
| 个人 GitHub | `main`、`dev-marketplace` | `feature/*` | 开发 CI、开发插件安装与回滚 |
| 公司 GitHub | `main`、CI 生成的 `marketplace` | `feature/*`、短期 `release/0.3` | 公开 Beta 和后续正式发布 |

不维护永久 `prod` 分支。开发和生产环境由编译 profile 决定：默认构建固定海外测试，
`-tags prod` 固定海外生产。生产发布通过受保护的版本 Tag 和审批流水线完成。

## Codeup 迁移顺序

1. 检查 Workflow、脚本和文档是否写死旧分支名。
2. 从当前完整源码提交建立并推送 `main`。
3. 把 Codeup 默认分支切换为 `main`。
4. 验证 `main` 可以正常拉取，且与迁移前源码提交一致。
5. 在 Codeup 建立以下归档 Tag：
   - `archive/codeup-master-2026-08-11`
   - `archive/pilot-marketplace-0.2.0-pilot.1`
   - `archive/pilot-marketplace-0.2.0-pilot.2`
   - `archive/pilot-marketplace-0.2.0-pilot.3`
6. 验证归档 Tag 可以解析到预期提交。
7. 删除远端 `master`、`zijian`、`pilot-marketplace` 和 `feature/go-public-beta`。

任何一步验证失败都停止删除。已经推送的 `main` 和归档 Tag 不回滚；旧分支保留到问题解决。

## 个人 GitHub 迁移顺序

1. 把当前完整源码推送为 `main`。
2. 将默认分支切换为 `main`。
3. 验证 `main` 的开发 CI 和手动 Workflow 可用。
4. 删除 `feature/go-public-beta`。
5. 保留 `dev-marketplace` 以及现有开发 Prerelease/Tag，直到公司 GitHub Beta 通道完成迁移。

## 公司 GitHub 公开 Beta 边界

公司 GitHub 初始阶段使用私有仓库完成权限、流水线和生产构建验证。由于当前仓库包含旧 Pilot
祖先历史，公司仓库从评审后的 Go 源码树建立干净初始历史，不做完整历史镜像，也不复制个人
GitHub 的开发二进制或 `dev-marketplace`。

公司仓库公开前至少完成许可证、敏感信息、依赖许可证、生产地址扫描和构建产物审计。公开
Beta 使用 `v0.3.0-beta.1` 等受保护 Tag，由公司 CI 使用 `prod` profile 重新构建，并更新
CI 生成的 `marketplace` 分支。

## 本地清理边界

- 当前工作目录切换并跟踪 `main`。
- 在远端迁移验证完成后删除本地 `master`、`pilot-marketplace` 和
  `feature/go-public-beta`。
- 清理已经失效且可判定为 prunable 的旧 Pilot worktree 元数据。
- 不删除或修改 Codex 正在使用的 detached worktree。

## 验收标准

- Codeup 和个人 GitHub 的默认源码分支都是 `main`。
- 两个远端的 `main` 指向相同的已验证源码提交。
- Codeup 旧 Pilot 发布提交均有可解析的归档 Tag。
- Codeup 不再存在 `master`、`zijian`、`pilot-marketplace` 和
  `feature/go-public-beta` 分支。
- 个人 GitHub 仅保留 `main` 和开发安装所需的 `dev-marketplace` 长期分支。
- Workflow 和操作文档不再把 `feature/go-public-beta` 当作主分支。
- 分支清理不修改 Git 全局配置，不影响其他仓库的拉取、提交和推送。
