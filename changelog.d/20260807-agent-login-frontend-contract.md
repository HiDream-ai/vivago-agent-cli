# Changed

- 公开 Beta 登录改为独立的 `/agent/login` 页面，使用随机 loopback 端口、一次性 `state` 和 HTML Form POST；不改造旧 `/login-cli`，不兼容旧 `vivago-client` 回调，也不迁移 Python Pilot 凭证。
