# WSL Snapaste

Windows 截图 → 一键粘贴到 WSL 终端。

## 痛点

Windows 剪贴板里的图片无法直接 Ctrl+V 到 WSL 终端。想发给 WSL 里的 AI 编程工具（Codex CLI、OpenCode、Claude Code、Cursor 等），需要：

截图 → 手动保存 → `wslpath` 转换 → 复制路径 → 粘贴

WSL Snapaste 让这个过程变成一步：截图 → Ctrl+V。

## 快速开始

### 下载预编译

从 [Releases](https://github.com/breath57/wsl-snapaste/releases/latest) 下载 `WSL-Snapaste-x.x.x.exe`，直接运行。

### 从源码运行

```bash
# 安装 uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

git clone https://github.com/breath57/wsl-snapaste.git
cd wsl-snapaste
uv sync
uv run python main.py
```

## 工作流程

1. 截图（Snipaste、ShareX、Win+Shift+S、QQ 截图……任何可写入剪贴板的工具）
2. 切换到 WSL 终端
3. Ctrl+V → 得到 `/tmp/snapaste/snap_xxxxx.png`
4. AI 工具立即读取图片

截图后剪贴板同时保留图片和路径文本，Windows 中粘贴仍是图片，不影响日常工作。

## 系统托盘

右键托盘图标：

- **状态** > 开启 / 关闭
- **退出**

## 要求

- Windows + WSL
- Python >= 3.13（从源码运行时）
- Windows 截图工具（任意）

## 技术原理

通过 `SetClipboardViewer` 监听剪贴板变化，检测到图片后：

1. 保存为 PNG（自动清理，最多 50 张）
2. 在剪贴板中同时写入图片数据、WSL 路径文本、文件拖放格式

Windows 应用粘贴得到图片，WSL 终端粘贴得到路径。

## License

MIT
