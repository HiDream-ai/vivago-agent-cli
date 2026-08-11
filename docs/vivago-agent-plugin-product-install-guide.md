# VivagoAgent 插件安装和升级说明

VivagoAgent 插件支持 Codex 和 Claude Code，安装包内置 macOS、Windows、Linux 的 ARM64/x64
二进制。普通用户不需要安装 Go、Python、`vivago-agent` 或 `vivago-client`。公开 Beta 固定访问
Vivago 海外正式环境，不提供环境切换，也不调用 App API。

## 安装前准备

- 已安装 Codex 或 Claude Code；
- 使用 macOS、Windows 或 Linux 的本地桌面环境；
- 本机有可用的默认浏览器；
- 有可登录 Vivago 海外正式环境的账号。

GitHub 仓库公开后可以直接安装，不需要提交 GitHub PAT。Vivago 登录也不会要求用户把 ticket、
refresh token、Cookie 或验证码复制给 Codex、Claude Code 或其他人。

## Codex 安装

```bash
codex plugin marketplace add \
  https://github.com/HiDream-ai/vivago-agent-cli.git \
  --ref marketplace

codex plugin add vivago-agent-cli@vivago
```

安装完成后重新打开 Codex 或新建一个任务。查看安装状态：

```bash
codex plugin list --json
```

## Claude Code 安装

```bash
claude plugin marketplace add \
  'https://github.com/HiDream-ai/vivago-agent-cli.git#marketplace'

claude plugin install vivago-agent-cli@vivago --scope user
```

安装完成后重新打开 Claude Code。查看安装状态：

```bash
claude plugin list --json
```

## 第一次怎么用

安装后直接用自然语言说明要交给 VivagoAgent 的完整任务。例如：

```text
请使用 VivagoAgent 为一个高端咖啡品牌整理三组海报创意方向。
```

第一次调用会打开 Vivago 登录页面。用户在网页中正常登录后，凭证保存在当前操作系统的凭证库中，
原任务会继续执行。不要把登录结果或任何凭证复制回聊天。

需要联网寻找图片或视觉参考时要明确说明：

```text
请使用 VivagoAgent 联网搜索适合高端咖啡海报的视觉参考，并总结构图、色彩和适用场景。
```

图片任务通常约一分钟；视频任务一般需要 15～40 分钟并消耗更多额度。长任务可以关闭当前流式连接
后恢复，不要重复提交同一请求。

## 升级

新 Beta 发布后，先刷新 Marketplace，再刷新插件。

Codex：

```bash
codex plugin marketplace upgrade vivago
codex plugin add vivago-agent-cli@vivago
```

Claude Code：

```bash
claude plugin marketplace update vivago
claude plugin update vivago-agent-cli@vivago --scope user
```

升级后完全重启对应应用，再通过 `plugin list --json` 查看版本。正常升级不会删除 Vivago 登录态，
也不会影响 VivagoAgent 服务端已有的项目、会话和历史。

## 回滚到指定 Beta

每个 GitHub Release 都提供 `vivago-beta-marketplace.tar.gz`、包内文件的 `SHA256SUMS`、SBOM 和
GitHub 构建证明。先从目标版本的 Release 页面下载并核对构建证明与校验和，再把压缩包解压到独立
目录。下面命令中的 `N` 要替换成实际版本数字，也可以使用 GitHub CLI 下载：

```bash
mkdir -p /absolute/path/vivago-beta-rollback/marketplace
gh release download v0.3.0-beta.N \
  --repo HiDream-ai/vivago-agent-cli \
  --pattern vivago-beta-marketplace.tar.gz \
  --dir /absolute/path/vivago-beta-rollback
tar -xzf /absolute/path/vivago-beta-rollback/vivago-beta-marketplace.tar.gz \
  -C /absolute/path/vivago-beta-rollback/marketplace
```

Codex 切换到本地版本：

```bash
codex plugin marketplace remove vivago
codex plugin marketplace add /absolute/path/vivago-beta-rollback/marketplace
codex plugin add vivago-agent-cli@vivago
```

Claude Code 切换到本地版本：

```bash
claude plugin marketplace remove vivago
claude plugin marketplace add /absolute/path/vivago-beta-rollback/marketplace --scope user
claude plugin update vivago-agent-cli@vivago --scope user
```

回到最新 Beta 时，移除本地 Marketplace，再按本文开头的公司 GitHub 地址重新添加并升级。回滚只
替换本地插件代码，不删除服务端项目、会话和历史。

## 卸载

Codex：

```bash
codex plugin remove vivago-agent-cli@vivago
codex plugin marketplace remove vivago
```

Claude Code：

```bash
claude plugin uninstall vivago-agent-cli@vivago --scope user
claude plugin marketplace remove vivago
```

如果还要清除 Vivago 登录态，请在卸载前让插件执行退出登录。仅卸载插件不等于注销 Vivago 账号。

## 常见问题

### 提示仓库或 Marketplace 不存在

确认公司仓库已经公开，并且 `marketplace` 分支和至少一个 Beta Release 已发布。不要改用其他测试
Marketplace 代替生产包。

### 提示 Marketplace 已存在

说明已经添加过，不需要重复添加。Codex 执行：

```bash
codex plugin marketplace upgrade vivago
codex plugin add vivago-agent-cli@vivago
```

Claude Code 执行：

```bash
claude plugin marketplace update vivago
claude plugin update vivago-agent-cli@vivago --scope user
```

### 安装后没有调用 VivagoAgent

完全重启 Codex 或 Claude Code，并在请求中明确写“请使用 VivagoAgent”。然后使用
`plugin list --json` 确认 `vivago-agent-cli@vivago` 已安装。

### 登录页面没有打开

首次登录需要本机默认浏览器和 loopback 回调。远程容器、纯命令行服务器或禁止打开浏览器的环境
不能完成登录，请改用本地桌面环境。不要用手工复制 token 或直接调用业务 API 的方式绕过登录。

### 升级后仍显示旧版本

先更新 Marketplace，再更新插件并完全重启宿主。仍未生效时，只需反馈 `plugin list --json` 中的
宿主、插件版本、操作系统和 CPU 架构，不要附带凭证或完整任务内容。

## 反馈问题时提供什么

- Codex 或 Claude Code 及其版本；
- 操作系统和 CPU 架构；
- `plugin list --json` 显示的插件版本；
- 问题发生的大致时间；
- 出现在安装、登录、任务提交、恢复还是结果展示阶段；
- 界面中可见的错误信息。

不要发送 GitHub PAT、Vivago ticket、refresh token、Cookie、Authorization Header、预签名 URL、
客户素材或敏感任务内容。安全问题请按仓库的 [Security Policy](../SECURITY.md) 私密提交。
