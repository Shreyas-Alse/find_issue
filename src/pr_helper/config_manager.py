import os
import stat
import sys
import getpass
import subprocess
from pathlib import Path
from dotenv import dotenv_values


def get_config_dir() -> Path:
    """Return standard config directory based on OS."""
    if sys.platform == "win32":
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base_dir / "Initial_PR_Guide"


CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "config.env"


def restrict_permissions_windows(path: Path):
    """
    Restrict file/folder access on Windows to the current user only using icacls.
    Removes inherited permissions and grants full control (F) to %USERNAME%.
    """
    username = os.environ.get("USERNAME") or getpass.getuser()
    try:
        # /inheritance:r removes inherited permissions
        # /grant:r assigns exclusive full control to the user
        subprocess.run(
            ["icacls.exe", str(path), "/inheritance:r", f"/grant:r", f"{username}:(F)"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def ensure_secure_permissions(path: Path):
    """Enforce user-only permissions cross-platform."""
    if not path.exists():
        return

    if sys.platform == "win32":
        restrict_permissions_windows(path)
    else:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def save_config(github_token: str, gemini_key: str):
    """Creates the config directory and writes credentials securely."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if sys.platform == "win32":
        restrict_permissions_windows(CONFIG_DIR)
    else:
        CONFIG_DIR.chmod(stat.S_IRWXU)  # 700 permissions

    # Open with restricted file creation flags on POSIX (umask-aware)
    if sys.platform != "win32":
        # Create fd with 0600 directly before writing
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = stat.S_IRUSR | stat.S_IWUSR
        with os.fdopen(os.open(CONFIG_FILE, flags, mode), "w", encoding="utf-8") as f:
            f.write(f"GITHUB_TOKEN={github_token.strip()}\n")
            f.write(f"GEMINI_API_KEY={gemini_key.strip()}\n")
    else:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(f"GITHUB_TOKEN={github_token.strip()}\n")
            f.write(f"GEMINI_API_KEY={gemini_key.strip()}\n")
        restrict_permissions_windows(CONFIG_FILE)

    print(f"Credentials saved securely to: {CONFIG_FILE}")


def get_credentials() -> tuple[str, str]:
    """
    Resolves GitHub Token and Gemini API Key using the priority chain:
    Environment -> config.env -> Interactive Prompt
    """
    gh_token = os.environ.get("GITHUB_TOKEN")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if (not gh_token or not gemini_key) and CONFIG_FILE.exists():
        ensure_secure_permissions(CONFIG_FILE)
        stored_env = dotenv_values(CONFIG_FILE)
        gh_token = gh_token or stored_env.get("GITHUB_TOKEN")
        gemini_key = gemini_key or stored_env.get("GEMINI_API_KEY")

    needs_save = False
    if not gh_token:
        print("\n[Setup Required] GitHub Personal Access Token not found.")
        gh_token = getpass.getpass("Enter your GitHub Token (hidden): ").strip()
        needs_save = True

    if not gemini_key:
        print("\n[Setup Required] Gemini API Key not found.")
        gemini_key = getpass.getpass("Enter your Gemini API Key (hidden): ").strip()
        needs_save = True

    if needs_save:
        prompt_path = CONFIG_FILE
        choice = input(f"\nSave these tokens to {prompt_path} for future use? [Y/n]: ").strip().lower()
        if choice in ("", "y", "yes"):
            save_config(gh_token, gemini_key)

    os.environ["GITHUB_TOKEN"] = gh_token or ""
    os.environ["GEMINI_API_KEY"] = gemini_key or ""

    return gh_token or "", gemini_key or ""