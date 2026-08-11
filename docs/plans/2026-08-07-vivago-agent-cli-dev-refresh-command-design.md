# VivagoAgent CLI 开发版手动刷新设计

## 为什么需要这个命令

Go CLI 已经实现自动刷新：登录票据进入到期前 60 秒的窗口后，下一次 API 请求会使用 Keychain 中的
refresh token 换取新票据并覆盖保存。海外测试的真实登录、logout 和重新登录已经通过，但当前票据
仍在有效期内，无法立即触发自动刷新。

测试不能读取或篡改 Keychain 中的凭证，也不能为了等票据过期长期占用联调窗口。开发构建因此增加
一个受限的手动刷新命令，只用来验证真实 refresh API、系统凭证库写回和错误处理。它不改变正式用户
的自动刷新行为。

## 命令怎么工作

开发构建支持：

```bash
vivago-agent --json auth refresh
```

执行过程固定为：

```text
CLI
  -> 从系统凭证库加载当前凭证
  -> 获取认证进程锁
  -> 使用 refresh token 调用现有 refresh API
  -> 将新 ticket 写回同一个系统凭证库
  -> 只输出刷新结果和凭证存储类型
```

成功输出：

```json
{"ok":true,"data":{"refreshed":true,"backend":"keychain"},"error":null}
```

stdout 和 stderr 都不能出现 ticket、refresh token、Authorization Header 或 refresh 请求头。命令不接收
凭证参数，也不提供显示凭证的调试选项。

## dev 和 prod 怎么隔离

是否允许手动刷新由编译 profile 决定，不读取运行时环境变量：

- 默认 `dev` profile 访问 `https://dev.vivago.ai`，允许 `auth refresh`；
- `prod` build tag 访问 `https://vivago.ai`，拒绝 `auth refresh`；
- 用户不能通过参数、配置文件或环境变量打开正式构建的手动刷新能力。

prod 收到该命令时返回结构化 `COMMAND_UNAVAILABLE`，退出码为 2，不读取系统凭证库，也不发起网络请求。
插件 Skill 不宣传这个命令，外部用户的正常路径仍然只有 login、status、logout 和请求时自动刷新。

## 复用现有刷新逻辑

手动刷新与自动刷新必须共用同一个实现，不能另写一套 HTTP 调用：

- 使用现有 `/prod-api/user/apikey2token` refresh 接口；
- 使用现有进程锁，避免多个宿主同时覆盖票据；
- 瞬时网络错误按现有规则重试一次；
- refresh token 被服务端拒绝时清除当前 CLI 凭证并返回 login required；
- 保存新 ticket 失败时返回认证错误，不能把新 ticket 输出给调用方兜底。

为了避免手动刷新接口把 ticket 暴露给 CLI 层，认证模块只返回“刷新完成”和凭证库类型。API 客户端仍通过
`AccessToken()` 获取票据，命令处理层不接触凭证字符串。

## 测试要求

实现顺序按测试先行执行：

1. 认证层测试：即使 ticket 尚未进入刷新窗口，手动刷新也调用现有 refresher，并在进程锁内写回新 ticket。
2. CLI 测试：dev 命令只输出 `refreshed` 和 `backend`，输出中不包含任何凭证值。
3. prod 测试：命令返回 `COMMAND_UNAVAILABLE`，认证 runtime 未被调用。
4. 错误测试：无凭证、失效 refresh token、瞬时网络失败和系统凭证库写入失败沿用现有认证错误语义。
5. 回归测试：自动刷新、login、logout、六平台构建和 prod profile 均保持原行为。
6. 真实 E2E：只在海外测试构建执行一次 `auth refresh`，随后用 `auth status` 和一个只读 Web API 请求确认
   登录仍有效；证据中不保存任何凭证值。

## 完成标准

- dev 构建可以通过真实 refresh API 更新系统凭证库；
- prod 构建无法调用手动刷新；
- 自动刷新逻辑没有分叉；
- 所有机器可读输出不含凭证；
- Go 全包测试、race、vet、六平台构建和插件校验通过；
- 海外测试真实刷新后，现有登录和只读 API 仍可使用。

## 当前实施状态

2026-08-07 已完成 Go 实现、本地回归和海外测试真实刷新：开发构建允许命令，生产构建在认证 runtime
初始化前拒绝；手动刷新与自动刷新共用锁、重试、失效凭证清理和写回逻辑。真实用例在原 ticket 仍为
`needs_refresh=false` 时强制刷新，只返回 `refreshed=true` 和 `backend=keychain`；刷新后仍为已登录状态，
Web 项目列表只读请求返回应用 `code=0`。证据未保存任何凭证值。
