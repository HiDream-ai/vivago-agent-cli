# VivagoAgent 插件安装和升级说明

当前提供的是内部开发版本，供产品和研发在 Codex、Claude Code 中体验 VivagoAgent。插件已经内置
macOS、Windows、Linux 的 ARM64/x64 二进制，不需要另外安装 Go、Python、`vivago-agent` 或
`vivago-client`。

当前可安装版本：`0.3.0-dev.6`。

> 这个版本连接 Vivago 海外测试环境，只用于内部体验。请不要提交客户素材、未公开业务数据、账号凭证
> 或其他敏感内容。后续面向外部用户的版本会迁移到公司 GitHub，并重新构建为海外正式环境版本。

## 安装前准备

安装前确认以下几项：

- 已安装 Codex 或 Claude Code；
- 使用受支持的系统：macOS、Windows 或 Linux，ARM64/x64 均可；
- GitHub 账号已经获得私有仓库 `ChaoXia-Beginer/vivago-agent-cli` 的只读权限，并接受仓库邀请；
- 本机 Git 能正常访问这个私有仓库；
- 有可用的 Vivago 海外测试环境账号。

不需要把 GitHub 密码、PAT、Vivago ticket 或 refresh token 发给任何人。遇到权限问题时，只需提供
GitHub 用户名，由仓库管理员补充只读权限。

## 使用 Codex 安装

在终端依次执行：

```bash
codex plugin marketplace add \
  https://github.com/ChaoXia-Beginer/vivago-agent-cli.git \
  --ref dev-marketplace

codex plugin add vivago-agent-cli@vivago-dev
```

安装完成后，重新打开 Codex 或新建一个任务。

查看安装状态和版本：

```bash
codex plugin list --json
```

## 使用 Claude Code 安装

在终端依次执行：

```bash
claude plugin marketplace add \
  'https://github.com/ChaoXia-Beginer/vivago-agent-cli.git#dev-marketplace'

claude plugin install vivago-agent-cli@vivago-dev --scope user
```

安装完成后，重新打开 Claude Code。

查看安装状态和版本：

```bash
claude plugin list --json
```

## 第一次怎么用

安装后直接在 Codex 或 Claude Code 中用自然语言发起任务，不需要手动调用 CLI。例如：

```text
请使用 VivagoAgent 为一个高端咖啡品牌整理三组海报创意方向。
```

第一次调用时，系统会打开 Vivago 登录页面。正常登录后，凭证保存在当前用户的系统凭证库中；插件
不会要求你复制或粘贴 token。登录完成后回到 Codex 或 Claude Code，原任务会继续执行。

可以用下面的请求验证联网图片搜索：

```text
请使用 VivagoAgent 联网搜索适合高端咖啡海报的视觉参考，并总结构图、色彩和适用场景。
```

也可以验证图片生成：

```text
请使用 VivagoAgent 生成一张可爱的小猫图片。
```

图片任务一般需要约一分钟，视频任务通常需要 15～40 分钟并消耗更多额度。测试安装时优先使用创意
方案或联网视觉参考任务，不需要一开始就生成视频。

## 有新版本时怎么升级

仓库管理员发布新版本后，产品不需要重新接受 GitHub 邀请，也不需要重新登录 Vivago。

Codex 执行：

```bash
codex plugin marketplace upgrade vivago-dev
codex plugin add vivago-agent-cli@vivago-dev
```

Claude Code 执行：

```bash
claude plugin marketplace update vivago-dev
claude plugin update vivago-agent-cli@vivago-dev --scope user
```

升级后重启对应应用，再通过 `plugin list --json` 查看版本。Vivago 登录凭证保存在独立的系统凭证库
中，正常安装和升级不会删除登录态，也不会影响 VivagoAgent 服务端已有的项目、会话和历史。

## 常见问题

### 提示仓库不存在或没有权限

先确认 GitHub 已登录、仓库邀请已经接受，并在浏览器中能够打开：

```text
https://github.com/ChaoXia-Beginer/vivago-agent-cli
```

如果浏览器能打开但命令仍然失败，检查本机 Git 是否能读取该私有仓库。不要通过聊天发送 PAT、密码或
验证码。

### 提示 Marketplace 已存在

说明之前已经添加过，不需要重复添加。Codex 执行：

```bash
codex plugin marketplace upgrade vivago-dev
```

Claude Code 执行：

```bash
claude plugin marketplace update vivago-dev
```

随后执行对应的插件安装或升级命令。

### 安装后自然语言请求没有调用 VivagoAgent

先重启 Codex 或 Claude Code，并明确写出“请使用 VivagoAgent”。然后使用 `plugin list --json` 确认
`vivago-agent-cli@vivago-dev` 已安装。如果插件已安装但仍未调用，请记录宿主、版本、操作系统、发生
时间和界面错误信息后反馈。

### 登录页面没有打开

插件登录需要本机默认浏览器以及 loopback 回调。远程容器、纯命令行服务器或禁用浏览器的环境无法
完成首次登录。请在本地桌面环境重试。

### 升级后仍显示旧版本

先更新 Marketplace，再执行插件升级，并完全重启 Codex 或 Claude Code。如果仍然显示旧版本，反馈
`plugin list --json` 中的插件版本即可，不要附带凭证、Cookie、Authorization Header 或完整任务内容。

## 反馈问题时提供什么

反馈时请提供：

- 使用的是 Codex 还是 Claude Code；
- 操作系统和 CPU 架构；
- `plugin list --json` 显示的插件版本；
- 出现问题的大致时间；
- 执行到安装、登录、任务提交、进度恢复还是结果展示哪一步；
- 界面上可见的错误信息。

不要发送 GitHub PAT、Vivago ticket、refresh token、Cookie、Authorization Header、预签名 URL、客户
素材或敏感任务内容。
