# VivagoAgent CLI 登录页前端配合说明

## 背景

我们正在开发 `vivago-agent-cli`，让用户从 Codex 或 Claude Code 插件把创作任务交给 VivagoAgent。CLI 会调用 Vivago 现有的 Web REST API，项目、会话和生成结果仍保存在 Vivago，用户之后也能回到 Web 页面查看和编辑。

第一版继续使用 Vivago 现有账号体系，不建设新的 OAuth 服务。CLI 首次使用或本地凭证失效时，会打开一个新的 VivagoAgent CLI 登录页面，由用户在浏览器内完成登录，再把登录结果安全地交给本地 CLI。

海外测试环境的新入口为：

```text
https://dev.vivago.ai/agent/login
```

这是一个全新的登录入口，不调用 `/login-cli`，也不考虑旧客户端兼容。邮箱、Google、Apple、Discord 等已有登录能力可以复用，但页面进入方式和登录结果回调按本文的新协议实现。

## 登录过程

### 1. CLI 打开登录页面

CLI 先在本机选择一个可用端口，并生成一次性的随机 `state`，然后打开：

```text
https://dev.vivago.ai/agent/login
  ?client=vivago-agent-cli
  &callback_port=<本地随机端口>
  &state=<一次性随机值>
```

参数说明：

| 参数 | 必填 | 说明 |
|---|---:|---|
| `client` | 是 | 固定为 `vivago-agent-cli` |
| `callback_port` | 是 | CLI 在 `127.0.0.1` 上监听的随机端口 |
| `state` | 是 | CLI 为本次登录生成的一次性随机值 |

### 2. 前端完成用户登录

用户在 `/agent/login` 页面使用现有 Vivago 登录方式。以下两种情况进入相同的回调流程：

- 用户打开页面时已经登录；
- 用户在当前页面完成登录。

### 3. 前端提交登录结果

前端通过 HTML Form POST 向本地 CLI 提交登录结果：

```text
http://127.0.0.1:<callback_port>/callback
```

表单使用 `application/x-www-form-urlencoded`，包含：

| 字段 | 必填 | 说明 |
|---|---:|---|
| `ticket` | 是 | 当前登录用户的访问 ticket |
| `refresh_token` | 是 | 后续用于刷新 ticket |
| `state` | 是 | 原样返回登录 URL 中的 `state` |

示例只展示字段结构，不代表真实凭证：

```http
POST /callback HTTP/1.1
Host: 127.0.0.1:54321
Content-Type: application/x-www-form-urlencoded

ticket=example-ticket&refresh_token=example-refresh-token&state=example-state
```

表单使用普通页面提交，不设置隐藏 iframe，也不通过 `fetch` 调用。提交后浏览器离开 Vivago 登录页，进入本地 CLI 返回的页面。

### 4. CLI 完成本地处理

CLI 收到回调后负责：

1. 校验 Method、Path、Body 大小和必要字段；
2. 校验请求中的 `state` 是否属于本次登录；
3. 保存 `ticket` 和 `refresh_token`；
4. 在浏览器中展示本地成功或失败页面；
5. 把最终结果输出给发起登录的终端命令。

前端不读取 `/callback` 的 HTTP 状态或响应内容，不监听 `postMessage`，也不判断本地凭证是否保存成功。本地处理结果由 CLI 和终端负责。

## 前端需要实现什么

### 1. 校验页面参数

`/agent/login` 页面加载时读取：

```text
client
callback_port
state
```

只有以下条件全部满足，页面才允许继续登录：

- `client` 严格等于 `vivago-agent-cli`；
- `callback_port` 是 `1` 到 `65535` 之间的十进制整数；
- `state` 非空，建议限制为 32～128 个 URL-safe 字符；
- 页面没有收到调用方指定的完整 `callback_url`。

回调地址必须由前端按固定规则生成：

```text
Protocol = http
Host = 127.0.0.1
Port = callback_port
Path = /callback
```

调用方不能指定 Host、协议或 Path，避免页面向外部地址发送凭证。

参数不完整或不合法时，页面显示登录请求无效，不进入登录流程，也不发送任何凭证。

### 2. 登录成功后提交 Form POST

登录成功后，前端创建普通 HTML Form 并提交：

```js
function returnLoginToCli({ port, state, ticket, refreshToken }) {
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = `http://127.0.0.1:${port}/callback`

  const fields = {
    ticket,
    refresh_token: refreshToken,
    state,
  }

  for (const [name, value] of Object.entries(fields)) {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = name
    input.value = value
    form.appendChild(input)
  }

  document.body.appendChild(form)
  form.submit()
}
```

不设置 `form.target`，让浏览器直接进入本地 CLI 返回页面。前端不需要增加 callback 状态解析、错误码映射、CORS、OPTIONS 或浏览器私网请求处理。

### 3. 防止重复提交

页面需要防止同一笔登录结果被重复发送：

- 第一次提交前设置本地 `submitting` 状态；
- `submitting=true` 后忽略重复的登录成功事件；
- 用户登录失败或取消时不提交表单；
- 参数校验失败时不创建表单；
- 提交前可以展示“正在返回 VivagoAgent CLI”，但不等待前端可读的回调状态。

## 页面提示

等待用户登录时沿用现有登录 UI。

参数不完整或不合法时建议提示：

```text
登录请求无效，请返回终端重新发起登录。
```

提交表单前可以提示：

```text
登录成功，正在返回 VivagoAgent CLI…
```

表单提交后浏览器会进入本地 CLI 页面，最终成功或失败提示由 CLI 展示。前端不需要为 callback 结果保留额外页面状态。

错误页面不能展示端口、`state`、ticket 或 refresh token 的完整值。

## 安全要求

- `ticket` 和 `refresh_token` 只能放在 POST Body，不能放进 URL。
- 不得在 `console`、埋点、Sentry、错误提示或网络诊断信息中记录凭证。
- 不得支持调用方传入任意 `callback_url`、Host、协议或 Path。
- 页面只提交一次。登录事件重复触发时不能重复发送凭证。
- `state` 由 CLI 生成，前端只负责原样提交。
- 登录失败或用户取消登录时不发送回调。
- 如果站点配置了 CSP，需要确认 `form-action` 允许向 `http://127.0.0.1:*` 提交表单。
- 页面和测试代码只能使用明确的假凭证，不得提交真实账号凭证或完整登录响应。

`state` 用于让本地 CLI 判断回调是否属于当前登录，不代表用户身份，也不能替代 `ticket` 鉴权。

## 前端测试范围

至少覆盖以下场景：

| 场景 | 预期结果 |
|---|---|
| 已登录用户打开合法 `/agent/login` URL | 直接向随机端口 Form POST |
| 未登录用户打开合法 `/agent/login` URL | 登录成功后向随机端口 Form POST |
| `callback_port` 缺失、格式错误或超出范围 | 显示无效请求，不进入登录流程 |
| `state` 缺失或格式错误 | 显示无效请求，不进入登录流程 |
| `client` 不是 `vivago-agent-cli` | 显示无效请求，不进入登录流程 |
| 登录失败或用户取消 | 不回调，不输出凭证 |
| 登录成功事件重复触发 | 只提交一次 |
| 表单提交成功 | 浏览器进入本地 CLI 返回页面 |
| 本地端口不可访问 | 浏览器展示连接失败，不要求前端解析失败状态 |
| 查看地址栏、控制台、埋点和前端错误采集 | 不出现 ticket 和 refresh token |

联调时至少验证最新版 Chrome、Safari 和 Edge。Firefox 如果属于公开 Beta 支持范围，也需要一并验证。重点确认：

- HTTPS 页面能够向 loopback HTTP 地址提交 Form；
- 站点 CSP 没有拦截 Form 提交；
- 成功提交后浏览器能够进入本地 CLI 页面；
- 本地端口不可访问时不会把凭证追加到 URL；
- 登录过程不会在前端日志和监控中留下凭证。

## 发布顺序

为避免 CLI 发布后无法登录，发布顺序需要固定：

1. 海外测试 Web 上线 `/agent/login`。
2. Go CLI 在海外测试环境完成登录、state 校验和凭证保存联调。
3. 使用同一协议发布海外正式 `/agent/login`。
4. 正式页面验证通过后，再发布面向外部用户的 CLI Beta。

如果新入口在联调阶段出现问题，直接修复或回滚 `/agent/login`，不影响站内其他登录页面。CLI Beta 发布后，如果需要下线该入口，应同时暂停对应 CLI 版本的分发。

## 这次不需要前端处理的事情

- 不需要接入或改造旧 `/login-cli`；
- 不需要兼容旧 `vivago-client`；
- 不需要读取 `/callback` 的 HTTP 响应；
- 不需要接收 callback 成功或失败状态；
- 不需要实现 iframe、`postMessage` 或 callback 超时判断；
- 不需要新建 OAuth Server；
- 不需要修改用户账号体系和现有登录接口；
- 不需要修改 `/prod-api/user/apikey2token`；
- 不需要调用 VivagoAgent 业务 API；
- 不需要保存 CLI 会话或任务历史；
- 不需要决定 `platform` 或 `source` 的落库方式；
- 不需要为 `/callback` 实现后端服务，该接口由本地 CLI 提供。

前端本次只负责新 `/agent/login` 页面、参数校验和登录结果 Form POST。提交后的处理全部由本地 CLI 负责。

## 联调完成标准

满足以下条件即可认为前端配合完成：

- 海外测试 `/agent/login` 能使用现有 Vivago 账号完成登录；
- 页面只向固定格式的 `127.0.0.1:<port>/callback` 提交凭证；
- 参数不合法、登录失败或用户取消时不会发送凭证；
- 登录结果只提交一次；
- 前端不读取 callback 响应，也不维护 callback 状态；
- 浏览器地址栏、历史记录、控制台、埋点和错误采集均不包含凭证；
- Chrome、Safari、Edge 的 Form 和 CSP 场景验证通过；
- 前端和 CLI 使用同一组请求参数及表单字段完成联调记录；
- 海外正式入口验证通过后再发布 CLI Beta。

## 前端评审时需要确认

- 海外正式入口是否使用 `https://vivago.ai/agent/login`；
- 当前 CSP 是否允许向 loopback 地址提交 Form；
- 公开 Beta 需要覆盖的浏览器范围。
