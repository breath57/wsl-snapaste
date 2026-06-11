# WSL Snapaste

<p align="center">
  <img src="assets/wsl-snapaste-logo-concept1.svg" alt="WSL Snapaste Logo" width="200">
</p>

<p align="center">
  Windows 截图 → 一键粘贴到 WSL 终端
</p>

## 痛点

Windows截图后，无法直接 Ctrl+V 到 WSL AI 编程工具（Codex CLI、OpenCode、Claude Code、Cursor 等）。

## 支持的截图软件

几乎所有截图软件都支持：

- **Snipaste**（F1 悬停截图、F2 截屏注解）
- **ShareX**（专业级截图录屏工具）
- **Windows 系统截图**（Win+Shift+S）
- **QQ 截图**（Ctrl+Alt+A）
- **微信截图**（Alt+A）
- **DingTalk 截图**（Ctrl+Shift+A）
- **FastStone Capture**
- **PicPick**（多功能截图工具）
- **ScreenToGif**（截图转 GIF）
- **HyperSnap**（屏幕捕捉工具）
- **Nimbus Screenshot**
- **Loom**（屏幕录制）
- **OBS Studio**（录屏软件截图）
- **Shotcut**等
- 没有提到的也支持

## 快速开始

从 [Releases](https://github.com/breath57/wsl-snapaste/releases/latest) 下载 `WSL-Snapaste-v1.0.3.exe`，直接运行即可。

## 工作流程

1. 截图（支持的截图软件见下方）
2. 切换到 WSL 终端
3. Ctrl+V → 得到 `/tmp/snapaste/snap_xxxxx.png`
4. AI 工具立即读取图片

截图后剪贴板同时保留图片和路径文本，Windows 中粘贴仍是图片，不影响日常工作。


本质上，任何支持标准剪贴板 API 的 Windows 截图工具均可使用。


## 系统托盘

右键托盘图标：

- **状态** > 开启 / 关闭
- **退出**

## License

MIT
