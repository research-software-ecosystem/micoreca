import shutil
import subprocess
import sys
from pathlib import Path

# --- Configuration paths ---

# 1. Define the script path (independent of the execution directory)
SCRIPT_PATH = Path(__file__).resolve()
# 2. Define the BIN directory (script's parent)
SCRIPT_BIN_DIR = SCRIPT_PATH.parent

# 3. BASE_DIR is the micoreca repository root (parent directory of 'bin')
# This ensures that BASE_DIR is the repository root, regardless of where the script is executed.
BASE_DIR = SCRIPT_BIN_DIR.parent

# The target directory that should contain the tools (micoreca/content/rsec)
RSEC_DIR = BASE_DIR / "content" / "rsec"

# The parent directory for the tools (micoreca/content)
CONTENT_DIR = BASE_DIR / "content"

# URL of the RSEC repository (we need to clone it to get the 'data' subdirectory)
RSEC_REPO_URL = "https://github.com/research-software-ecosystem/content.git"

# The path of the subdirectory in the remote repository that we want
TARGET_SUBDIR_IN_REPO = "data"

# Temporary directory for cloning
TEMP_CLONE_DIR = BASE_DIR / "temp_rsec_clone"

# --- Functions ---


def run_command(command: list[str], cwd: Path | None = None) -> bool:
    """Executes a shell command and handles errors."""
    try:
        cwd_display = cwd.name if cwd else "CWD"
        print(f"Executing: {' '.join(command)} (in directory: {cwd_display})")
        # Use capture_output and text=True for better log management
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,  # Raises an exception if the return code is non-zero
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.stdout and result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr and result.stderr.strip():
            print(result.stderr.strip())
        print("... Success.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Command failed (Return Code {e.returncode}): {' '.join(command)}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"\n[ERROR] Command '{command[0]}' not found. Is Git installed?")
        return False


def clone_rsec_data():
    """Deletes the old folder and clones the TARGET_SUBDIR_IN_REPO subdirectory into RSEC_DIR."""

    # NOTE: Executing git commands requires the CWD to be correct for relative paths.
    # We use BASE_DIR as CWD for the git clone command.

    print("=" * 60)
    print(f"Preparing to re-clone RSEC/data to {RSEC_DIR.relative_to(BASE_DIR)}/")
    print(f"Project Root (BASE_DIR) set to: {BASE_DIR.name}/")
    print("=" * 60)

    # 1. Cleanup old temporary working directory
    if TEMP_CLONE_DIR.exists():
        print(f"Cleaning up existing temporary directory: {TEMP_CLONE_DIR.name}/")
        shutil.rmtree(TEMP_CLONE_DIR)

    # 2. Cleanup old RSEC_DIR (the filtered folder)
    if RSEC_DIR.exists():
        print(f"🗑️ Deleting old filtered folder: {RSEC_DIR.relative_to(BASE_DIR)}/")
        shutil.rmtree(RSEC_DIR)

    # Ensure the parent directory exists (micoreca/content/)
    CONTENT_DIR.mkdir(exist_ok=True, parents=True)

    # --- Sparse Checkout cloning process (to fetch only 'data') ---

    # 3. Clone to the repository root (without initial checkout)
    print("\n--- Step 1/4: Initial cloning of the repository without checkout ---")
    # We clone into TEMP_CLONE_DIR.name (folder name) using BASE_DIR as CWD
    command = [
        "git",
        "clone",
        "--depth",
        "1",
        "--no-checkout",
        RSEC_REPO_URL,
        TEMP_CLONE_DIR.name,
    ]
    if not run_command(command, cwd=BASE_DIR):
        print("[CRITICAL] Initial cloning failed.")
        return False

    # 4. Enable Sparse-Checkout
    print("\n--- Step 2/4: Enabling Sparse-Checkout ---")
    command = ["git", "config", "core.sparseCheckout", "true"]
    if not run_command(command, cwd=TEMP_CLONE_DIR):
        return False

    # 5. Define the path to extract (here, the 'data' folder)
    print("\n--- Step 3/4: Defining the path to extract (data/) ---")
    sparse_checkout_file = TEMP_CLONE_DIR / ".git" / "info" / "sparse-checkout"
    try:
        with open(sparse_checkout_file, "w", encoding="utf-8") as f:
            f.write(f"/{TARGET_SUBDIR_IN_REPO}\n")
    except Exception as e:
        print(f"[ERROR] Failed to write sparse-checkout file: {e}")
        return False

    # 6. Checkout files (fetches only 'data/')
    print("\n--- Step 4/4: Extracting targeted files (checkout) ---")
    command = ["git", "checkout"]
    if not run_command(command, cwd=TEMP_CLONE_DIR):
        return False

    # 7. Rename and move
    print("\n--- Finalization: Moving the folder ---")

    # The 'data' folder is now inside TEMP_CLONE_DIR
    source_dir = TEMP_CLONE_DIR / TARGET_SUBDIR_IN_REPO

    if source_dir.is_dir():
        # Move the 'data' folder to 'content/rsec'
        # RSEC_DIR is micoreca/content/rsec
        shutil.move(source_dir, RSEC_DIR)
        print(f" Move complete: {source_dir.name}/ -> {RSEC_DIR.relative_to(BASE_DIR)}/")

        # Final cleanup of the temporary directory
        shutil.rmtree(TEMP_CLONE_DIR)
        print(f"Cleanup of temporary directory {TEMP_CLONE_DIR.name}/ performed.")

        return True
    else:
        print(f"[CRITICAL] Target subdirectory '{TARGET_SUBDIR_IN_REPO}' not found after cloning.")
        return False


# --- Main execution ---

if __name__ == "__main__":

    # Check for the existence of the parent directory
    if not CONTENT_DIR.is_dir():
        print(f"WARNING: Parent directory '{CONTENT_DIR.name}/' does not exist. Creating it now.")
        CONTENT_DIR.mkdir(parents=True, exist_ok=True)

    # Start the cloning operation
    success = clone_rsec_data()

    if success:
        print("\n" + "#" * 60)
        print("CLONING AND PREPARATION COMPLETED SUCCESSFULLY!")
        print(f"The directory {RSEC_DIR.relative_to(BASE_DIR)}/ is ready for filtering.")
        print("#" * 60)

    else:
        print("\n" + "!" * 60)
        print("CLONING FAILED. Please check the error messages above.")
        print("!" * 60)
        sys.exit(1)
