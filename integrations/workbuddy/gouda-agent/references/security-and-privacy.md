# 安全与隐私说明

## 处理的数据

- 用户明确提交给够搭 Agent 的 prompt；
- 用户明确授权的本地附件；
- 用户要求预览或下载的够搭生成资源；
- Project、Conversation、Turn 和 SSE event 标识；
- 登录 ticket、refresh token 和上传期间的短期阿里云 STS 凭证。

prompt、消息历史和生成记录由够搭服务端保存。本地状态文件只保存恢复所需的 ID、游标、状态
和时间，不建立第二份聊天记录。附件只在用户明确通过 `--file` 选择后上传。

`artifact preview` 把单个资源写入操作系统临时目录供当前 WorkBuddy 会话展示；
`artifact download` 只写入用户明确给出的绝对路径并拒绝覆盖已有文件。预览文件不属于凭证或
状态数据，使用结束后可以删除，也可能由操作系统的临时目录清理策略回收。

## 访问的域名

- `goudaai.com`：登录、业务 API 和刷新；
- `*.oss-cn-beijing.aliyuncs.com`：把用户授权文件上传到接口返回的国内 bucket；
- `storage-cdn.hidreamai.com`：国内图片资源；
- `media-cdn.hidreamai.com`：国内视频、音频和文档资源。

API origin、登录 origin、区域和资源域名都写死在国内 profile 中，用户参数不能覆盖。OSS bucket
名称必须满足阿里云 bucket 格式，上传 region 固定为 `oss-cn-beijing`。

## 凭证保护

- 不把 ticket、refresh token、Cookie、Authorization、AccessKey、STS token 或签名 URL 写入
  stdout/stderr、状态文件、错误正文或文档示例；
- STS 凭证只在内存中用于单次上传，不持久化；
- 输出层按敏感字段名和常见签名 URL 参数执行二次脱敏；
- 本地凭证使用独立目录、限制权限、原子替换并拒绝符号链接；
- `auth logout` 可删除本地登录凭证。

## 已知审核风险

登录复用现有够搭页面和 loopback Form POST，不是标准 OAuth。尽管实现包含 HTTPS 登录页、
随机 state、loopback-only、单次回调和受限本地存储，腾讯 WorkBuddy 的最终审核结论仍由平台
决定，不能以本地测试替代审核承诺。

公开发布材料应如实说明：登录方式、回调地址、访问域名、本地凭证位置、POSIX/Windows 权限
差异、附件上传范围、服务端数据用途与保留策略、退出登录的删除行为，以及隐私政策和联系渠道。
