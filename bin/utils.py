import json
import re
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import yaml
import subprocess
from typing import (
    Any,
    Dict,
    List,
    Optional,
)
import shutil


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


def load_yaml(input_df: str) -> Dict:
    """
    Read a YAML file
    """
    with Path(input_df).open("r") as t:
        content = yaml.safe_load(t)
    return content


def load_json(input_df: str) -> Any:
    """
    Read a JSON file
    """
    with Path(input_df).open("r") as t:
        content = json.load(t)
    return content


def has_keyword(tags: dict, target: str, target_name: str) -> str:
    for tag in tags["keywords"]:
        regexk = re.compile(format_regex(tag), re.IGNORECASE)
        if regexk.search(target):
            return f"{tag} in {target_name}"

    for acron in tags["acronyms"]:
        regexa = re.compile(format_regex(acron))
        if regexa.search(target):
            return f"{acron} in {target_name}"

    return ""


def export_to_json(data: List[Dict], output_fp: str) -> None:
    """
    Export to a JSON file
    """
    with Path(output_fp).open("w") as f:
        json.dump(data, f, indent=4, sort_keys=True)


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
#               RSEc functions
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


def clone_rsec_data(repo_url: str, temp_dir: Path, target_dir: Path, subdir_in_repo: str = "data") -> bool:
    """
    Clone a remote repository and move a specific subdirectory to its final destination.
    Uses sparse-checkout to retrieve only the required path.

    Args:
        repo_url (str): URL of the git repository.
        temp_dir (Path): Path to the temporary clone directory.
        target_dir (Path): Final destination path for the extracted content (e.g. content/rsec).
        subdir_in_repo (str): Subdirectory to extract from the repository (default: 'data').

    Returns:
        bool: True on success, False on failure.
    """
    print("=" * 60)
    print(f"Preparing to clone {subdir_in_repo} to {target_dir.name}/")
    print("=" * 60)

    # 1. Cleanup any leftovers from a previous clone
    if temp_dir.exists():
        shutil.rmtree(temp_dir)

    # 2. Clean up the target directory if it already exists
    if target_dir.exists():
        print(f"Cleaning up old filtered folder : {target_dir.name}/")
        shutil.rmtree(target_dir)

    # 3. Create parent directory if necessary
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # 4. Initial cloning (Sparse Checkout)
    print("\n--- Step 1/4: Initial cloning of the repository without checkout ---")
    # Clone in temp dir (absolute path)
    clone_cmd = ["git", "clone", "--depth", "1", "--no-checkout", repo_url, str(temp_dir)]
    if not run_command_rsec(clone_cmd):
        print("[CRITICAL] Initial cloning failed.")
        return False

    print("\n--- Step 2/4: Enabling Sparse-Checkout ---")
    if not run_command_rsec(["git", "config", "core.sparseCheckout", "true"], cwd=temp_dir):
        return False

    print(f"\n--- Step 3/4: Defining path ({subdir_in_repo}/) ---")
    sparse_checkout_file = temp_dir / ".git" / "info" / "sparse-checkout"
    try:
        with open(sparse_checkout_file, "w", encoding="utf-8") as f:
            f.write(f"/{subdir_in_repo}\n")
    except Exception as e:
        print(f"[ERROR] Failed to write sparse-checkout file : {e}")
        return False

    print("\n--- Step 4/4: Extracting files (checkout) ---")
    if not run_command_rsec(["git", "checkout"], cwd=temp_dir):
        return False

    print("\n--- Finalization : Moving the folder ---")
    source_dir = temp_dir / subdir_in_repo

    if source_dir.is_dir():
        shutil.move(str(source_dir), str(target_dir))
        print(f"Move complete: {source_dir.name}/ -> {target_dir.name}/")

        # Nettoyage final
        shutil.rmtree(temp_dir)
        print(f"Cleanup of temporary directory  {temp_dir.name} performed.")
        return True
    else:
        print(f"[CRITICAL] Target subdirectory '{subdir_in_repo}' is not found after cloning.")
        return False


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
            "to_keep": "True",
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
