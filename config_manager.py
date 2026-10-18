import os
import stat
import getpass
from pathlib import Path
from dotenv import dotenv_values

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "hacktober"
CONFIG_FILE = CONFIG_DIR / "config.env"


def ensure_secure_permissions(path: Path):
    """Enforce rw------- (600) permissions on the config file."""
    if path.exists():
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def save_config(github_token: str, gemini_key: str):
    """Creates the config directory and writes credentials securely."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(stat.S_IRWXU)  # 700 permissions

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(f"GITHUB_TOKEN={github_token.strip()}\n")
        f.write(f"GEMINI_API_KEY={gemini_key.strip()}\n")

    ensure_secure_permissions(CONFIG_FILE)
    print(f"Credentials saved securely to: {CONFIG_FILE}")


def get_credentials() -> tuple[str, str]:
    """
    Resolves GitHub Token and Gemini API Key using the priority chain:
    Environment -> ~/.config/hacktober/config.env -> Interactive Prompt
    """
    gh_token = os.environ.get("GITHUB_TOKEN")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    # Fallback to ~/.config/hacktober/config.env
    if (not gh_token or not gemini_key) and CONFIG_FILE.exists():
        ensure_secure_permissions(CONFIG_FILE)
        stored_env = dotenv_values(CONFIG_FILE)
        gh_token = gh_token or stored_env.get("GITHUB_TOKEN")
        gemini_key = gemini_key or stored_env.get("GEMINI_API_KEY")

    # If still missing, prompt the user interactively
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
        choice = input("\nSave these tokens to ~/.config/hacktober/config.env for future use? [Y/n]: ").strip().lower()
        if choice in ("", "y", "yes"):
            save_config(gh_token, gemini_key)

    # Set in os.environ for libraries that auto-detect them (like langchain-google-genai)
    os.environ["GITHUB_TOKEN"] = gh_token
    os.environ["GEMINI_API_KEY"] = gemini_key

    return gh_token, gemini_key