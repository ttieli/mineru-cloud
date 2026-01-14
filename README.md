# MinerU Cloud CLI

A command-line interface for the [MinerU](https://mineru.net) Cloud OCR parsing service. Efficiently parse PDFs, images, and URLs into structured data.

## Features

*   **Smart Parsing:** Supports PDF, DOCX, PPTX, Images, and URLs.
*   **Batch Processing:** Submit multiple files or URLs at once.
*   **Formula & Table Recognition:** Advanced options to toggle specific recognition features.
*   **Persistent Configuration:** Token configuration survives system reboots.
*   **Result Management:** Automatically downloads and extracts results.

## Installation

### Option 1: Python (Recommended)

Requires Python 3.6+.

1.  Clone the repository:
    ```bash
    git clone https://github.com/yourusername/mineru-cli.git
    cd mineru-cli
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3.  (Optional) Install globally:
    ```bash
    pip install .
    ```

### Option 2: NPM (Wrapper)

If you prefer managing tools via npm:

```bash
npm install -g .
```

*Note: This still requires Python 3 to be installed on your system.*

## Configuration

Before using the tool, you must configure your API token.

1.  **Get Token:** detailed instructions at [mineru.net](https://mineru.net).
2.  **Set Token:**
    ```bash
    mineru config
    ```
    Follow the interactive prompt to paste your token.

**Note on Persistence:**
The token is saved to `~/.config/mineru/config.json` and **will persist across system restarts**. You do not need to re-enter it unless it expires or changes.

### Updating an Expired Token

If your token expires or you want to switch accounts, simply run the config command again:

```bash
mineru config
```

Or verify your current setting:

```bash
mineru config --show
```

## Usage

### Basic Parsing
Parse a file and wait for the result (saved to a timestamped folder):
```bash
mineru document.pdf
```

### Parse URL
```bash
mineru https://example.com/paper.pdf
```

### Batch Processing
Parse all PDF files in the current directory:
```bash
mineru batch *.pdf
```

### Options
*   `-o <dir>`: Specify output directory.
*   `--no-wait`: Submit task and exit immediately (don't wait for download).
*   `--ocr`: Force OCR mode.
*   `--no-formula`: Disable formula recognition.
*   `--format markdown,json`: Request specific output formats.

### Check Status
If you used `--no-wait`, you can check status later:
```bash
mineru status <task_id>
```

## Development

1.  Make changes to `mineru_cli.py`.
2.  Deploy your changes to your local global command (if set up):
    ```bash
    ./deploy.sh
    ```

## License

MIT
