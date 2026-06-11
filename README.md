# WSL Snapaste

<p align="center">
  <img src="assets/wsl-snapaste-logo-concept1.svg" alt="WSL Snapaste Logo" width="200">
</p>

<p align="center">
  Windows 截图 → 一键粘贴到 WSL 终端
</p>

## 痛点

Windows 剪贴板里的图片无法直接 Ctrl+V 到 WSL 终端。想发给 WSL 里的 AI 编程工具（Codex CLI、OpenCode、Claude Code、Cursor 等），需要：

截图 → 手动保存 → `wslpath` 转换 → 复制路径 → 粘贴

WSL Snapaste 让这个过程变成一步：截图 → Ctrl+V。

## 快速开始

从 [Releases](https://github.com/breath57/wsl-snapaste/releases/latest) 下载 `WSL-Snapaste-v1.0.2.exe`，直接运行即可。

## 工作流程

1. 截图（支持的截图软件见下方）
2. 切换到 WSL 终端
3. Ctrl+V → 得到 `/tmp/snapaste/snap_xxxxx.png`
4. AI 工具立即读取图片

截图后剪贴板同时保留图片和路径文本，Windows 中粘贴仍是图片，不影响日常工作。

## 支持的截图软件

只要是能将图片写入 Windows 剪贴板的截图工具，都自动支持：

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

本质上，任何支持标准剪贴板 API 的 Windows 截图工具均可使用。


## 系统托盘

右键托盘图标：

- **状态** > 开启 / 关闭
- **退出**

## 要求

- Windows + WSL

## 技术原理

通过 `SetClipboardViewer` 监听剪贴板变化，检测到图片后：

1. 保存为 PNG（自动清理，最多 50 张）
2. 在剪贴板中同时写入图片数据、WSL 路径文本、文件拖放格式

Windows 应用粘贴得到图片，WSL 终端粘贴得到路径。

## License

MIT
