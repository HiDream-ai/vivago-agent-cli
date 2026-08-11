# VivagoAgent CLI 公开 Beta 实施计划

日期：2026-08-11

关联设计：
[`2026-08-11-vivago-agent-cli-public-beta-release-design.md`](2026-08-11-vivago-agent-cli-public-beta-release-design.md)

## 当前实施状态

截至 2026-08-11，本分支已完成生产 Beta 构建与 Marketplace 组装、仓库绑定策略、六平台原生
门禁脚本、双宿主生命周期门禁、公司规范 Go module 地址、SPDX 2.3 SBOM 和 GitHub 构建证明
Workflow。公司 GitHub PR #1 的 Beta Check（run `31481271742`）已经完成 L0、六平台原生启动和
12 个双宿主生命周期用例。此前 Windows 四个宿主用例因 Git Bash 把盘符冒号解释为远端 tar 地址
而失败；改用 Python 标准库跨平台解包后，Windows ARM64/x64 的 Codex 与 Claude Code 4/4
全部通过。

个人开发通道随后发布了 `v0.3.0-dev.8`（run `31484366464`），六平台构建、6/6 原生启动和
12/12 双宿主插件生命周期均通过。macOS ARM64 代表平台进一步完成 dev.8 登录刷新、退出、
浏览器重登、Codex 自然语言选择 Skill 和 Web 可见性验证。Claude Code 模型调用按用户决定移出
本轮范围；这不影响已经通过的 Claude Code 插件安装、升级、回滚和再升级结果。

| 层级 | 当前本地结果 | 尚待完成 |
| --- | --- | --- |
| L0 静态与构建 | 本地 Python 114/114；Go default/prod/race/vet；公司 PR #1 Hosted Runner 全部通过；含 Dev/Beta 产物一致性与 profile 结构门禁 | 已完成 |
| L1 原生启动 | 公司 PR #1 Hosted Runner 六平台 6/6 通过 | 已完成 |
| L2 宿主生命周期 | 公司 PR #1 Hosted Runner 六平台 × Codex/Claude Code 12/12 通过，覆盖安装、升级、回滚、再升级 | 已完成 |
| L3 海外生产 | 登录前检查通过；真实登录为 `BLOCKED/ENV`，生产 `/agent/login` 尚未部署 | 入口部署后重跑登录，再执行受控账号代表平台 6 个组合 |
| 发布治理 | LICENSE、NOTICE、第三方声明、SECURITY、CODEOWNERS、SBOM 与 attestation 已完成 | 公司法定版权主体复核、公司仓库保护规则 |
| 发布恢复 | 同版本、同 SHA、同资产摘要可续跑；旧任务和冲突制品失败关闭 | 公司仓库首次真实演练 |
| Manifest、Skill 与渠道一致性 | 源码模板已中性化；Dev/Beta 显示名、命令与插件文件保持一致；Beta 双 manifest、Skill 开发字样门禁和逐文件一致性测试均已通过公司 PR CI | 已完成 |
| 对外安装文档 | README 和产品安装说明只保留公司 GitHub Beta，覆盖安装、升级、回滚、卸载与排障；个人 Dev 信息仅保留在内部开发文档 | 首个 Beta 发布后按真实 Tag 和 Release 页面复核命令 |
| Dev.8 代表平台收口 | refresh、logout、浏览器重登、Codex 自然语言调用、服务端历史 Web 可见性均 PASS | Claude Code 模型调用本轮不验证 |
| `production-beta` Environment | 已创建并限制为公司 `main` | 当前私有仓库套餐不支持 reviewer/wait timer；暂由仓库写权限与手动发布入口授权，公开或升级套餐后补 reviewer |

### 本地验证记录

| 项目 | 结果 | 说明 |
| --- | --- | --- |
| 生产候选包 | PASS | 六平台二进制均由 `-tags prod` 构建，候选版本为 `0.3.0-beta.1` |
| 临时低版本包 | PASS | 同一生产源码构建，仅用于 `beta.1` 生命周期测试，不发布 |
| SPDX 2.3 SBOM | PASS | 覆盖 7 个包和 31 个 Marketplace 文件 |
| macOS ARM64 原生 doctor | PASS | `profile=prod`、`channel=beta`、`target=overseas-production` |
| Codex 0.147.0 | PASS | 安装、升级、回滚、再升级全部通过，隔离配置中未登录 |
| Claude Code 2.1.220 | PASS | 安装、升级、回滚、再升级全部通过，隔离配置中未登录 |
| 海外生产登录前检查 | PASS | 精确生产构建、生产域名、macOS Keychain 和初始未登录状态均符合预期 |
| 海外生产真实登录 | BLOCKED | 生产 `/agent/login` 尚未部署；等待进程已取消，未保存生产凭证，未调用业务 API |
| 海外测试 dev.8 鉴权闭环 | PASS | Keychain refresh、logout、浏览器 loopback 重登均通过，没有打印凭据 |
| Codex 自然语言选择 Skill | PASS | 全新模型会话主动选择 dev.8 插件并完成一条低成本文本任务 |
| Web 可见性 | PASS | CLI 创建的项目、用户请求和 VivagoAgent 回复可在海外测试 Web 页面打开 |

### 已发现并处理的问题

| 阶段 | 现象 | 原因 | 处理 |
| --- | --- | --- | --- |
| L1 本机真实包 | 原生门禁错误报告“不是海外生产 profile” | 校验器误用凭证账户名 `overseas-prod` 作为 doctor 环境 target；真实 CLI 固定返回 `overseas-production` | 校验器和测试统一到 `overseas-production`；凭证账户名保持不变 |
| 本机固定宿主验证 | 系统现有 Codex/Claude Code 版本与 CI 固定版本不同 | 本机日常安装版本不等于发布矩阵版本 | 仅在临时目录安装固定版本，不修改用户全局宿主 |
| L3 生产登录 | 网页进入现有生产站内页面，但 CLI 未收到 loopback 回调 | 用户确认生产 `/agent/login` 尚未部署，不属于已部署功能回归失败 | 标记 `BLOCKED/ENV` 并暂停生产鉴权测试；入口部署后从首次未登录用例重新执行 |
| L2 Windows Hosted Runner | GNU tar 报 `Cannot connect to C:/D:`，四个宿主组合全部在解包前失败 | Git Bash 下 GNU tar 把 Windows 盘符冒号解释为远程归档语法 | Dev/Beta Release 和 Beta Check 统一改用 `python -m tarfile -e`；PR #1 Windows 四个宿主组合 4/4 通过 |
| Dev/Beta 产品一致性 | 生产包曾禁用手动 `auth refresh`，个人 Marketplace 描述带 Development | profile 中混入了功能开关，组装器各自维护用户文案 | 删除 profile 功能开关，两种构建均支持同一命令；中性化文案并新增归一化逐文件产物对比 |

## 实施原则

- 个人 GitHub 只能发布海外测试 Dev，公司 GitHub 只能发布海外生产 Beta。
- 每项行为先增加失败测试，再写最小实现。
- 自动检查保持只读；写 Tag、Release 和 Marketplace 只发生在手动发布 Job。
- 公司 Beta 从公司源码重新构建，不复用个人 GitHub Artifact。
- Dev/Beta 只允许环境、凭证命名空间、版本/内部渠道标识和发布治理元数据不同；产品能力完全一致。
- 公司仓库已建立并作为 `origin`；保持 Private，完成门禁和生产登录验收后再单独批准公开。

## 第一阶段：生产构建和分发脚本

### 1. Beta 版本和仓库策略校验

先增加测试，约束：

- Dev 只接受 `0.3.0-dev.N` 和个人仓库；
- Beta 只接受 `0.3.0-beta.N`、公司仓库和 `main`；
- 拒绝 profile、URL、Marketplace 和 channel 运行时输入；
- 已存在 Tag 不允许覆盖。

实现独立的 Beta 版本/仓库策略校验入口，不把 Dev 校验器改成可切换生产环境的万能入口。

### 2. 六平台生产二进制

测试先验证：

- 六个 OS/CPU 目标都使用 `go build -tags prod`；
- ldflags 固定 `channel=beta`、版本和完整源码 SHA；
- 版本必须包含 `-beta.`；
- 二进制包含生产登录入口；
- 二进制拒绝测试和国内地址；
- 任一目标失败后删除不完整输出。

随后实现独立的 Beta builder。

### 3. 生产 Marketplace 组装和独立校验

测试先约束：

- Marketplace 名称固定 `vivago`；
- Manifest、`VERSION`、`BUILD_INFO.json`、`SHA256SUMS` 一致；
- `profile=prod`、`channel=beta`；
- 包内包含六个平台二进制和两个宿主启动器；
- 包内不存在测试/国内地址、`vivago-dev` 和占位值；
- 源码双 manifest 使用 `0.0.0` 中性模板版本，组装时写入本次版本；
- Dev/Beta 的 Codex manifest、Codex Marketplace 和 Skill 显示名均为 `Vivago Agent CLI`，
  Claude 除版本外不改动；
- Beta 双 manifest 的名称和用户可见描述、Skill 指引均不含开发版字样；
- 分发包排除 `.DS_Store`、`__pycache__` 和 `.pyc`；
- 校验器独立重新计算 checksum 和来源信息。

随后实现 Beta assembler 和 verifier。

## 第二阶段：公司 GitHub Workflow

### 4. Workflow 合同测试

先扩展 `tests/test_github_workflows.py`，要求：

- `beta-check.yml` 是只读 Pull Request/Push/手动检查；
- `beta-release.yml` 仅允许手动触发；
- Beta Job 校验公司仓库、`main`、版本和完整源码 SHA；
- Workflow 不提供环境/profile/URL/channel 输入；
- 发布前重新构建并重新校验；
- 发布 Job 使用 `production-beta` Environment，并只允许公司 `main`；
- 只在发布 Job 使用 `contents: write`；
- 更新 `marketplace` 不强推，已有 Tag 不覆盖；
- 所有第三方 Action 固定完整 Commit SHA。

确认测试因 Workflow 缺失而失败后，再实现两个 Workflow。

### 5. Beta Check

实现只读流水线：

- Go default/prod/race/vet；
- Python 测试；
- 六平台生产构建和 Marketplace 组装；
- Codex、Claude Code 校验；
- checksum、环境地址和敏感信息扫描；
- 六平台原生启动；
- 六平台乘两个宿主安装生命周期；
- 上传候选包和脱敏报告。

`beta.1` 没有真实上一版，流水线从同一生产源码构建一个不发布的严格低版本 Beta，完成安装、升级、
回滚和再升级的机制验证。`beta.2` 起必须额外使用已发布的真实上一版验证跨版本兼容性。

### 6. Publish Beta

已实现手动流水线：

- 输入 `0.3.0-beta.N`；
- 从公司 `main` 的确定 SHA 重新构建；
- 运行与 Beta Check 相同门禁；
- 进入 `production-beta` Environment；当前私有仓库套餐不支持 reviewer，暂由公司仓库写权限、
  手动 `workflow_dispatch`、公司仓库与 `main` 硬校验共同承担人工授权；仓库公开或套餐升级后补
  至少一名 reviewer；
- 创建不可变 Prerelease；
- 普通快进更新 `marketplace`；
- 支持基于相同版本和 SHA 补完安全的部分失败，不覆盖不同制品。

发布 Job 会比较 Tag 指向、Release 目标 SHA、Prerelease 状态和三个发布资产的 SHA256。只有完全
一致的已发布 Release 才允许跳过重复创建并继续修复 Marketplace。同版本不同 SHA、资产被替换或
Marketplace 已含更高 Beta 时失败关闭。首个 Beta 不要求管理员手工预建 `marketplace`；流水线会
创建不包含源码历史的 orphan 产物分支，后续版本只允许普通快进。

## 第三阶段：公开仓库和供应链

### 7. 仓库治理文件

已完成：

- Apache-2.0 `LICENSE`、`NOTICE` 和第三方许可证说明；
- `SECURITY.md` 和初始 `CODEOWNERS`；
- 法律文件随 Dev/Beta 插件包分发并进入校验和；
- 清除已追踪的 `.idea` 工程文件，`.gitignore` 继续屏蔽个人 IDE 和系统文件。

待公司确认：

- 法定版权主体和正式维护团队；
- 隐私政策、服务条款及用户问题反馈入口；
- 公司仓库私密漏洞报告开关和分支保护规则。

HiDream.ai 组织现有公开仓库仅做了只读参考检查，没有发现可直接复用的 `CODEOWNERS`、
`SECURITY.md` 或 `NOTICE` 公司模板，也没有修改任何现有仓库。

### 8. Release 元数据

- Release archive；
- `SHA256SUMS`；
- SPDX SBOM；
- `BUILD_INFO.json`；
- GitHub Artifact Attestation 或等价构建证明；
- 环境和敏感信息扫描报告。

## 第四阶段：验证和仓库迁移

### 9. 本地和个人 GitHub 验证

- 仓库全量 Go/Python/插件校验；
- 个人 Dev Workflow 不受 Beta 代码影响；
- Dev 包仍只访问海外测试；
- Beta 包静态证明只访问海外生产。

### 10. 公司仓库和 Remote

执行前单独确认公司初始历史方案。确认后：

- 创建 `HiDream-ai/vivago-agent-cli` 私有仓库；
- 从审计后的 Go 源码树建立干净初始历史；
- 配置 `origin`、`personal`、`codeup`；
- 设置 `main`、`marketplace`、Environment 和分支保护；
- 验证三个 Remote 不影响其他仓库配置。

### 11. Beta 验收和公开

- 公司 CI 完成 L0、L1、L2；
- 海外生产代表平台完成 L3；
- 完成一次 30 分钟目标的回滚演练；
- 公司仓库由 Private 切换 Public；
- 发布 `v0.3.0-beta.1`；
- 观察生产指标并按停止条件决定是否继续发布。

## 提交拆分

计划使用以下独立提交，便于评审和回滚：

1. `test: define beta release policy`
2. `feat: build and verify production beta distribution`
3. `test: define company beta workflow contracts`
4. `ci: add company beta check and release workflows`
5. `docs: prepare public repository governance`
6. `ci: add beta supply-chain metadata`
7. `docs: record beta validation and release handoff`

每个提交都在当前实施分支完成对应测试。公司仓库创建、Remote 修改、GitHub 权限配置和公开发布
不与源码提交混在同一步执行。
