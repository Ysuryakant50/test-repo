from pathlib import Path
import os

import requests
from dotenv import load_dotenv
from fastmcp import FastMCP

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
PROJECT_ROOT = os.getenv("PROJECT_ROOT", str(ROOT_DIR)).strip()

required_env = {
    "GITHUB_TOKEN": GITHUB_TOKEN,
    "GITHUB_OWNER": GITHUB_OWNER,
    "GITHUB_REPO": GITHUB_REPO,
    "PROJECT_ROOT": PROJECT_ROOT,
}

missing = [key for key, value in required_env.items() if not value]
if missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(missing)}"
    )

PROJECT_ROOT = Path(PROJECT_ROOT).expanduser().resolve()
PROJECT_ROOT.mkdir(parents=True, exist_ok=True)

session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
)

mcp = FastMCP(name="GitHub Development Agent")


def get_project_path(relative_path: str) -> Path:
    """Resolve a workspace-relative path and keep it inside PROJECT_ROOT."""
    if not relative_path or not relative_path.strip():
        raise ValueError("Path cannot be empty.")

    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError("Absolute paths are not allowed.")

    target = (PROJECT_ROOT / candidate).resolve()
    try:
        target.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Operation outside PROJECT_ROOT is not allowed.") from exc

    return target


def github_request(method: str, endpoint: str, **kwargs):
    """Wrap a GitHub REST API request."""
    url = f"https://api.github.com{endpoint}"
    response = session.request(method=method, url=url, **kwargs)
    if response.status_code >= 400:
        raise Exception(f"GitHub API Error {response.status_code}: {response.text}")
    return response.json() if response.text else None


@mcp.tool(
    name="create",
    description="Create a new file or directory inside the current workspace.",
)
def create(path: str, item_type: str = "file") -> str:
    """Create a file or directory inside the workspace."""
    try:
        target = get_project_path(path)
        if item_type.lower() == "directory":
            if target.exists():
                return f"Directory already exists: {path}"
            target.mkdir(parents=True, exist_ok=False)
            return f"Directory created successfully: {path}"
        if item_type.lower() == "file":
            if target.exists():
                return f"File already exists: {path}"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            return f"File created successfully: {path}"
        return "item_type must be either 'file' or 'directory'."
    except ValueError as exc:
        return str(exc)
    except PermissionError:
        return "Permission denied."
    except Exception as exc:
        return f"Unexpected error: {exc}"


@mcp.tool(
    name="read_file",
    description="Read the contents of a file from the workspace.",
)
def read_file(path: str) -> str:
    """Read a workspace-relative file and return its contents."""
    target = get_project_path(path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    return target.read_text(encoding="utf-8")


@mcp.tool(
    name="write_file",
    description="Write or overwrite a file inside the workspace.",
)
def write_file(path: str, content: str) -> str:
    """Write content to a workspace-relative file."""
    target = get_project_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"File written successfully: {path}"


@mcp.tool(
    name="list_directory",
    description="List files and directories within a workspace folder.",
)
def list_directory(path: str = ".") -> list[str]:
    """List the contents of a workspace-relative directory."""
    target = get_project_path(path)
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(f"Directory not found: {path}")
    return sorted([child.name for child in target.iterdir()])


@mcp.tool(
    name="get_repo_info",
    description="Fetch basic repository metadata from GitHub.",
)
def get_repo_info() -> dict:
    """Return repository metadata for the configured GitHub repository."""
    return github_request("GET", f"/repos/{GITHUB_OWNER}/{GITHUB_REPO}")


if __name__ == "__main__":
    print("Starting GitHub Development Agent...")
    mcp.run()