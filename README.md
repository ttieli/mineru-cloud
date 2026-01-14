# MinerU Cloud CLI | MinerU 云端命令行工具

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## English

A command-line interface for the [MinerU](https://mineru.net) Cloud OCR parsing service. Efficiently parse PDFs, images, and URLs into structured data.

### Features

*   **Smart Parsing:** Supports PDF, DOCX, PPTX, Images, and URLs.
*   **Batch Processing:** Submit multiple files or URLs at once.
*   **Formula & Table Recognition:** Advanced options to toggle specific recognition features.
*   **Persistent Configuration:** Token configuration survives system reboots.
*   **Result Management:** Automatically downloads and extracts results.

### Installation

#### Option 1: Python (Recommended)

Requires Python 3.6+.

1.  Clone the repository:
    ```bash
    git clone https://github.com/ttieli/mineru-cloud.git
    cd mineru-cloud
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  (Optional) Install globally:
    ```bash
    pip install .
    ```

#### Option 2: NPM

If you prefer managing tools via npm:

```bash
npm install -g mineru-cli
# Or from local source
npm install -g .
```

*Note: This still requires Python 3 to be installed on your system.*

### Configuration

Before using the tool, you must configure your API token.

1.  **Get Token:** Get your API token from [mineru.net](https://mineru.net).
2.  **Set Token:**

    **Method A: Interactive**
    ```bash
    mineru config
    ```
    
    **Method B: Direct Command**
    ```bash
    mineru token <your_token_here>
    ```

**Persistence:** The token is saved to `~/.config/mineru/config.json`. You do not need to re-enter it unless it expires.

### Usage

#### Basic Parsing
Parse a file and wait for the result (saved to a timestamped folder):
```bash
mineru document.pdf
```

#### Parse URL
```bash
mineru https://example.com/paper.pdf
```

#### Batch Processing
Parse all PDF files in the current directory:
```bash
mineru batch *.pdf
```

#### Options
*   `-o <dir>`: Specify output directory.
*   `--no-wait`: Submit task and exit immediately (don't wait for download).
*   `--ocr`: Force OCR mode.
*   `--no-formula`: Disable formula recognition.
*   `--no-table`: Disable table recognition.
*   `--format markdown,json`: Request specific output formats.

#### Check Status
```bash
mineru status <task_id>
```

---

<a name="中文"></a>
## 中文

[MinerU](https://mineru.net) 云端 OCR 解析服务的命令行接口工具。高效地将 PDF、图片和 URL 解析为结构化数据。

### 功能特性

*   **智能解析:** 支持 PDF, DOCX, PPTX, 图片以及 URL 链接。
*   **批量处理:** 支持一次性提交多个文件或链接。
*   **公式与表格识别:** 提供选项以开启或关闭特定识别功能。
*   **配置持久化:** Token 配置自动保存，重启依然有效。
*   **结果管理:** 自动下载并解压解析结果。

### 安装指南

#### 选项 1: Python (推荐)

需要 Python 3.6+ 环境。

1.  克隆仓库:
    ```bash
    git clone https://github.com/ttieli/mineru-cloud.git
    cd mineru-cloud
    ```

2.  安装依赖:
    ```bash
    pip install -r requirements.txt
    ```

3.  (可选) 全局安装:
    ```bash
    pip install .
    ```

#### 选项 2: NPM

如果您习惯使用 npm 管理工具：

```bash
npm install -g mineru-cli
# 或者从本地源码安装
npm install -g .
```

*注意: 无论哪种方式，您的系统都需要预先安装 Python 3。*

### 配置

使用前需要配置 API Token。

1.  **获取 Token:** 请前往 [mineru.net](https://mineru.net) 获取。
2.  **设置 Token:**

    **方式 A: 交互式配置**
    ```bash
    mineru config
    ```
    
    **方式 B: 快捷命令**
    ```bash
    mineru token <your_token_here>
    ```

**持久化说明:** Token 将保存在 `~/.config/mineru/config.json` 中，**永久有效**（除非过期或手动更改），无需每次输入。

### 使用方法

#### 基础解析
解析文件并等待结果（结果保存在带时间戳的文件夹中）:
```bash
mineru document.pdf
```

#### 解析 URL
```bash
mineru https://example.com/paper.pdf
```

#### 批量处理
解析当前目录下所有 PDF 文件:
```bash
mineru batch *.pdf
```

#### 常用选项
*   `-o <dir>`: 指定输出目录。
*   `--no-wait`: 提交任务后立即退出（不等待下载）。
*   `--ocr`: 强制开启 OCR 模式。
*   `--no-formula`: 禁用公式识别。
*   `--no-table`: 禁用表格识别。
*   `--format markdown,json`: 请求额外的输出格式。

#### 查看状态
```bash
mineru status <task_id>
```

## License

MIT