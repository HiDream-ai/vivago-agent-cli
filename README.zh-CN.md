# vivago-agent-cli

[English](./README.md) | 简体中文

面向 Codex 和 Claude Code 的 VivagoAgent 本地客户端与插件工程。宿主 Agent 通过包内 Go CLI 把完整任务委派给 VivagoAgent；VivagoAgent 负责内部工具执行和服务端会话历史，本插件不暴露业务 MCP 工具或内部 Skill。

当前仓库只维护 Go 实现，长期源码分支为 `main`。

## 调用链

```text
Codex / Claude Code
        ↓
VivagoAgent Plugin Skill
        ↓
插件内置 vivago-agent Go CLI
        ↓
VivagoAgent Web REST / SSE API
```

- 默认构建固定连接海外测试环境，用于开发和测试。
- `prod` build tag 固定连接海外正式环境，用于公开 Beta。
- 用户不能通过命令行切换环境，公开包也不支持国内环境。
- CLI 请求使用 `X-Source: cli`，同时保持 Web 产品语义。
- 完整对话历史保存在 VivagoAgent；本地任务账本只保存恢复所需的 ID、游标和状态。

## 项目目录

```text
cmd/vivago-agent/                       CLI 入口、运行时装配和 doctor
internal/auth/                          浏览器登录、loopback 回调和系统凭证库
internal/client/                        VivagoAgent REST/SSE 协议映射
internal/cli/                           JSON/JSONL 命令契约
internal/sse/                           SSE 解析和终态判断
internal/attachment/                    附件类型与约束
internal/upload/                        预签名上传
internal/artifact/                      产物 URL、下载与本地预览
internal/config/                        dev/prod 编译配置
plugin/                                Codex/Claude Code 共用的 Go 插件与 Skill
scripts/                                六平台编译与 Marketplace 组装
tests/                                  发布脚本和分发包测试
docs/                                   当前方案、差距分析和联调说明
changelog.d/                            用户可感知的变更记录
```

## 开发

要求：

- Go 1.25.12（见 `go.mod` 的 toolchain）
- Python 3.11+，仅用于跨平台构建、Marketplace 组装和官方插件校验；CLI 运行时不依赖 Python

安装开发校验依赖：

```bash
python -m pip install -r requirements-dev.txt
```

运行开发版：

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go run ./cmd/vivago-agent --json version

GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go run ./cmd/vivago-agent --json doctor
```

默认构建访问海外测试环境。检查生产编译配置时使用：

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache \
  go test -tags prod ./...
```

不要给 CLI 增加 `--env`，也不要让公开构建回退到测试、国内或 App 接口。

## CLI 命令

登录：

```bash
vivago-agent --json auth status
vivago-agent --json auth login
vivago-agent --json auth logout
```

`auth login` 会打开 Vivago 登录页面，使用随机 loopback 端口、一次性 `state` 和 Form POST 回调。凭证优先进入 macOS Keychain、Windows Credential Manager 或 Linux Secret Service；只有 Linux/WSL2 在 Secret Service 不可用时允许降级为权限 `0600` 的本地文件。

项目和任务：

```bash
vivago-agent --json project create --name "Codex task"
vivago-agent --json project list --page-size 20

vivago-agent --json project link \
  --project-id <project-id> \
  --conversation-id <conversation-id>

vivago-agent --jsonl ask \
  --project-id <project-id> \
  --prompt "帮我生成一张小猫图片"

vivago-agent --jsonl ask \
  --conversation-id <conversation-id> \
  --prompt "继续修改上一版" \
  --file /absolute/path/reference.png
```

恢复、取消和历史：

```bash
vivago-agent --jsonl resume \
  --turn-id <turn-id> \
  --last-event-id <event-id>

vivago-agent --json cancel \
  --conversation-id <conversation-id> \
  --turn-id <turn-id>

vivago-agent --json history --conversation-id <conversation-id>
```

产物：

```bash
vivago-agent --json artifact preview \
  --media-type image --content-id <content-id>

vivago-agent --json artifact download \
  --media-type video --content-id <content-id> \
  --output /absolute/path/result.mp4
```

机器可读 stdout 是兼容契约：普通命令输出 JSON，流式命令输出 JSONL，诊断信息写入 stderr。只有收到 `RUN_FINISHED` 才算远端任务成功；断流应使用原 `turn_id` 和 `last_event_id` 恢复，不能重复提交 Prompt。

`project link` 不访问服务端，由构建时固定的 profile 返回正确环境的 Web 项目链接；插件文档不会自行选择或拼接开发、生产域名。

## 网络代理

普通 API、附件上传和产物下载统一遵循标准 `HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY` 环境变量。
没有配置代理时直接访问；配置了代理时通过代理访问；命中 `NO_PROXY` 时仍然直连。例如：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY=127.0.0.1,localhost
```

设置环境变量后，需要从同一个终端启动或重新启动 Codex、Claude Code。CLI 不保存代理地址和代理
凭证，也不会把它们写入任务、日志或仓库。第一版不自动读取操作系统代理、PAC 或第三方代理软件配置；
使用 TUN/VPN 时由操作系统路由接管，无需额外配置 CLI。

## 安装公开 Beta

插件品牌素材和颜色规范见
[`plugin/assets/README.md`](plugin/assets/README.md)。

公开 Beta 从公司 GitHub 的 `marketplace` 分支安装，内置 macOS、Linux 和 Windows 的 ARM64/x64
二进制。普通用户不需要安装 Go、Python、`vivago-agent` 或 `vivago-client`。

Codex：

```bash
codex plugin marketplace add \
  https://github.com/HiDream-ai/vivago-agent-cli.git \
  --ref marketplace
codex plugin add vivago-agent-cli@vivago
```

Claude Code：

```bash
claude plugin marketplace add \
  'https://github.com/HiDream-ai/vivago-agent-cli.git#marketplace'
claude plugin install vivago-agent-cli@vivago --scope user
```

安装后重新打开 Codex 或 Claude Code，直接用自然语言说明“请使用 VivagoAgent”。第一次调用会打开
Vivago 登录页面；用户正常登录即可，不要把 ticket、refresh token、Cookie 或 PAT 复制给宿主 Agent。

升级时先刷新 Marketplace，再刷新插件：

```bash
# Codex
codex plugin marketplace upgrade vivago
codex plugin add vivago-agent-cli@vivago

# Claude Code
claude plugin marketplace update vivago
claude plugin update vivago-agent-cli@vivago --scope user
```

卸载：

```bash
codex plugin remove vivago-agent-cli@vivago
codex plugin marketplace remove vivago

claude plugin uninstall vivago-agent-cli@vivago --scope user
claude plugin marketplace remove vivago
```

升级、指定版本回滚和常见问题见
[VivagoAgent 插件安装和升级说明](docs/vivago-agent-plugin-product-install-guide.md)。

## 发布方式

Pull Request 和 `main` 的检查只构建、测试并上传临时候选包，不会自动改变用户的安装版本。公开
Beta 由公司 GitHub 的手动发布流程从确定的 `main` 提交重新构建，经过六平台原生启动、Codex 与
Claude Code 安装生命周期、checksum、SBOM、环境扫描和生产审批后，才会创建 Prerelease 并更新
`marketplace` 分支。完整流程见
[公开 Beta 发布设计](docs/plans/2026-08-11-vivago-agent-cli-public-beta-release-design.md)。

## 验证

```bash
GOCACHE=/tmp/vivago-agent-cli-go-cache go test ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -tags prod ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go test -race ./...
GOCACHE=/tmp/vivago-agent-cli-go-cache go vet ./...
python -m unittest discover -s tests -v
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py \
  plugin
```

六平台构建和 Marketplace 组装见 [Go 开发 Marketplace](docs/go-dev-marketplace.md)。完整公开 Beta 方案见 [Go 公开 Beta 设计](docs/plans/2026-08-07-vivago-agent-cli-go-public-beta-design.md)，正式版差距见 [GA 差距分析](docs/plans/2026-08-07-vivago-agent-cli-public-ga-gap-analysis.md)。

## 安全边界

- 不打印 access ticket、refresh token、Cookie、Authorization 或预签名上传 URL。
- 不调用 VivagoAgent App API，不暴露内部业务 MCP 工具。
- 不把完整会话或用户文件复制到第二套本地存储。
- 只上传用户明确授权的本地路径。
- 开发构建和生产构建使用不同服务地址与凭证命名空间。
- 公共插件必须通过公司 GitHub 的受控构建、校验和真实环境验证后发布。

## 许可证与安全

源码采用 [Apache License 2.0](LICENSE)。发布包同时携带 `LICENSE`、`NOTICE`、
`THIRD_PARTY_LICENSES.md`、SPDX 2.3 SBOM、SHA256 校验和以及 GitHub 构建证明。

安全问题请按 [Security Policy](SECURITY.md) 通过 GitHub 私密漏洞报告提交，不要在公开 Issue 中
粘贴凭证、用户内容、内部地址或漏洞利用细节。
