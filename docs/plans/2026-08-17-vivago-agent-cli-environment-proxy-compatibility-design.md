# Vivago Agent CLI 标准环境代理兼容设计

日期：2026-08-17
状态：已确认，待实施

## 背景

普通 API、Token 刷新和 Chat SSE 已通过 Go 标准库 `http.ProxyFromEnvironment` 兼容
`HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`。没有适用代理时直接访问，存在适用代理时通过代理
访问，命中 `NO_PROXY` 时仍然直连。

附件上传和产物下载当前使用独立的安全 HTTP Client，将 `Transport.Proxy` 固定为 `nil`，并在实际
拨号时只允许连接经过公网 DNS 校验的目标地址。这能降低 SSRF 和 DNS rebinding 风险，但会导致只能
通过本地代理访问外网的用户无法上传附件或下载产物。

公开 Beta 需要让三条网络链路保持一致的代理使用体验，同时不能放弃上传和下载已有的安全边界。

## 已确认需求

- 普通 API、附件上传和产物下载都兼容标准环境代理；
- 用户设置适用的 `HTTP_PROXY` 或 `HTTPS_PROXY` 时走代理，没有设置时直连；
- `NO_PROXY` 继续生效；
- 允许用户显式配置位于 loopback 或私网地址的本地代理；
- 不增加 Vivago 专用代理配置、运行时环境切换或国内/App 回退；
- 第一版不自动读取 macOS、Windows 或 Linux 的系统代理设置。

## 当前 API 实现

`cmd/vivago-agent/main.go` 的 `newHTTPClient()` 创建共享 HTTP Client：

```go
&http.Transport{
    Proxy: http.ProxyFromEnvironment,
    // 连接、TLS 和响应 Header 超时省略
}
```

同一个 Client 被注入 `HTTPTokenRefresher` 和 `internal/client.Client`，因此 Token 刷新、项目与会话
请求、Chat SSE 使用同一套环境代理规则。代理地址不进入 CLI 配置文件，也不会写入会话状态。

## 方案

代理选择语义与 API 保持一致，但 API、上传和下载不共用同一个 Transport：

```text
标准环境代理选择
├── API Transport
├── 安全上传 Transport
└── 安全下载 Transport
```

上传和下载发送请求前使用 `http.ProxyFromEnvironment` 选择网络路径：

1. 没有适用代理时使用现有安全直连路径；
2. 存在适用代理时先校验业务目标，再连接用户配置的代理；
3. `NO_PROXY` 判断交给 Go 标准库，语义与普通 API 一致。

不采用“只替换 `Proxy: nil`”，因为当前自定义 `DialContext` 会把实际连接的本地代理地址当成业务
目标校验并拒绝。也不采用“直连失败后自动改走代理”，避免上传部分发送后重复 PUT。

## 安全边界

### 附件上传

- 仅允许 HTTPS 和 443 端口；
- 拒绝 userinfo、fragment、字面私网 IP 和无效 URL；
- 发送请求前解析上传目标，任一结果不是公网地址时拒绝；
- 禁止上传重定向；
- PUT 只携带 Content-Type 和 Content-Length，不携带 Vivago Authorization；
- 不输出完整预签名 URL。

直连时继续按已校验公网 IP 拨号。代理模式下，代理可能自行解析目标域名，CLI 不能像直连模式一样
固定最终目标 IP；这是用户显式配置代理时的信任边界。CLI 仍须在连接代理前完成业务目标 URL 和本地
公网 DNS 校验。

### 产物下载

- 图片、视频和音频继续使用既定域名白名单；
- 仅允许 HTTPS 和 443 端口；
- 重定向不得跨域、降级或携带 userinfo/fragment；
- 发送请求前解析目标，任一结果不是公网地址时拒绝；
- 保留 Content-Type、大小限制、临时文件、原子落盘和禁止覆盖检查。

代理本身是用户明确配置的网络出口，允许位于 loopback 或私网地址。业务目标仍不得位于这些地址。

## 错误处理

- 网络错误可以说明本次路径为 `direct` 或 `environment-proxy`，但不得输出代理 URL、代理凭证、
  预签名 URL或请求 Header；
- 不在直连和代理之间自动重试上传；
- 代理配置无效时返回稳定的网络配置错误，机器可读 stdout 结构保持不变；
- `NO_PROXY` 导致直连失败时，只提示检查标准代理环境变量，不猜测具体代理软件。

## 测试设计

- 未设置代理时选择直连，并保持现有公网 DNS 和 IP 固定拨号行为；
- 设置本地代理时选择代理路径；
- `NO_PROXY` 命中时选择直连；
- 本地代理不会被误当成业务目标拒绝；
- 不安全的上传或下载目标在连接代理前拒绝；
- 上传重定向和下载域名、重定向、类型、大小限制在代理模式下仍生效；
- 错误、stdout 和 stderr 不包含代理凭证或完整预签名 URL。

集成验证覆盖无代理直连、可用环境代理、`NO_PROXY`、代理不可达和不安全目标五类场景。正式 Beta
候选包继续在受控海外环境完成直连附件和产物冒烟，避免只验证代理路径。

## 不在本次范围内

- 自动读取操作系统代理、PAC、WPAD 或第三方代理软件配置；
- 在 CLI 中保存代理地址或代理认证信息；
- 代理连通性自动探测、自动切换或失败后自动重试上传；
- 自签 CA 安装和企业 TLS 中间人证书管理；
- Hosted MCP、标准 OAuth 或运行时环境切换。

## 验收标准

- 直连用户的现有上传、下载和安全测试没有回退；
- 设置标准环境代理的用户可以完成 API、附件上传和产物下载；
- `NO_PROXY` 行为与普通 API 一致；
- 本地代理地址不会被 SSRF 校验误杀，业务目标仍执行既有安全检查；
- 默认、`prod`、race、vet、分发测试和官方插件校验通过；
- 文档、日志、错误和测试产物没有代理凭证、Token 或完整预签名 URL。
