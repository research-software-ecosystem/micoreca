#!/usr/bin/env python
import csv
import json
import re
import shutil
import sys
import time
import subprocess
import yaml
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

# --- Configuration paths  ---
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BIN_DIR = SCRIPT_PATH.parent
BASE_DIR = SCRIPT_BIN_DIR.parent

# Dossiers cibles
CONTENT_DIR = BASE_DIR / "content"
RSEC_DIR = CONTENT_DIR / "rsec"
KEYWORDS_FILEPATH = BASE_DIR / "keywords.yml"

# Configuration Extraction RSEC
RSEC_REPO_URL = "https://github.com/research-software-ecosystem/content.git"
TARGET_SUBDIR_IN_REPO = "data"
TEMP_CLONE_DIR = BASE_DIR / "temp_rsec_clone"

# Global variables (initialized in __main__)
ROOT_DIRECTORY: Path
OUTPUT_DIR: Path
REPORTING_FILE: Path
VALIDATED_METADATA_FILE: Path
FAILED_METADATA_FILE: Path
TSV_OUTPUT_FILE: Path

METADATA_FILE_PATTERN = "*biotools.json"

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

# -------------------------------------------------------------
#               FONCTIONS D'EXTRACTION (ex extract_rsec.py)
# -------------------------------------------------------------


def run_command(command: List[str], cwd: Optional[Path] = None) -> bool:
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


def clone_rsec_data() -> bool:
    """Nettoie et clone le sous-répertoire 'data' de RSEC dans RSEC_DIR."""
    print("=" * 60)
    print(f"Preparing to re-clone RSEC/data to {RSEC_DIR.relative_to(BASE_DIR)}/")
    print("=" * 60)

    if TEMP_CLONE_DIR.exists():
        shutil.rmtree(TEMP_CLONE_DIR)

    if RSEC_DIR.exists():
        print(f"🗑️ Deleting old filtered folder: {RSEC_DIR.relative_to(BASE_DIR)}/")
        shutil.rmtree(RSEC_DIR)

    CONTENT_DIR.mkdir(exist_ok=True, parents=True)

    # Sparse Checkout
    print("\n--- Step 1/4: Initial cloning (no-checkout) ---")
    command = ["git", "clone", "--depth", "1", "--no-checkout", RSEC_REPO_URL, TEMP_CLONE_DIR.name]
    if not run_command(command, cwd=BASE_DIR):
        return False

    print("\n--- Step 2/4: Enabling Sparse-Checkout ---")
    if not run_command(["git", "config", "core.sparseCheckout", "true"], cwd=TEMP_CLONE_DIR):
        return False

    print("\n--- Step 3/4: Defining path (data/) ---")
    sparse_checkout_file = TEMP_CLONE_DIR / ".git" / "info" / "sparse-checkout"
    try:
        with open(sparse_checkout_file, "w", encoding="utf-8") as f:
            f.write(f"/{TARGET_SUBDIR_IN_REPO}\n")
    except Exception as e:
        print(f"[ERROR] Failed to write sparse-checkout file: {e}")
        return False

    print("\n--- Step 4/4: Checkout targeted files ---")
    if not run_command(["git", "checkout"], cwd=TEMP_CLONE_DIR):
        return False

    print("\n--- Finalization: Moving the folder ---")
    source_dir = TEMP_CLONE_DIR / TARGET_SUBDIR_IN_REPO
    if source_dir.is_dir():
        shutil.move(source_dir, RSEC_DIR)
        shutil.rmtree(TEMP_CLONE_DIR)
        print(f"Move complete: {source_dir.name}/ -> {RSEC_DIR.relative_to(BASE_DIR)}/")
        return True
    else:
        print(f"[CRITICAL] Target subdirectory '{TARGET_SUBDIR_IN_REPO}' not found.")
        return False


# -------------------------------------------------------------
#               FONCTIONS DE FILTRAGE (ex filter_rsec.py)
# -------------------------------------------------------------


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


class Tool:
    def __init__(self, folder_path: Path):
        self.folder_path = folder_path
        self.tool_id = folder_path.name
        self.keep = False
        self.validation_data: Dict[str, Any] = {"tool_id": self.tool_id}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.descriptions: Dict[str, str] = {}
        self._load_all_metadata_optimized()
        self._store_full_report_metadata()

    def _safe_load(self, filepath: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(filepath, encoding="utf-8") as fh:
                if filepath.suffix == ".json":
                    return json.load(fh)
                elif filepath.suffix == ".yaml":
                    return yaml.safe_load(fh)
        except Exception:
            pass
        return None

    def _load_all_metadata_optimized(self) -> None:
        self.validation_data.update(
            {
                "has_biocontainers_infos": False,
                "has_biotools_infos": False,
                "has_galaxy_infos": False,
                "biotools_description_full": "",
                "biocontainers_description_full": "",
                "galaxy_description_full": "",
            }
        )

        for path in self.folder_path.glob("*biotools.json"):
            data = self._safe_load(path)
            if data:
                self.metadata["biotools"] = data
                desc = data.get("description", "")
                self.descriptions["biotools"] = desc
                self.validation_data["has_biotools_infos"] = True
                self.validation_data["biotools_description_full"] = desc
                break
        for path in self.folder_path.glob("*.biocontainers.yaml"):
            data = self._safe_load(path)
            if data:
                self.metadata["biocontainers"] = data
                desc = data.get("description", "")
                self.descriptions["biocontainers"] = desc
                self.validation_data["has_biocontainers_infos"] = True
                self.validation_data["biocontainers_description_full"] = desc
                break
        for path in self.folder_path.glob("*.galaxy.json"):
            data = self._safe_load(path)
            if data:
                self.metadata["galaxy"] = data
                desc = data.get("description", "")
                self.descriptions["galaxy"] = desc
                self.validation_data["has_galaxy_infos"] = True
                self.validation_data["galaxy_description_full"] = desc
                break

    def _extract_edam_terms(self, data: Dict[str, Any], key: str) -> str:
        terms = set()
        if key == "function" and "function" in data and isinstance(data["function"], list):
            for func in data["function"]:
                if "operation" in func and isinstance(func["operation"], list):
                    for op in func["operation"]:
                        if "term" in op:
                            terms.add(op["term"])
        elif key == "topic" and "topic" in data and isinstance(data["topic"], list):
            for topic in data["topic"]:
                if "term" in topic:
                    terms.add(topic["term"])
        return ", ".join(sorted(list(terms)))

    def _store_full_report_metadata(self) -> None:
        data = self.metadata.get("biotools")
        self.validation_data["biotools_id"] = data.get("biotoolsID", "") if data else ""
        self.validation_data["EDAM_operations_full"] = self._extract_edam_terms(data, "function") if data else ""
        self.validation_data["EDAM_topics_full"] = self._extract_edam_terms(data, "topic") if data else ""

    def check_criteria_1(self) -> bool:
        data = self.metadata.get("biotools")
        if not data:
            return False
        if "topic" in data and isinstance(data["topic"], list):
            for topic in data["topic"]:
                if "term" in topic and topic["term"] in TARGET_TOPICS:
                    self.validation_data["EDAM_topics"] = topic["term"]
                    return True
        if "function" in data and isinstance(data["function"], list):
            for func in data["function"]:
                if "operation" in func and isinstance(func["operation"], list):
                    for op in func["operation"]:
                        if "term" in op and op["term"] in TARGET_OPERATIONS:
                            self.validation_data["EDAM_operation"] = op["term"]
                            return True
        return False

    def check_criteria_2(self) -> bool:
        data = self.metadata.get("biocontainers")
        if not data:
            return False
        file_keywords = data.get("keywords", [])
        if isinstance(file_keywords, str):
            file_keywords = [x.strip() for x in file_keywords.replace(";", ",").split(",") if x.strip()]

        for kw in file_keywords:
            kw_s = str(kw).strip()
            if kw_s.upper() in STRICT_KEYWORDS:
                self.validation_data["biocontainers_keywords"] = kw_s
                return True
            kw_l = kw_s.lower()
            for pattern in COMPILED_FRAGMENT_PATTERNS:
                match = pattern.search(kw_l)
                if match:
                    self.validation_data["biocontainers_keywords"] = match.group(0)
                    return True
        return False

    def check_criteria_3(self) -> bool:
        sources = [
            ("biotools_description", self.descriptions.get("biotools", "")),
            ("biocontainers_description", self.descriptions.get("biocontainers", "")),
            ("galaxy_description", self.descriptions.get("galaxy", "")),
        ]
        for key, content in sources:
            content_l = content.lower()
            if not content_l:
                continue
            for strict_up, pattern in zip(STRICT_KEYWORDS, COMPILED_STRICT_PATTERNS):
                if pattern.search(content_l):
                    self.validation_data[key] = strict_up
                    return True
            for pattern in COMPILED_FRAGMENT_PATTERNS:
                match = pattern.search(content_l)
                if match:
                    word = match.group(0).split()[0]
                    self.validation_data[key] = re.sub(r"[.,;()?!]+$", "", word)
                    return True
        return False

    def run_checks(self) -> bool:
        if self.check_criteria_1() or self.check_criteria_2() or self.check_criteria_3():
            self.keep = True
            return True
        self.keep = False
        return False


class ToolSet:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.tools: List[Tool] = []
        self.report_counts = {
            "total_folders": 0,
            "validated_filter_1": 0,
            "validated_filter_2": 0,
            "validated_filter_3": 0,
            "did_not_pass_any": 0,
        }

    def _prepare_output_dir(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for f in [VALIDATED_METADATA_FILE, FAILED_METADATA_FILE, REPORTING_FILE, TSV_OUTPUT_FILE]:
            if f.exists():
                f.unlink()

    def run_filtering(self) -> None:
        start_time = time.time()
        self._prepare_output_dir(OUTPUT_DIR)
        to_delete, validated_meta, failed_meta = [], [], []

        print(f"Starting filtering in: {self.root_dir}")
        all_items = [item for item in self.root_dir.iterdir() if item.is_dir() and item.name != OUTPUT_DIR.name]
        total = len(all_items)

        for i, item in enumerate(all_items):
            sys.stdout.write(f"\rProgression: {i+1}/{total} ({item.name})")
            sys.stdout.flush()
            self.report_counts["total_folders"] += 1
            tool = Tool(item)
            tool.run_checks()
            if tool.keep:
                validated_meta.append(tool.validation_data)
                if "EDAM_operation" in tool.validation_data or "EDAM_topics" in tool.validation_data:
                    self.report_counts["validated_filter_1"] += 1
                elif "biocontainers_keywords" in tool.validation_data:
                    self.report_counts["validated_filter_2"] += 1
                else:
                    self.report_counts["validated_filter_3"] += 1
            else:
                to_delete.append(item)
                failed_meta.append(tool.validation_data)
                self.report_counts["did_not_pass_any"] += 1

        sys.stdout.write("\n")
        self._write_json(validated_meta, VALIDATED_METADATA_FILE)
        self._write_json(failed_meta, FAILED_METADATA_FILE)
        self._finalize(to_delete)
        print(f"\nFiltering time: {time.time() - start_time:.2f}s")

    def _write_json(self, data: List[Dict[str, Any]], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _finalize(self, to_delete: List[Path]) -> None:
        total_kept = (
            self.report_counts["validated_filter_1"]
            + self.report_counts["validated_filter_2"]
            + self.report_counts["validated_filter_3"]
        )
        print(f"\nAnalyzed: {self.report_counts['total_folders']} | Kept: {total_kept} | Deleted: {len(to_delete)}")
        for folder in to_delete:
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
        self._write_report(REPORTING_FILE, len(to_delete), total_kept)

    def _write_report(self, path: Path, deleted: int, kept: int) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Total: {self.report_counts['total_folders']}\nKept: {kept}\nDeleted: {deleted}\n")
            f.write(f"Filter 1: {self.report_counts['validated_filter_1']}\n")
            f.write(f"Filter 2: {self.report_counts['validated_filter_2']}\n")
            f.write(f"Filter 3: {self.report_counts['validated_filter_3']}\n")


# -------------------------------------------------------------
#                    MAIN EXECUTION
# -------------------------------------------------------------

if __name__ == "__main__":
    # --- STEP 1: Extraction ---
    if not clone_rsec_data():
        sys.exit(1)

    # --- STEP 2: Configuration ---
    if not KEYWORDS_FILEPATH.is_file():
        print(f"ERROR: {KEYWORDS_FILEPATH} not found.")
        sys.exit(1)

    ROOT_DIRECTORY = RSEC_DIR
    OUTPUT_DIR = RSEC_DIR / "infos"
    REPORTING_FILE = OUTPUT_DIR / "filtering_report.txt"
    VALIDATED_METADATA_FILE = OUTPUT_DIR / "validated_tools_metadata.json"
    FAILED_METADATA_FILE = OUTPUT_DIR / "failed_tools_metadata.json"
    TSV_OUTPUT_FILE = OUTPUT_DIR / "validated_tools_summary.tsv"

    try:
        kw = load_keywords_from_yaml(KEYWORDS_FILEPATH)
        TARGET_OPERATIONS = kw["operations"]
        TARGET_TOPICS = kw["topics"]
        STRICT_KEYWORDS = kw["stricts"]
        COMPILED_FRAGMENT_PATTERNS = kw["compiled_fragments"]
        COMPILED_STRICT_PATTERNS = kw["compiled_stricts"]
    except Exception as e:
        print(f"Init Error: {e}")
        sys.exit(1)

    # --- STEP 3: Filtering ---
    tool_set = ToolSet(ROOT_DIRECTORY)
    tool_set.run_filtering()
    generate_tsv_summary(VALIDATED_METADATA_FILE, TSV_OUTPUT_FILE)
