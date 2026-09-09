# 产物交付手册

从收到远端终态到用户真正拿到结果之间，按本文件处理。

## 交付前验证

远端完成摘要不是交付证据。视频至少检查：

1. 读取时长和分辨率，与 brief 的总时长和比例对比。
2. 每个场景至少抽查一帧，检查主体、参考图外观、品牌标识和生成乱码。
3. 确认配音和字幕是否实际存在；有疑问时转录音轨。
4. 发现偏差时如实说明，并给出同一 Conversation 远端修改或宿主侧补救方案。

图片只检查主体、外观锁定、比例和禁止内容，不执行时长和音频检查。

## 本地预览

成功事件或历史中拿到图片、视频或音频 `content_id` 后，先生成临时预览：

```bash
node scripts/gouda-agent.js artifact preview \
  --media-type <image|video|audio> --content-id "<content-id>"
```

脚本使用国内 CDN、唯一临时目录、媒体类型检查和下载大小限制。只有用户明确指定永久保存位置
时才运行：

```bash
node scripts/gouda-agent.js artifact download \
  --media-type <image|video|audio> --content-id "<content-id>" \
  --output "<绝对路径>"
```

下载拒绝覆盖已有路径。不要自行替换资源域名，也不要把未经 allowlist 校验的 URL 传给其他
下载工具。

## 展示顺序

先展示最终产物。过程片段、分镜图和被淘汰候选只在用户要求时展示；图片有多个候选时全部
展示，由用户选择。使用宿主真正支持的本地媒体渲染方式。宿主不能内联显示时，提供命令返回的
绝对路径、时长和大小，不要声称已经展示。

不要把远程媒体 URL 作为主要预览方式：宿主代理和媒体处理可能让有效资源看起来不可用。

## 协作链接

优先分享 Project 深链，而不是裸资源 URL：

```bash
node scripts/gouda-agent.js project link \
  --project-id "<project-id>" --conversation-id "<conversation-id>"
```

原样展示返回的 `deep_link`。脚本负责选择国内 Web origin；不要手工拼接或替换域名。Project
链接固定使用站点顶层 `/new-chat` 路由，包含完整创作会话和素材；`artifact url` 只在用户明确
要求裸资源地址时使用。

## 交付时的下一步

主动说明两项用户不容易发现的能力：

- 可以在同一 Conversation 继续修改并复用已有镜头，通常比重新生成完整任务成本低。
- 可以通过 Project 深链进行查看和协作。
