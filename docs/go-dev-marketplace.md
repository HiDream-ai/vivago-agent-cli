# Go 六平台开发 Marketplace

这套流程只生成海外测试环境的 `vivago-dev` staging 包，用于开发和 12 组合 E2E。它读取
`plugin/` 中的 Go 插件模板，不会安装插件、推送 GitHub 或更新
Marketplace 分支。

前置条件：使用仓库固定的 Go 1.25.12，源码已经提交，并取得完整 40 位 Git SHA。先构建六个平台：

```bash
python scripts/build_go_binaries.py \
  --output /tmp/vivago-go-binaries \
  --version 0.3.0-dev.1 \
  --source-revision <40-char-source-sha>
```

构建器固定 `CGO_ENABLED=0`，生成 macOS/Linux/Windows 的 ARM64 与 x64 二进制，并注入版本、SHA、
`channel=dev`。每份二进制必须包含海外测试登录入口；发现海外正式登录入口、国内环境标识或不完整
目标时直接失败并清理输出目录。

再组装 Codex 与 Claude Code 共用的开发 Marketplace：

```bash
python scripts/assemble_go_distribution.py \
  --plugin-template plugin \
  --binary-root /tmp/vivago-go-binaries \
  --output /tmp/vivago-dev-marketplace \
  --version 0.3.0-dev.1 \
  --source-revision <40-char-source-sha>
```

输出包含六份二进制、POSIX/Windows 启动器、双插件 manifest、双 Marketplace、`SHA256SUMS` 和
`BUILD_INFO.json`。启动器只选择包内当前 OS/CPU 的二进制，不下载文件、不修改 PATH，也不调用
`vivago-client`。

交付前运行：

```bash
python /absolute/path/to/plugin-creator/scripts/validate_plugin.py \
  /tmp/vivago-dev-marketplace/plugins/vivago-agent-cli

python scripts/verify_dev_distribution.py \
  --marketplace /tmp/vivago-dev-marketplace \
  --version 0.3.0-dev.1 \
  --source-revision <40-char-source-sha>
```

个人 GitHub 的 `.github/workflows/ci.yml` 自动执行上述构建、双宿主校验、checksum 与环境扫描，并上传
模式位保持完整的压缩包。需要发布可安装版本时，从 Actions 页面手动运行 `dev-release.yml`，输入
`0.3.0-dev.N`；它重新构建全部制品，创建 GitHub Prerelease，并以普通快进提交更新
`dev-marketplace`。工作流不接受 profile 或环境地址输入。

开发包名称固定为 `vivago-dev`，不得改名冒充公开 `vivago`。真正的 prod/Beta 组装由公司 GitHub CI
另行实现，只能从公司受保护 Tag 以 `prod` profile 重新构建，不能复用这里生成的任何二进制。
