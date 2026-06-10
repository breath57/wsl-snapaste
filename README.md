# WSL Snapaste

把 Windows 截图直接粘贴到 WSL 终端——一步到位。

## 痛点

在 Windows 上用 Snipaste、ShareX、Win+Shift+S 等截图后，图片在 Windows 剪贴板里。但 WSL 终端无法直接读取 Windows 剪贴板中的图片数据——Ctrl+V 粘贴进去的是乱码或者什么都没有。

这意味着每次想把截图发给 WSL 里的 AI 编程工具（Codex CLI、OpenCode、Claude Code、Cursor Terminal 等），都需要：截图 → 手动保存文件 → 用 `wslpath` 转换路径 → 复制路径 → 粘贴到终端。

WSL Snapaste 解决这个问题：监听剪贴板，截图后自动将图片保存为文件，并把 WSL 路径写回剪贴板。你在 WSL 终端里直接 Ctrl+V，得到的就是图片路径。

## 安装

```
# 安装 uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

git clone https://github.com/breath57/wsl-snapaste.git
cd wsl-snapaste

uv sync
```

## 使用

### 启动

```
uv run python main.py
```

程序在系统托盘静默运行，无窗口。也可以用 `start.vbs` 实现开机静默启动。

### 工作流程

1. 用任意截图工具截图（Snipaste、ShareX、Win+Shift+S、QQ 截图……）
2. 切换到 WSL 终端
3. Ctrl+V → 得到 `/tmp/snapaste/snap_xxxxx.png` 路径
4. AI 工具直接读取图片，开始工作

截图后剪贴板同时保留图片数据和路径文本，Windows 中粘贴仍然是图片，不影响日常使用。

### 托盘控制

右键托盘图标：

- **状态** > 开启 / 关闭 — 关闭后不处理剪贴板，恢复原始行为
- **退出** — 关闭程序

## 要求

- Windows + WSL
- Python >= 3.13
- 任意 Windows 截图工具（Snipaste、ShareX、Win+Shift+S、QQ 截图等）

## 技术原理

程序通过 `SetClipboardViewer` 监听 Windows 剪贴板变化。检测到图片后：

1. 将 DIB 数据保存为 PNG（自动清理，最多保留 50 张）
2. 在剪贴板中同时写入图片数据、WSL 路径文本和文件拖放格式

Windows 应用粘贴得到的仍然是图片，WSL 终端粘贴得到的是路径。

## License

MIT
