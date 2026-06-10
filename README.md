# WSL Snapaste

Windows 截图粘贴到 WSL 终端 AI 工具（Codex CLI、OpenCode、Claude Code 等）的桥接方案。

## 问题背景

在 WSL 终端中使用 AI 编码工具时，经常需要把 Windows 截图传给 AI 分析。常见方式是拖拽文件，但每次都要先保存截图再找到文件再拖拽，流程繁琐。

直接 Ctrl+V 粘贴剪贴板中的图片到 WSL 终端，终端只认文本格式，图片数据会被丢弃。

## 核心原理

Windows 剪贴板不是单一数据槽，而是一个**多格式容器**。一次写入可以同时存放多种格式：

```
剪贴板
├── Text/UnicodeText  →  "/mnt/c/Users/ws/Pictures/snap_123456.png"
├── Bitmap (DIB)      →  [PNG 图片二进制数据]
└── FileDrop (HDROP)  →  ["C:\Users\ws\Pictures\snap_123456.png"]
```

每个粘贴目标应用**自行选择它认识的格式**：

| 粘贴到 | 读取的格式 | 效果 |
|--------|-----------|------|
| WSL 终端（Windows Terminal） | Text | 收到 WSL 路径字符串 |
| 画图 / 钉钉 / Word | Bitmap | 粘贴出实际图片 |
| 文件管理器 | FileDrop | 粘贴出文件引用 |

不需要检测前台窗口，剪贴板本身天然实现了智能分流。

## PowerShell 验证过程

在开发应用之前，我们用 PowerShell 脚本验证了这个方案的可行性。

### 步骤 1：确认图片文件存在

```powershell
Get-Item "C:\Users\ws\Pictures\截图.png" | Select-Object FullName, Length
```

输出：文件存在，8911 字节。

### 步骤 2：多格式写入剪贴板

```powershell
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$imgPath = "C:\Users\ws\Pictures\截图.png"
$wslPath = "/mnt/c/Users/ws/Pictures/截图.png"

$img = [System.Drawing.Image]::FromFile($imgPath)

$data = New-Object System.Windows.Forms.DataObject

# Text 格式：WSL 路径
$data.SetData([System.Windows.Forms.DataFormats]::Text, $wslPath)
$data.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $wslPath)

# Bitmap 格式：Windows 应用用
$data.SetData([System.Windows.Forms.DataFormats]::Bitmap, $img)

# FileDrop 格式：支持文件拖拽的应用用
$fileList = New-Object System.Collections.Specialized.StringCollection
$fileList.Add("C:\Users\ws\Pictures\截图.png")
$data.SetData([System.Windows.Forms.DataFormats]::FileDrop, $fileList)

[System.Windows.Forms.Clipboard]::SetDataObject($data, $true)

$img.Dispose()
```

### 步骤 3：验证结果

粘贴测试结果：

- **WSL 终端（Codex CLI）**：收到路径 `/mnt/c/Users/ws/Pictures/截图.png`，显示为 `[Image #1]` ✅
- **Windows 应用（画图/钉钉）**：粘贴出实际图片 ✅

两种场景都能正确工作，无需任何额外判断逻辑。

## 应用架构

项目由两个核心模块组成：

### clipboard.py - 剪贴板操作

- `has_clipboard_image()`：检测剪贴板中是否有图片
- `get_clipboard_image()`：从剪贴板提取图片（通过 CF_DIB 格式）
- `save_clipboard_image()`：将图片保存为 PNG 到临时目录
- `set_clipboard_multi()`：将图片以多格式写回剪贴板（Text + Bitmap + FileDrop）
- `win_to_wsl_path()`：将 Windows 路径转换为 WSL 路径（如 `C:\foo` → `/mnt/c/foo`）
- `is_snapaste_clipboard()`：检测当前剪贴板是否已经是本工具处理过的，避免重复处理
- `snapaste()`：完整的处理流程入口

### app.py - 系统托盘应用

- 监听 Windows 剪贴板变化（通过 `SetClipboardViewer` API）
- 检测到新图片时自动执行多格式注入
- 系统托盘图标，支持开关自动监听和手动触发

## 使用方式

```bash
# 开发模式运行
uv run main.py

# 或激活虚拟环境后
python main.py
```

启动后在系统托盘出现图标，自动监听剪贴板。截图后（Win+Shift+S）图片自动被处理，直接 Ctrl+V 粘贴到 WSL 终端即可。

## 技术细节

### 路径转换规则

`C:\Users\ws\Pictures\snap.png` → `/mnt/c/Users/ws/Pictures/snap.png`

规则：盘符字母小写，反斜杠改正斜杠，去掉 `:\` 前缀。

### 图片格式转换

Windows 剪贴板使用 DIB (Device Independent Bitmap) 格式存储图片数据。应用读取 CF_DIB 数据后，手动构建 BMP 文件头，转换为 PNG 保存，再通过构造 DIB 数据写回剪贴板。

### FileDrop 格式

用于模拟文件拖拽效果。构造 `DROPFILES` 结构体 + UTF-16 文件路径列表，通过 `GlobalAlloc` 分配内存后写入剪贴板。这是 Windows 标准的文件拖拽数据格式。

## 依赖

- Python >= 3.13
- pywin32（Windows API 访问）
- Pillow（图片处理）
- infi-systray（系统托盘）
