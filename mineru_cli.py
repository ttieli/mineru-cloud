#!/usr/bin/env python3
"""
mineru - MinerU Cloud OCR CLI Tool

A command-line interface for MinerU cloud OCR parsing service.
Similar to `wf` (WebFetcher), this tool provides easy access to mineru.net API.

Usage:
    mineru <file_or_url>              # Parse a local file or URL
    mineru batch <files...>           # Batch parse multiple files
    mineru status <task_id>           # Query task status
    mineru token [new_token]          # Update API token
    mineru config                     # Configure API token
    mineru diagnose                   # Check service status
"""

import argparse
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import requests

# =============================================================================
# Configuration
# =============================================================================

CONFIG_DIR = Path.home() / ".config" / "mineru"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_OUTPUT_DIR = Path("./output")

API_BASE = "https://mineru.net"
API_ENDPOINTS = {
    "task": "/api/v4/extract/task",           # Single URL task
    "task_status": "/api/v4/extract/task/{}",  # Task status
    "batch_upload": "/api/v4/file-urls/batch", # Batch file upload
    "batch_url": "/api/v4/extract/task/batch", # Batch URL task
    "batch_status": "/api/v4/extract-results/batch/{}",  # Batch status
}

SUPPORTED_FORMATS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".png", ".jpg", ".jpeg", ".html"}

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def color(text: str, c: str) -> str:
    """Apply color to text if terminal supports it."""
    if sys.stdout.isatty():
        return f"{c}{text}{Colors.ENDC}"
    return text


# =============================================================================
# Configuration Management
# =============================================================================

def load_config() -> Dict:
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: Dict) -> None:
    """Save configuration to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_token() -> Optional[str]:
    """Get API token from config or environment."""
    # Priority: environment variable > config file
    token = os.environ.get("MINERU_API_TOKEN") or os.environ.get("MINERU_API_KEY")
    if token:
        return token
    config = load_config()
    return config.get("token")


def set_token(token: str) -> None:
    """Set API token in config."""
    config = load_config()
    config["token"] = token
    save_config(config)


def ensure_token() -> Optional[str]:
    """Get token, or prompt user to enter it if missing."""
    token = get_token()
    if token:
        return token

    print(color("No API token found.", Colors.YELLOW))
    return prompt_for_token()


def prompt_for_token() -> Optional[str]:
    """Interactive prompt for token."""
    print(color("MinerU API Configuration", Colors.BOLD))
    print()
    print(f"Please enter your API token from: {color('https://mineru.net', Colors.BLUE)}")
    print()
    try:
        token = input("Enter API token: ").strip()
        if token:
            set_token(token)
            print(color("\nToken saved successfully.", Colors.GREEN))
            print(f"Config file: {CONFIG_FILE}")
            return token
    except (KeyboardInterrupt, EOFError):
        print()
        return None
    
    print("No token provided.")
    return None


def get_default_output_dir() -> Path:
    """Get default output directory."""
    env_dir = os.environ.get("MINERU_OUTPUT_DIR")
    if env_dir:
        return Path(env_dir)
    config = load_config()
    if "output_dir" in config:
        return Path(config["output_dir"])
    return DEFAULT_OUTPUT_DIR


# =============================================================================
# API Client
# =============================================================================

class APIError(Exception):
    """API error exception."""
    pass


class AuthError(APIError):
    """Authentication failed."""
    pass


class MinerUClient:
    """Client for MinerU cloud API."""

    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "*/*"
        })

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """Make API request."""
        url = f"{API_BASE}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            result = response.json()
            code = result.get("code")
            
            if code != 0:
                error_msg = result.get("msg", "Unknown error")
                
                # Check for auth errors (codes may vary, adjust based on actual API)
                # Assuming typical auth error codes or messages
                if code == 401 or "auth" in error_msg.lower() or "token" in error_msg.lower():
                    raise AuthError(f"Authentication failed: {error_msg}")
                    
                raise APIError(f"API Error: {error_msg} (code: {code})")
                
            return result
        except requests.exceptions.RequestException as e:
            raise APIError(f"Request failed: {e}")

    def submit_url_task(self, url: str, **options) -> str:
        """Submit a URL parsing task. Returns task_id."""
        data = {"url": url}
        data.update(self._build_options(**options))
        result = self._request("POST", API_ENDPOINTS["task"], json=data)
        return result["data"]["task_id"]

    def submit_file_task(self, file_path: Path, **options) -> Tuple[str, str]:
        """Submit a file parsing task. Returns (batch_id, upload_url)."""
        data = {
            "files": [{"name": file_path.name}]
        }
        data.update(self._build_options(**options))
        result = self._request("POST", API_ENDPOINTS["batch_upload"], json=data)
        batch_id = result["data"]["batch_id"]
        upload_url = result["data"]["file_urls"][0]
        return batch_id, upload_url

    def submit_batch_files(self, file_paths: List[Path], **options) -> Tuple[str, List[str]]:
        """Submit multiple files for parsing. Returns (batch_id, upload_urls)."""
        data = {
            "files": [{"name": fp.name} for fp in file_paths]
        }
        data.update(self._build_options(**options))
        result = self._request("POST", API_ENDPOINTS["batch_upload"], json=data)
        batch_id = result["data"]["batch_id"]
        upload_urls = result["data"]["file_urls"]
        return batch_id, upload_urls

    def submit_batch_urls(self, urls: List[str], **options) -> str:
        """Submit multiple URLs for parsing. Returns batch_id."""
        data = {
            "files": [{"url": url} for url in urls]
        }
        data.update(self._build_options(**options))
        result = self._request("POST", API_ENDPOINTS["batch_url"], json=data)
        return result["data"]["batch_id"]

    def upload_file(self, file_path: Path, upload_url: str) -> bool:
        """Upload file to the given URL."""
        with open(file_path, 'rb') as f:
            response = requests.put(upload_url, data=f)
            return response.status_code == 200

    def get_task_status(self, task_id: str) -> Dict:
        """Get status of a single task."""
        endpoint = API_ENDPOINTS["task_status"].format(task_id)
        result = self._request("GET", endpoint)
        return result["data"]

    def get_batch_status(self, batch_id: str) -> Dict:
        """Get status of a batch task."""
        endpoint = API_ENDPOINTS["batch_status"].format(batch_id)
        result = self._request("GET", endpoint)
        return result["data"]

    def _build_options(self, model: str = "vlm", ocr: bool = False,
                       formula: bool = True, table: bool = True,
                       language: str = "ch", pages: str = None,
                       extra_formats: List[str] = None) -> Dict:
        """Build API options dict."""
        opts = {
            "model_version": model,
            "is_ocr": ocr,
            "enable_formula": formula,
            "enable_table": table,
            "language": language,
        }
        if pages:
            opts["page_ranges"] = pages
        if extra_formats:
            opts["extra_formats"] = extra_formats
        return opts


# =============================================================================
# Utility Functions
# =============================================================================

def is_url(s: str) -> bool:
    """Check if string is a URL."""
    try:
        result = urlparse(s)
        return result.scheme in ('http', 'https')
    except:
        return False


def extract_url(text: str) -> Optional[str]:
    """Extract URL from text."""
    # Match http/https URLs
    url_pattern = r'https?://[^\s<>"\'{}|\\^`\[\]]+'
    match = re.search(url_pattern, text)
    if match:
        return match.group(0)

    # Match domain-like patterns without protocol
    domain_pattern = r'(?:www\.)?[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}[^\s]*'
    match = re.search(domain_pattern, text)
    if match:
        return f"https://{match.group(0)}"

    return None


def get_file_extension(path: Path) -> str:
    """Get file extension in lowercase."""
    return path.suffix.lower()


def generate_output_dir_name(base_name: str) -> str:
    """Generate output directory name with MinerU tag and timestamp.

    Format: {base_name}_MinerU_{{YYYYMMDD}}_{{HHMMSS}}
    Example: document_MinerU_20260113_101500
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Remove file extension if present
    stem = Path(base_name).stem
    return f"{stem}_MinerU_{timestamp}"


def validate_file(path: Path) -> bool:
    """Validate file exists and has supported format."""
    if not path.exists():
        print(color(f"Error: File not found: {path}", Colors.RED))
        return False
    ext = get_file_extension(path)
    if ext not in SUPPORTED_FORMATS:
        print(color(f"Error: Unsupported format '{ext}'. Supported: {', '.join(SUPPORTED_FORMATS)}", Colors.RED))
        return False
    return True


def download_file(url: str, output_path: Path) -> bool:
    """Download file from URL."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(color(f"Download failed: {e}", Colors.RED))
        return False


def extract_zip(zip_path: Path, extract_dir: Path) -> bool:
    """Extract zip file."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        return True
    except Exception as e:
        print(color(f"Extraction failed: {e}", Colors.RED))
        return False


def format_time(seconds: float) -> str:
    """Format seconds to human readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def print_progress(state: str, extracted: int = 0, total: int = 0, start_time: str = ""):
    """Print progress bar (Legacy, kept for reference)."""
    pass


# =============================================================================
# Commands
# =============================================================================

def handle_auth_error(func):
    """Decorator to handle AuthError and prompt for token update."""
    def wrapper(args, *vargs, **kwargs):
        while True:
            try:
                return func(args, *vargs, **kwargs)
            except AuthError as e:
                print(color(f"\nAuthorization Error: {e}", Colors.RED))
                print("Your token may have expired or is invalid.")
                
                # Prompt to update
                try:
                    choice = input(f"Do you want to update your token now? [{color('Y', Colors.BOLD)}/n]: ").strip().lower()
                except (KeyboardInterrupt, EOFError):
                    choice = 'n'
                
                if choice not in ('n', 'no'):
                    new_token = prompt_for_token()
                    if new_token:
                        print("Token updated. Retrying...")
                        continue
                
                print("Aborted.")
                return 1
    return wrapper

@handle_auth_error
def cmd_parse(args):
    """Parse a single file or URL."""
    token = ensure_token()
    if not token:
        return 1

    client = MinerUClient(token)
    input_arg = args.input

    # Build options
    options = {
        "model": args.model,
        "ocr": args.ocr,
        "formula": not args.no_formula,
        "table": not args.no_table,
        "language": args.lang,
        "pages": args.pages,
        "extra_formats": args.format.split(",") if args.format else None,
    }

    # Check if input is URL or file
    if is_url(input_arg):
        url = input_arg
        # For URL, generate output dir name from URL path or use default
        url_path = urlparse(url).path
        url_filename = Path(url_path).name if url_path else "download"
        output_dir_name = generate_output_dir_name(url_filename)

        if args.output:
            output_dir = Path(args.output)
        else:
            output_dir = Path.cwd() / output_dir_name

        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"{color('URL:', Colors.BOLD)} {url}")
        print(f"{color('Output:', Colors.BOLD)} {output_dir}")
        print()

        try:
            task_id = client.submit_url_task(url, **options)
            print(f"{color('Task ID:', Colors.CYAN)} {task_id}")
        except APIError as e:
            if isinstance(e, AuthError): raise e
            print(color(str(e), Colors.RED))
            return 1

        # Default: wait for completion (use --no-wait to disable)
        if not args.no_wait:
            return wait_for_task(client, task_id, output_dir, args.timeout)
        else:
            print(f"\nUse '{color(f'mineru status {task_id}', Colors.CYAN)}' to check progress.")
            return 0

    # Try to extract URL from text
    extracted_url = extract_url(input_arg)
    if extracted_url and not Path(input_arg).exists():
        url_path = urlparse(extracted_url).path
        url_filename = Path(url_path).name if url_path else "download"
        output_dir_name = generate_output_dir_name(url_filename)

        if args.output:
            output_dir = Path(args.output)
        else:
            output_dir = Path.cwd() / output_dir_name

        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"{color('Extracted URL:', Colors.BOLD)} {extracted_url}")
        print(f"{color('Output:', Colors.BOLD)} {output_dir}")
        print()

        try:
            task_id = client.submit_url_task(extracted_url, **options)
            print(f"{color('Task ID:', Colors.CYAN)} {task_id}")
        except APIError as e:
            if isinstance(e, AuthError): raise e
            print(color(str(e), Colors.RED))
            return 1

        # Default: wait for completion (use --no-wait to disable)
        if not args.no_wait:
            return wait_for_task(client, task_id, output_dir, args.timeout)
        else:
            print(f"\nUse '{color(f'mineru status {task_id}', Colors.CYAN)}' to check progress.")
            return 0

    # Handle as local file
    file_path = Path(input_arg).expanduser().resolve()
    if not validate_file(file_path):
        return 1

    # Output directory: same directory as source file, with MinerU timestamp folder name
    output_dir_name = generate_output_dir_name(file_path.name)
    if args.output:
        output_dir = Path(args.output)
    else:
        # Default: output to same directory as source file
        output_dir = file_path.parent / output_dir_name

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"{color('File:', Colors.BOLD)} {file_path}")
    print(f"{color('Size:', Colors.BOLD)} {file_path.stat().st_size / 1024:.1f} KB")
    print(f"{color('Output:', Colors.BOLD)} {output_dir}")
    print()

    try:
        # Get upload URL
        print("Requesting upload URL...", end=" ", flush=True)
        batch_id, upload_url = client.submit_file_task(file_path, **options)
        print(color("OK", Colors.GREEN))

        # Upload file
        print("Uploading file...", end=" ", flush=True)
        if client.upload_file(file_path, upload_url):
            print(color("OK", Colors.GREEN))
        else:
            print(color("FAILED", Colors.RED))
            return 1

        print(f"{color('Batch ID:', Colors.CYAN)} {batch_id}")

    except APIError as e:
        if isinstance(e, AuthError): raise e
        print(color(str(e), Colors.RED))
        return 1

    # Default: wait for completion (use --no-wait to disable)
    if not args.no_wait:
        return wait_for_batch(client, batch_id, output_dir, args.timeout, file_path.stem)
    else:
        print(f"\nUse '{color(f'mineru status {batch_id}', Colors.CYAN)}' to check progress.")
        return 0

@handle_auth_error
def cmd_batch(args):
    """Batch parse multiple files or URLs."""
    token = ensure_token()
    if not token:
        return 1

    client = MinerUClient(token)
    inputs = args.inputs

    # Build options
    options = {
        "model": args.model,
        "ocr": args.ocr,
        "formula": not args.no_formula,
        "table": not args.no_table,
        "language": args.lang,
        "pages": args.pages,
        "extra_formats": args.format.split(",") if args.format else None,
    }

    # Separate URLs and files
    urls = []
    files = []
    for inp in inputs:
        if is_url(inp):
            urls.append(inp)
        else:
            path = Path(inp).expanduser().resolve()
            if validate_file(path):
                files.append(path)

    if not urls and not files:
        print(color("No valid inputs provided.", Colors.RED))
        return 1

    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    elif files:
        # Use first file's parent directory with batch timestamp
        output_dir_name = generate_output_dir_name("batch")
        output_dir = files[0].parent / output_dir_name
    else:
        # URL batch: use current directory
        output_dir_name = generate_output_dir_name("batch")
        output_dir = Path.cwd() / output_dir_name

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"{color('Output:', Colors.BOLD)} {output_dir}")

    batch_ids = []

    # Handle URLs
    if urls:
        print(f"\n{color('Submitting', Colors.BOLD)} {len(urls)} URLs...")
        try:
            batch_id = client.submit_batch_urls(urls, **options)
            batch_ids.append(("urls", batch_id, None))
            print(f"{color('Batch ID:', Colors.CYAN)} {batch_id}")
        except APIError as e:
            if isinstance(e, AuthError): raise e
            print(color(str(e), Colors.RED))

    # Handle files
    if files:
        print(f"\n{color('Submitting', Colors.BOLD)} {len(files)} files...")
        try:
            batch_id, upload_urls = client.submit_batch_files(files, **options)
            print(f"{color('Batch ID:', Colors.CYAN)} {batch_id}")

            # Upload each file
            for file_path, upload_url in zip(files, upload_urls):
                print(f"  Uploading {file_path.name}...", end=" ", flush=True)
                if client.upload_file(file_path, upload_url):
                    print(color("OK", Colors.GREEN))
                else:
                    print(color("FAILED", Colors.RED))

            batch_ids.append(("files", batch_id, files))
        except APIError as e:
            if isinstance(e, AuthError): raise e
            print(color(str(e), Colors.RED))

    if not batch_ids:
        return 1

    # Default: wait for completion (use --no-wait to disable)
    if not args.no_wait:
        for batch_type, batch_id, batch_files in batch_ids:
            print(f"\nWaiting for {batch_type} batch {batch_id}...")
            wait_for_batch(client, batch_id, output_dir, args.timeout)
        return 0
    else:
        print("\nBatch IDs:")
        for batch_type, batch_id, _ in batch_ids:
            print(f"  {batch_type}: {batch_id}")
        return 0

@handle_auth_error
def cmd_status(args):
    """Check task/batch status."""
    token = ensure_token()
    if not token:
        return 1

    client = MinerUClient(token)
    task_id = args.task_id

    # Determine output directory if downloading
    output_dir = Path(args.output) if args.output else get_default_output_dir()

    try:
        # Try as batch ID first
        try:
            status = client.get_batch_status(task_id)
            print_batch_status(status)

            # Download if all done and --download flag
            if args.download:
                results = status.get("extract_result", [])
                all_done = all(r.get("state") == "done" for r in results)
                if all_done:
                    output_dir.mkdir(parents=True, exist_ok=True)
                    for result in results:
                        if result.get("full_zip_url"):
                            download_result(result["full_zip_url"], output_dir, result.get("file_name", "result"))
            return 0
        except APIError as e:
            if isinstance(e, AuthError): raise e
            # Ignore regular API errors when guessing batch ID
            pass

        # Try as single task ID
        status = client.get_task_status(task_id)
        print_task_status(status)

        if args.download and status.get("state") == "done" and status.get("full_zip_url"):
            output_dir.mkdir(parents=True, exist_ok=True)
            download_result(status["full_zip_url"], output_dir, "result")

        return 0

    except APIError as e:
        if isinstance(e, AuthError): raise e
        print(color(str(e), Colors.RED))
        return 1


def cmd_token(args):
    """Update API token manually."""
    # If a token is provided as an argument, save it directly
    if args.inputs:
        new_token = args.inputs[0]
        set_token(new_token)
        print(color("Token updated successfully.", Colors.GREEN))
        return 0
    
    # Otherwise, use the interactive prompt
    prompt_for_token()
    return 0

def cmd_config(args):
    """Configure API token."""
    config = load_config()

    if args.show:
        token = get_token()
        if token:
            # Mask token for display
            masked = token[:10] + "..." + token[-10:] if len(token) > 25 else token
            print(f"Token: {masked}")
            print(f"Config file: {CONFIG_FILE}")
        else:
            print("No token configured.")
        return 0

    if args.token:
        set_token(args.token)
        print(color("Token saved successfully.", Colors.GREEN))
        return 0

    # Use shared prompt
    prompt_for_token()
    return 0


def cmd_diagnose(args):
    """Diagnose service connectivity."""
    print(color("MinerU Service Diagnostics", Colors.BOLD))
    print()

    # Check config
    print("1. Configuration:")
    token = get_token()
    if token:
        print(f"   {color('Token:', Colors.GREEN)} configured")
    else:
        print(f"   {color('Token:', Colors.RED)} not configured")

    output_dir = get_default_output_dir()
    print(f"   Output dir: {output_dir}")

    # Check network
    print("\n2. Network Connectivity:")
    try:
        response = requests.get(f"{API_BASE}", timeout=10)
        print(f"   {color('API Base:', Colors.GREEN)} reachable ({response.status_code})")
    except Exception as e:
        print(f"   {color('API Base:', Colors.RED)} unreachable ({e})")

    # Test API if token available
    if token:
        print("\n3. API Authentication:")
        try:
            client = MinerUClient(token)
            # Try a simple request - get a non-existent task will fail with specific error
            try:
                client.get_task_status("test-invalid-id")
            except APIError as e:
                if isinstance(e, AuthError):
                    print(f"   {color('Authentication:', Colors.RED)} invalid token")
                elif "找不到任务" in str(e) or "-60012" in str(e):
                    print(f"   {color('Authentication:', Colors.GREEN)} valid")
                else:
                    print(f"   {color('Authentication:', Colors.YELLOW)} {e}")
        except Exception as e:
            print(f"   {color('Authentication:', Colors.RED)} failed ({e})")

    print("\n4. Environment Variables:")
    env_vars = ["MINERU_API_TOKEN", "MINERU_API_KEY", "MINERU_OUTPUT_DIR"]
    for var in env_vars:
        val = os.environ.get(var)
        if val:
            print(f"   {var}: set")
        else:
            print(f"   {var}: not set")

    return 0


# =============================================================================
# Helper Functions
# =============================================================================

def wait_for_task(client: MinerUClient, task_id: str, output_dir: Path, timeout: int) -> int:
    """Wait for a single task to complete."""
    print("\nWaiting for completion...")
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            print(color(f"\nTimeout after {format_time(timeout)}", Colors.RED))
            return 1

        try:
            status = client.get_task_status(task_id)
            state = status.get("state", "unknown")

            progress = status.get("extract_progress", {})
            extracted = progress.get("extracted_pages", 0)
            total = progress.get("total_pages", 0)

            # Spinner animation
            spinner = ['|', '/', '-', '\\']
            spin_char = spinner[int(time.time() * 2) % 4]
            elapsed_str = f"({int(elapsed)}s)"

            print(f"\r{color(label, c)} {spin_char} {elapsed_str}", end="", flush=True)

            if state == "running" and total > 0:
                pct = int((extracted / total) * 100)
                bar_len = 30
                filled = int(bar_len * extracted / total)
                bar = "=" * filled + ">" + " " * (bar_len - filled - 1)
                print(f"\r{color(label, c)} [{bar}] {pct}% ({extracted}/{total} pages) {spin_char} {elapsed_str}", end="", flush=True)

            print("\033[K", end="", flush=True)

            if state == "done":
                print()
                if status.get("full_zip_url"):
                    download_result(status["full_zip_url"], output_dir, "result")
                print(color(f"\nCompleted in {format_time(elapsed)}", Colors.GREEN))
                return 0
            elif state == "failed":
                print()
                print(color(f"\nFailed: {status.get('err_msg', 'Unknown error')}", Colors.RED))
                return 1

        except APIError as e:
            # If wait loop hits an AuthError, we should probably stop waiting and let the main handler catch it
            # But main handler has already started the loop.
            # Ideally, wait_for_task should also propagate AuthError to the decorator.
            if isinstance(e, AuthError): raise e
            print(color(f"\n{e}", Colors.RED))

        time.sleep(5)


def wait_for_batch(client: MinerUClient, batch_id: str, output_dir: Path, timeout: int, expected_stem: str = None) -> int:
    """Wait for a batch task to complete.

    Args:
        client: MinerU API client
        batch_id: Batch task ID
        output_dir: Output directory (already includes MinerU timestamp)
        timeout: Timeout in seconds
        expected_stem: Expected file stem (used for single file mode to avoid nested folders)
    """
    print("\nWaiting for completion...")
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed > timeout:
            print(color(f"\nTimeout after {format_time(timeout)}", Colors.RED))
            return 1

        try:
            status = client.get_batch_status(batch_id)
            results = status.get("extract_result", [])

            done_count = sum(1 for r in results if r.get("state") == "done")
            failed_count = sum(1 for r in results if r.get("state") == "failed")
            total = len(results)

            # Spinner animation
            spinner = ['|', '/', '-', '\\']
            spin_char = spinner[int(time.time() * 2) % 4]
            elapsed_str = f"({int(elapsed)}s)"

            # Show progress with running task details
            running_tasks = [r for r in results if r.get("state") == "running"]
            if running_tasks:
                progress = running_tasks[0].get("extract_progress", {})
                extracted = progress.get("extracted_pages", 0)
                total_pages = progress.get("total_pages", 0)
                if total_pages > 0:
                    print(f"\r\033[KProcessing: {extracted}/{total_pages} pages ({done_count}/{total} files done) {spin_char} {elapsed_str}", end="", flush=True)
                else:
                    print(f"\r\033[KProgress: {done_count}/{total} done, {failed_count} failed {spin_char} {elapsed_str}", end="", flush=True)
            else:
                print(f"\r\033[KProgress: {done_count}/{total} done, {failed_count} failed {spin_char} {elapsed_str}", end="", flush=True)

            all_finished = all(r.get("state") in ("done", "failed") for r in results)
            if all_finished:
                print()

                # Download all completed results
                for result in results:
                    if result.get("state") == "done" and result.get("full_zip_url"):
                        file_name = result.get("file_name", "result")
                        # For single file mode, extract directly to output_dir (no nested folder)
                        if expected_stem and len(results) == 1:
                            download_result_flat(result["full_zip_url"], output_dir)
                        else:
                            download_result(result["full_zip_url"], output_dir, file_name)
                    elif result.get("state") == "failed":
                        print(color(f"  {result.get('file_name', 'Unknown')}: {result.get('err_msg', 'Failed')}", Colors.RED))

                print(color(f"\nCompleted in {format_time(elapsed)}", Colors.GREEN))
                print(f"{color('Output:', Colors.BOLD)} {output_dir}")
                return 0 if failed_count == 0 else 1

        except APIError as e:
            if isinstance(e, AuthError): raise e
            print(color(f"\n{e}", Colors.RED))

        time.sleep(5)


def print_task_status(status: Dict):
    """Print single task status."""
    state = status.get("state", "unknown")
    task_id = status.get("task_id", "")

    states_display = {
        "pending": ("Queued", Colors.YELLOW),
        "running": ("Processing", Colors.BLUE),
        "converting": ("Converting", Colors.CYAN),
        "done": ("Completed", Colors.GREEN),
        "failed": ("Failed", Colors.RED),
    }

    label, c = states_display.get(state, (state, Colors.DIM))
    print(f"Task ID: {task_id}")
    print(f"Status:  {color(label, c)}")

    if state == "running":
        progress = status.get("extract_progress", {})
        extracted = progress.get("extracted_pages", 0)
        total = progress.get("total_pages", 0)
        start_time = progress.get("start_time", "")
        if total > 0:
            print(f"Progress: {extracted}/{total} pages")
        if start_time:
            print(f"Started:  {start_time}")
    elif state == "done":
        if status.get("full_zip_url"):
            print(f"Download: {status['full_zip_url']}")
    elif state == "failed":
        print(f"Error:   {status.get('err_msg', 'Unknown error')}")


def print_batch_status(status: Dict):
    """Print batch status."""
    batch_id = status.get("batch_id", "")
    results = status.get("extract_result", [])

    print(f"Batch ID: {batch_id}")
    print(f"Files:    {len(results)}")
    print()

    for result in results:
        file_name = result.get("file_name", "Unknown")
        state = result.get("state", "unknown")

        states_display = {
            "waiting-file": ("Waiting", Colors.DIM),
            "pending": ("Queued", Colors.YELLOW),
            "running": ("Processing", Colors.BLUE),
            "converting": ("Converting", Colors.CYAN),
            "done": ("Completed", Colors.GREEN),
            "failed": ("Failed", Colors.RED),
        }

        label, c = states_display.get(state, (state, Colors.DIM))
        print(f"  {file_name}: {color(label, c)}")

        if state == "running":
            progress = result.get("extract_progress", {})
            extracted = progress.get("extracted_pages", 0)
            total = progress.get("total_pages", 0)
            if total > 0:
                print(f"    Progress: {extracted}/{total} pages")
        elif state == "failed":
            print(f"    Error: {result.get('err_msg', 'Unknown')}")


def download_result(url: str, output_dir: Path, base_name: str):
    """Download and extract result zip to a subfolder."""
    # Create temp zip file
    zip_name = Path(base_name).stem + ".zip"
    zip_path = output_dir / zip_name

    print(f"Downloading {base_name}...", end=" ", flush=True)
    if download_file(url, zip_path):
        print(color("OK", Colors.GREEN))

        # Extract to subfolder
        extract_dir = output_dir / Path(base_name).stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        print(f"Extracting...", end=" ", flush=True)
        if extract_zip(zip_path, extract_dir):
            print(color("OK", Colors.GREEN))
            # Remove zip after extraction
            zip_path.unlink()
            print(f"  Output: {extract_dir}")
        else:
            print(f"  Zip saved: {zip_path}")
    else:
        print(color("FAILED", Colors.RED))


def download_result_flat(url: str, output_dir: Path):
    """Download and extract result zip directly to output_dir (no subfolder)."""
    zip_path = output_dir / "result.zip"

    print(f"Downloading...", end=" ", flush=True)
    if download_file(url, zip_path):
        print(color("OK", Colors.GREEN))

        print(f"Extracting...", end=" ", flush=True)
        if extract_zip(zip_path, output_dir):
            print(color("OK", Colors.GREEN))
            # Remove zip after extraction
            zip_path.unlink()
        else:
            print(f"  Zip saved: {zip_path}")
    else:
        print(color("FAILED", Colors.RED))


# =============================================================================
# Main Entry Point
# =============================================================================

def print_help():
    """Print usage help."""
    help_text = f"""
{color('mineru', Colors.BOLD)} - MinerU Cloud OCR CLI

{color('Usage:', Colors.BOLD)}
  mineru <file_or_url>              Parse a local file or URL
  mineru batch <files...>           Batch parse multiple files/URLs
  mineru status <task_id>           Query task status
  mineru token [new_token]          Update API token
  mineru config                     Configure API token
  mineru diagnose                   Check service status

{color('Default Behavior:', Colors.BOLD)}
  - Waits for completion and downloads result automatically
  - Output to source file's directory with format: {{name}}_MinerU_{{timestamp}}/
  - Example: document.pdf -> document_MinerU_20260113_101500/

{color('Examples:', Colors.BOLD)}
  mineru document.pdf                         # Parse and wait (default)
  mineru document.pdf -o ~/Desktop/           # Specify output directory
  mineru document.pdf --no-wait               # Submit only, don't wait
  mineru https://example.com/doc.pdf          # Parse URL
  mineru "some text https://example.com/doc"  # Extract URL from text
  mineru batch *.pdf                          # Batch parse multiple files
  mineru status abc-123-task-id               # Check status
  mineru status abc-123 --download            # Check and download if done

{color('Options:', Colors.BOLD)}
  -o, --output <dir>     Output directory (default: source file's directory)
  -m, --model <ver>      Model: vlm (default) or pipeline
  --ocr                  Enable OCR mode
  --no-formula           Disable formula recognition
  --no-table             Disable table recognition
  -l, --lang <lang>      Language: ch (default), en, japan, korean, etc.
  --pages <range>        Page range: 1-10, 2,4-6
  --format <fmt>         Extra formats: docx,html,latex
  --no-wait              Don't wait for completion (submit only)
  --timeout <sec>        Timeout in seconds (default: 1800)

{color('Configuration:', Colors.BOLD)}
  Token from: MINERU_API_TOKEN or MINERU_API_KEY env, or config file
  Config file: ~/.config/mineru/config.json
  Get token at: https://mineru.net
"""
    print(help_text)


def cmd_postinstall():
    """Print post-installation message."""
    print(color("\n===============================================================", Colors.GREEN))
    print(color("  MinerU CLI Installed Successfully!", Colors.GREEN + Colors.BOLD))
    print(color("===============================================================", Colors.GREEN))
    print("\nTo get started, run:")
    print(f"  {color('mineru config', Colors.CYAN)}")
    print("\nOr simply run 'mineru <file>' and follow the prompts.")
    print()
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="MinerU Cloud OCR CLI",
        add_help=False
    )

    # Global options
    parser.add_argument('-h', '--help', action='store_true', help='Show help')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('-m', '--model', default='vlm', choices=['vlm', 'pipeline'], help='Model version')
    parser.add_argument('--ocr', action='store_true', help='Enable OCR mode')
    parser.add_argument('--no-formula', action='store_true', help='Disable formula recognition')
    parser.add_argument('--no-table', action='store_true', help='Disable table recognition')
    parser.add_argument('-l', '--lang', default='ch', help='Document language')
    parser.add_argument('--pages', help='Page range')
    parser.add_argument('--format', help='Extra output formats')
    parser.add_argument('--no-wait', action='store_true', dest='no_wait', help='Do not wait for completion (submit only)')
    parser.add_argument('--timeout', type=int, default=1800, help='Timeout in seconds')
    parser.add_argument('--download', action='store_true', help='Download result (for status command)')
    parser.add_argument('--show', action='store_true', help='Show current config (for config command)')
    parser.add_argument('--token', help='Set API token (for config command)')
    parser.add_argument('--postinstall', action='store_true', help=argparse.SUPPRESS)

    # Positional arguments
    parser.add_argument('command', nargs='?', help='Command or input file/URL')
    parser.add_argument('inputs', nargs='*', help='Additional inputs')

    args = parser.parse_args()

    # Handle internal postinstall flag
    if args.postinstall:
        return cmd_postinstall()

    # Show help
    if args.help or args.command is None:
        print_help()
        return 0

    # Route commands
    cmd = args.command.lower() if args.command else None

    if cmd == 'config':
        return cmd_config(args)
    elif cmd == 'token':
        return cmd_token(args)
    elif cmd == 'diagnose':
        return cmd_diagnose(args)
    elif cmd == 'status':
        if not args.inputs:
            print(color("Error: Please provide task/batch ID", Colors.RED))
            return 1
        args.task_id = args.inputs[0]
        return cmd_status(args)
    elif cmd == 'batch':
        if not args.inputs:
            print(color("Error: Please provide files or URLs to parse", Colors.RED))
            return 1
        return cmd_batch(args)
    else:
        # Default: parse single file/URL
        args.input = args.command
        return cmd_parse(args)


if __name__ == '__main__':
    sys.exit(main())