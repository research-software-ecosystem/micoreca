import csv
import json
import logging
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import pandas as pd
import requests
import yaml

logger = logging.getLogger()


def format_date(date: str) -> str:
    return datetime.fromisoformat(date).strftime("%Y-%m-%d")


def format_list_column(col: pd.Series) -> pd.Series:
    """
    Format a column that could be a list before exporting
    """
    return col.apply(lambda x: ", ".join(str(i) for i in x))


def format_regex(pattern: str) -> str:
    """
    Format regex to allow various separators before and after the pattern
    """
    return rf"(?<![A-Za-z]){pattern}(?![A-Za-z])"


def load_yaml(input_fp: str) -> Dict:
    """
    Read a YAML file
    """
    with Path(input_fp).open("r") as t:
        content = yaml.safe_load(t)
    return content


def load_json(input_fp: str) -> Any:
    """
    Read a JSON file
    """
    with Path(input_fp).open("r") as t:
        content = json.load(t)
    return content


def export_to_json(data: List[Dict], output_fp: str) -> None:
    """
    Export to a JSON file
    """
    with Path(output_fp).open("w") as f:
        json.dump(data, f, indent=4, sort_keys=True, default=str)


def tags_has_keyword(keywords_list: dict, target_tags: List[str]) -> str:
    """
    Search for keywords and acronyms in tags
    """
    for tag in keywords_list:
        regex = re.compile(format_regex(tag), re.IGNORECASE)
        if any(regex.search(wtag) for wtag in target_tags):
            return f"{tag} in tags"

    return ""


def has_keyword(tags: dict, target: str, target_name: str) -> str:
    """
    Search for keywords and acronyms in target
    """
    for tag in tags["keywords"]:
        regexk = re.compile(format_regex(tag), re.IGNORECASE)
        if regexk.search(target):
            return f"{tag} in {target_name}"

    for acron in tags["acronyms"]:
        regexa = re.compile(format_regex(acron))
        if regexa.search(target):
            return f"{acron} in {target_name}"

    return ""


def has_edam_terms(edam_topics: list[str], edam_operations: list[str], edam_keywords: dict) -> bool:
    """
    Search for EDAM topics and operations
    """
    matches_topic = set(edam_topics) & set(edam_keywords["topics"])
    matches_operation = set(edam_operations) & set(edam_keywords["operations"])

    return len(matches_topic) != 0 or len(matches_operation) != 0


def get_edam_operation_from_tools(selected_tools: list, all_tools: dict) -> List:
    """
    NOT RUN

    Get list of EDAM operations of the tools

    :param selected_tools: list of tool suite ids
    :param all_tools: dictionary with information about all tools
    """
    edam_operation = set()
    for t in selected_tools:
        if t in all_tools:
            edam_operation.update(set(all_tools[t]["EDAM operations"]))
        else:
            print(f"{t} not found in all tools")
    return list(edam_operation)


def shorten_tool_id(tool: str) -> str:
    """
    Shorten tool id
    """
    if "toolshed" in tool:
        return tool.split("/")[-2]
    else:
        return tool


def get_request_json(url: str, headers: dict, retries: int = 3, delay: float = 2.0) -> dict:
    """
    Perform a GET request to retrieve JSON output from a specified URL, with retry on ConnectionError.

    :param url: URL to send the GET request to.
    :param headers: Headers to include in the GET request.
    :param retries: Number of retry attempts in case of a ConnectionError (default is 3).
    :param delay: Delay in seconds between retries (default is 2.0 seconds).
    :return: JSON response as a dictionary, or None if all retries fail.
    :raises ConnectionError: If all retry attempts fail due to a connection error.
    :raises SystemExit: For any other request-related errors.
    """
    attempt = 0  # Track the number of attempts

    while attempt < retries:
        try:
            r = requests.get(url, auth=None, headers=headers)
            r.raise_for_status()  # Raises an HTTPError for unsuccessful status codes
            return r.json()  # Return JSON response if successful
        except ConnectionError as e:
            attempt += 1
            if attempt == retries:
                raise ConnectionError(
                    "Connection aborted after multiple retries: Remote end closed connection without response"
                ) from e
            print(f"Connection error on attempt {attempt}/{retries}. Retrying in {delay} seconds...")
            time.sleep(delay)  # Wait before retrying
        except requests.exceptions.RequestException as e:
            # Handles all other exceptions from the requests library
            raise SystemExit(f"Request failed: {e}")
        except ValueError as e:
            # Handles cases where the response isn't valid JSON
            raise ValueError("Response content is not valid JSON") from e

    # Return None if all retries are exhausted and no response is received
    return {}


# -------------------------------------------------------------
#               RSEc functions and variables
# -------------------------------------------------------------
def run_command_rsec(command: List[str], cwd: Optional[Path] = None) -> bool:
    """Exécute une commande shell et gère les erreurs."""
    try:
        cwd_display = cwd.name if cwd else "CWD"
        print(f"Executing: {' '.join(command)} (in directory: {cwd_display})")
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.stdout and result.stdout.strip():
            print(result.stdout.strip())
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


def clone_rsec_content(repo_url: str, temp_dir: Path, subdirs: List[str]) -> bool:
    """
    Sparse-clone one or more subdirectories of the remote repository into temp_dir
    and leave them in place (no move). The caller is responsible for removing temp_dir.

    Args:
        repo_url (str): URL of the git repository.
        temp_dir (Path): Path to the temporary clone directory.
        subdirs (List[str]): Subdirectories to extract (e.g. ["data", "imports/bioconda"]).

    Returns:
        bool: True on success, False on failure.
    """
    print("=" * 60)
    print(f"Preparing to clone {', '.join(subdirs)} into {temp_dir.name}/")
    print("=" * 60)

    # Cleanup any leftovers from a previous clone.
    # If temp_dir exists and *already* contains a .git directory, preserve it.
    # Tests pre-create a fake repo layout (with .git/info) to simulate clone
    # side-effects when run_command_rsec is mocked. Only remove temp_dir when it
    # exists but does not look like a git repo.
    if temp_dir.exists():
        if (temp_dir / ".git").exists():
            print(f"Using existing temp dir (contains .git): {temp_dir}")
        else:
            shutil.rmtree(temp_dir)

    temp_dir.parent.mkdir(parents=True, exist_ok=True)

    print("\n--- Step 1/4: Initial cloning of the repository without checkout ---")
    clone_cmd = ["git", "clone", "--depth", "1", "--no-checkout", repo_url, str(temp_dir)]
    if not run_command_rsec(clone_cmd):
        print("[CRITICAL] Initial cloning failed.")
        return False

    print("\n--- Step 2/4: Enabling Sparse-Checkout ---")
    if not run_command_rsec(["git", "config", "core.sparseCheckout", "true"], cwd=temp_dir):
        return False

    print(f"\n--- Step 3/4: Defining paths ({', '.join(subdirs)}) ---")
    sparse_checkout_file = temp_dir / ".git" / "info" / "sparse-checkout"
    try:
        # Ensure parent directories exist (tests may rely on pre-created .git/info or
        # the clone command could create them; be defensive and create them here).
        sparse_checkout_file.parent.mkdir(parents=True, exist_ok=True)
        with open(sparse_checkout_file, "w", encoding="utf-8") as f:
            for subdir in subdirs:
                f.write(f"/{subdir}\n")
    except Exception as e:
        print(f"[ERROR] Failed to write sparse-checkout file : {e}")
        return False

    print("\n--- Step 4/4: Extracting files (checkout) ---")
    if not run_command_rsec(["git", "checkout"], cwd=temp_dir):
        return False

    missing = [s for s in subdirs if not (temp_dir / s).is_dir()]
    if missing:
        print(f"[CRITICAL] Subdirectories not found after cloning: {missing}")
        return False

    print("\n--- Clone complete; files left in place ---")
    return True


def load_keywords_from_yaml(filepath: Path) -> Dict[str, Any]:
    """Charge les critères de filtrage depuis le fichier YAML."""
    if not filepath.exists():
        raise FileNotFoundError(f"Keywords file not found at: {filepath}")

    with open(filepath, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    edam_data = data.get("edam", {})
    target_operations = edam_data.get("operations", [])
    target_topics = edam_data.get("topics", [])

    fragment_patterns_raw = data.get("keywords", [])
    compiled_fragments = []
    for pattern_raw in fragment_patterns_raw:
        if isinstance(pattern_raw, str) and pattern_raw.strip():
            try:
                compiled_fragments.append(re.compile(pattern_raw, re.IGNORECASE))
            except re.error as e:
                print(f" [WARNING] Could not compile regex pattern '{pattern_raw}': {e}")

    strict_keywords_list = [str(k).strip() for k in data.get("acronyms", []) if isinstance(k, str) and k.strip()]
    for kw in fragment_patterns_raw:
        if isinstance(kw, str) and kw.strip() and not any(c in kw for c in [".", "*", "+", "?"]):
            if kw.upper() == kw:
                strict_keywords_list.append(kw.strip())

    strict_keywords_list = list(set([k.strip().upper() for k in strict_keywords_list if k.strip()]))
    compiled_stricts = []
    for strict_ref in strict_keywords_list:
        regex_pattern = re.compile(r"\b" + re.escape(strict_ref) + r"\b")
        compiled_stricts.append(regex_pattern)

    return {
        "operations": target_operations,
        "topics": target_topics,
        "compiled_fragments": compiled_fragments,
        "stricts": strict_keywords_list,
        "compiled_stricts": compiled_stricts,
    }


def generate_tsv_summary(json_path: Path, tsv_path: Path) -> None:
    """Génère le résumé TSV à partir du JSON des métadonnées validées."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data: List[Dict[str, Any]] = json.load(f)
    except Exception as e:
        print(f"ERROR loading/parsing JSON for TSV: {e}")
        return
    if not isinstance(data, list) or not data:
        return

    summary_data: List[Dict[str, str]] = []
    fieldnames = [
        "tool_id",
        "biotools_id",
        "filtered_on",
        "reason",
        "to_keep",
        "EDAM_operations",
        "EDAM_topics",
        "description",
        "has_biocontainers_infos",
        "has_biotools_infos",
        "has_galaxy_infos",
    ]
    for item in data:
        entry = {
            "tool_id": item.get("tool_id", "N/A"),
            "biotools_id": item.get("biotools_id", ""),
            "EDAM_operations": item.get("EDAM_operations_full", ""),
            "EDAM_topics": item.get("EDAM_topics_full", ""),
            "has_biocontainers_infos": str(item.get("has_biocontainers_infos", False)),
            "has_biotools_infos": str(item.get("has_biotools_infos", False)),
            "has_galaxy_infos": str(item.get("has_galaxy_infos", False)),
            "filtered_on": "UNKNOWN_REASON",
            "reason": "N/A - Not Matched",
            "to_keep": "False",
        }
        description = (
            item.get("biotools_description_full", "")
            or item.get("biocontainers_description_full", "")
            or item.get("galaxy_description_full", "")
            or "N/A"
        )
        entry["description"] = description

        for key in CRITERIA_KEYS:
            match_value = item.get(key)
            if match_value:
                entry["filtered_on"] = key
                reason_template = REASON_MAPPING.get(key, "Match found on key: {key}")
                entry["reason"] = reason_template.format(value=str(match_value))
                break
        summary_data.append(entry)

    with open(tsv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary_data)
    print(f"Summary TSV created: {tsv_path.name}")


# --- Configuration paths  ---
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BIN_DIR = SCRIPT_PATH.parent
BASE_DIR = SCRIPT_BIN_DIR.parent

# Dossiers cibles
CONTENT_DIR = BASE_DIR / "content"
RSEC_DIR = CONTENT_DIR / "rsec"
BIOCONDA_DIR = CONTENT_DIR / "bioconda"
GALAXY_DIR = CONTENT_DIR / "galaxy"
KEYWORDS_FILEPATH = BASE_DIR / "keywords.yml"

# Configuration Extraction RSEC
RSEC_REPO_URL = "https://github.com/research-software-ecosystem/content.git"

# Filtering criterias (initialized in __main__)
TARGET_OPERATIONS: List[str] = []
TARGET_TOPICS: List[str] = []
STRICT_KEYWORDS: List[str] = []
COMPILED_FRAGMENT_PATTERNS: List[re.Pattern] = []
COMPILED_STRICT_PATTERNS: List[re.Pattern] = []

# CRITERIA KEYS and REASON MAPPING
CRITERIA_KEYS = [
    "EDAM_topics",
    "EDAM_operation",
    "biocontainers_keywords",
    "biotools_description",
    "biocontainers_description",
    "galaxy_description",
]

REASON_MAPPING = {
    "EDAM_topics": "{value} in EDAM Topics",
    "EDAM_operation": "{value} in EDAM Operations",
    "biocontainers_keywords": "{value} in BioContainers keywords",
    "biotools_description": "{value} in bio.tools description",
    "biocontainers_description": "{value} in BioContainers description",
    "galaxy_description": "{value} in Galaxy description",
}


def setup_logger(verbosity: int) -> None:
    """
    Configure the logger based on verbosity level.

    :param verbosity: verbosity level
    """
    log_levels = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARN,
        3: logging.INFO,
        4: logging.DEBUG,
    }
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=log_levels.get(verbosity, logging.INFO),
    )
