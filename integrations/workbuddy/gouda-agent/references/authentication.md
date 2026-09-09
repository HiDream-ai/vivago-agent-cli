# 登录与凭证

## 登录流程

1. 脚本只监听 `127.0.0.1` 的随机端口。
2. 打开：

   ```text
   https://goudaai.com/login?client=vivago-agent-cli&callback_port=<port>&state=<random-state>
   ```

3. 登录页向 `http://127.0.0.1:<port>/callback` 提交一次表单。
4. 脚本校验来源为 loopback、方法为 POST、路径为 `/callback`、随机 state 一致，并要求
   `ticket` 与 `refresh_token` 都存在。
5. 用户看到登录完成后返回 WorkBuddy；脚本不会显示凭证值。

这里复用够搭现有账号登录，不是标准 OAuth。不得增加 `callback_url` 参数，也不得把 callback
监听到 `0.0.0.0`、局域网地址或公网地址。

## 本地存储

WorkBuddy Skill 使用独立目录：

```text
~/.workbuddy-skills/gouda-agent/credentials.json
~/.workbuddy-skills/gouda-agent/state.json
```

它不读取或覆盖现有 Go CLI 的 Keychain、Credential Manager、Secret Service 或文件凭证。
POSIX 下目录权限为 `0700`、文件权限为 `0600`，文件采用同目录临时文件加原子替换，拒绝符号
链接目标。Windows 依赖用户目录继承的 ACL；这是市场审核材料中必须如实披露的限制。

`auth logout` 删除凭证文件。状态文件不含凭证、prompt 或消息正文，不随 logout 自动删除。

## 刷新

脚本只解析 ticket 的 JWT `exp` 判断是否需要刷新，不校验或使用其他 claim。到期前调用：

```text
GET https://goudaai.com/prod-api/user/apikey2token
Refresh-Token: <仅在请求头中使用>
```

刷新 token 无效时删除本地凭证并要求重新登录。不得把 refresh token 放在 URL、命令行参数、
stdout、stderr 或错误信息中。
