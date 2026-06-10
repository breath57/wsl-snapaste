# WSL Snapaste

Windows 截图一键粘贴到 WSL 终端的工具。

## 功能

截图（Win+Shift+S）后，程序自动将剪贴板中的图片转为路径格式。直接在 WSL 终端中 Ctrl+V 粘贴，即可得到文件路径（如 `/mnt/c/...`），AI 工具（Codex CLI、OpenCode、Claude Code 等）可以立即识别并处理。

## 安装

```
# 安装 uv（如果还没有）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 克隆项目
git clone <repo-url>
cd wsl-snapaste

# 安装依赖
uv sync
```

## 使用

### 启动

```
uv run python main.py
```

启动后程序在系统托盘运行，无窗口。也可使用 `start.vbs` 静默启动（无控制台窗口）。

### 托盘菜单

右键点击托盘图标：

- **状态** > 开启 / 关闭
  - **开启**（默认）：截图后自动将剪贴板转换为 WSL 路径格式，Windows 粘贴仍为图片
  - **关闭**：不处理剪贴板，恢复原始行为
- 切换状态时会自动处理当前剪贴板内容
- **退出**：关闭程序

### 典型流程

1. 截图（Win+Shift+S）
2. 切换到 WSL 终端
3. Ctrl+V 粘贴 → 得到 `/mnt/c/...` 路径

## 要求

- Windows + WSL
- Python >= 3.13
- 依赖：pywin32、Pillow
