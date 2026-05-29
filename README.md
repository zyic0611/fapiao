# 发票 PDF 识别工具

从 PDF 发票第一页自动识别**发票号码**，支持批量处理与 Excel 导出。

## 功能

- 选择单个或多个 PDF 文件
- 只读取每个 PDF 的**第一页**
- 优先提取 PDF 文本层；识别不到时自动 OCR 兜底
- 支持常见发票号码格式：8 位、12 位、20 位（全电发票）
- 结果可导出为 Excel（.xlsx）

## 给姐姐用（Windows）

1. 获取 `发票识别.exe`（见下方「打包 Windows exe」）
2. 双击运行
3. 点击「选择 PDF 文件」，选中发票 PDF（可多选）
4. 点击「开始识别」
5. 在表格中查看结果，需要时可点「导出 Excel」

> 首次识别若走 OCR，可能稍慢几秒，属正常现象。

## 开发者使用（Mac）

### 环境准备

本机 conda 环境名为 `py39`（Python 3.9）：

```bash
conda activate py39
pip install -r requirements.txt
```

### 本地运行

```bash
python app.py
```

或使用脚本：

```bash
bash scripts/run_dev.sh
```

### 项目结构

```
fapiao/
├── app.py              # Tkinter 界面
├── extractor.py        # 发票号码提取逻辑
├── requirements.txt
├── fapiao.spec         # PyInstaller 配置
└── scripts/
    ├── run_dev.sh      # Mac 开发启动
    └── build_windows.bat
```

## 打包 Windows exe

Mac 无法直接生成 Windows exe，推荐两种方式：

### 方式一：GitHub Actions（推荐）

1. 将代码推送到 GitHub
2. 在 Actions 中运行 `Build Windows EXE` 工作流
3. 下载 Artifact：`fapiao-windows-exe` 中的 `发票识别.exe`

### 方式二：在 Windows 上本地打包

```bat
scripts\build_windows.bat
```

生成文件位于 `dist\发票识别.exe`。

## 识别说明

- 只提取「发票号码」，不会把「发票代码」当成发票号码
- 多页 PDF 只处理第一页
- 扫描件或图片型 PDF 会走 OCR，清晰度太低时可能识别失败

## 依赖

- PyMuPDF：PDF 文本提取与页面渲染
- rapidocr-onnxruntime：OCR 兜底
- openpyxl：Excel 导出
- Tkinter：图形界面（Python 内置）
