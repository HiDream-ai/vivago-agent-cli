---
name: gouda-agent
display_name: 够搭 Agent
display_name_en: Gouda Agent
description: 够搭 Agent 是智象未来推出的一站式 AI 创意生产助手，可将文字和参考素材转化为图片、视频等内容，支持长任务执行、断点恢复、成果预览和协作交付。
description_zh: 够搭 Agent 是智象未来推出的一站式 AI 创意生产助手，可将文字和参考素材转化为图片、视频等内容，支持长任务执行、断点恢复、成果预览和协作交付。
description_en: Gouda Agent is an AI creative production assistant from HiDream that turns prompts and reference assets into images, videos, and other creative content with recovery and delivery support.
category: 创意工具
version: 1.0.1
author: HiDream.ai
allowed-tools: Bash
---

# 够搭 Agent

够搭 Agent 是面向 WorkBuddy 的 AI 创意生产 Skill。你可以直接描述想要的画面、视频或创意内容，
也可以附上参考素材；Skill 会协助整理需求、提交任务、跟踪进度、检查结果并交付成品。

## 能力介绍

- **图片创作**：根据文字描述和参考素材生成图片，并展示多个候选结果供选择。
- **视频创作**：支持从 brief、分镜、参考图和配音要求开始生成完整视频。
- **持续创作**：在同一 Conversation 中继续修改，尽量复用已经生成的镜头和素材。
- **长任务恢复**：视频生成耗时较长或连接中断时，可以恢复原任务，不重复提交请求。
- **成果交付**：生成后先检查内容，再创建本地预览；需要协作时提供 Project 深链。

## 适合处理的任务

- 产品广告、品牌视觉、社交媒体配图和宣传视频；
- 故事片段、概念设计、场景探索和创意方向验证；
- 需要参考图片、指定画面比例、总时长或目标平台的创作任务；
- 对已有结果进行改图、改镜头、调整风格或继续扩展；
- 查询进行中的任务、恢复中断的任务或取消尚未完成的任务。

## 使用方法

### 第一次使用

本 Skill 需要 Node.js 18 或更高版本。首次使用先检查运行环境：

```bash
node scripts/gouda-agent.js doctor
```

如果尚未登录，Skill 会打开够搭登录页。请在当前设备的浏览器中完成登录，登录结束后回到
WorkBuddy；不需要复制或提供密码、ticket、refresh token 等凭证。

### 描述创作需求

尽量说明主体、风格、画面比例、目标平台、参考素材和必须避免的内容。视频任务还应说明总时长、
场景、配音和字幕需求；没有指定的参数，Skill 会先说明采用的默认值。

用户明确授权在线视觉素材搜索时，Skill 才会启用图片搜索；普通图片或视频生成不会自动搜索网络。

### 提交附件

只有用户明确选择的本地文件才会作为参考素材上传。每个附件使用独立的 `--file` 参数，不用把
本地路径写进 prompt，也不读取未授权的其他文件。

## 任务执行与交付

1. Skill 先确认登录状态，并检查是否存在需要继续处理的任务。
2. 用户没有提供 Project 时，创建一个用于本次创作的 **v3 Project**。
3. 按需求提交图片或视频任务；视频任务会提示预计耗时，并在阶段变化时同步进度。
4. 只有收到远端完成状态并检查产物后，才会报告生成成功。
5. 图片、视频或音频会先生成本地预览；只有用户指定保存位置时才下载到该位置。
6. 交付时提供最终产物，并附上国内 Project 深链，方便继续修改和协作。

视频的字幕烧录、独立音效层和精确 TTS 音色选择存在能力边界。遇到这些需求时，Skill 会在提交
前说明限制，并在交付阶段给出可行的宿主侧补救方案，不会把未完成的能力当作已完成结果。

## 继续修改与恢复

- 修改已有成品时，优先在原 Conversation 中提交，不为普通修改重复创建 Project。
- 查询任务状态时只读取已有状态，不会因为查询而提交新任务。
- 如果 WorkBuddy 重启、宿主超时或 SSE 连接中断，使用原 Turn 和游标恢复；不会重新提交原 prompt。
- 只有用户明确要求取消时才发起取消。取消接口异步受理，在看到最终状态前不会声称任务已经停止。

## 安全与隐私

- 服务连接国内够搭正式环境，使用固定的业务接口和资源地址，不接受运行时改写服务 origin。
- 服务端保存用户提交的 prompt、消息历史和生成记录；本地只保存恢复任务所需的 Project、Conversation、
  Turn、游标、状态和时间，不建立第二份聊天记录。
- 登录凭证保存在 WorkBuddy 独立的本地目录中，附件上传只使用单次短期凭证；凭证不会出现在命令输出、
  错误信息、状态文件或任务内容中。
- 预览文件写入操作系统临时目录；永久下载只写入用户明确指定的绝对路径，并拒绝覆盖已有文件。
- Skill 不会输出密码、ticket、refresh token、Cookie、Authorization、AccessKey、STS token 或签名 URL。

## Agent 执行规范

Skill 只能通过自带的命令入口运行：

```bash
node scripts/gouda-agent.js <command>
```

执行时遵循以下规则：

- 使用脚本固定的国内配置，不搜索、安装或调用其他 CLI、二进制、npm 依赖或未声明的接口；
- 新 Project 固定使用 `version: "v3"`，一个 Project 不重复提交多个 Conversation；
- 先执行 `auth status` 和 `state list`，发现未完成任务时优先恢复；
- 只解析命令输出中的 JSON 或 JSONL 字段，不从自由文本、stderr 或日志猜测 ID；
- 只有 `RUN_FINISHED` 才是成功，`RUN_ERROR` 是业务失败，流提前结束必须按可恢复中断处理；
- 遇到 `PROJECT_CONVERSATION_CONFLICT` 不重复提交原 prompt，按恢复手册选择已有 Conversation 或请求用户确认；
- 任何时候都不输出或传播凭证、授权头、签名地址和本地凭证文件内容。

按需读取以下参考资料：

- @references/brief-guide.md — 编写图片和视频任务 brief；
- @references/recovery-runbook.md — 长任务、流中断、恢复和取消；
- @references/output-shapes.md — JSON/JSONL 输出和最终产物 ID；
- @references/delivery-playbook.md — 产物检查、预览、下载和交付；
- @references/capability-limits.md — 字幕、音效和 TTS 等能力边界；
- @references/commands.md — 命令、参数和退出码；
- @references/authentication.md — 登录、刷新、退出和本地凭证；
- @references/api-contract.md — 国内 API、Project、Conversation 和资源协议；
- @references/security-and-privacy.md — 数据范围、访问域名和隐私安全说明。
