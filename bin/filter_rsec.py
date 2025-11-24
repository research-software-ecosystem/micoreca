#!/usr/bin/env python
import json
import shutil
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import csv
import time

# Attempt to import YAML. If it fails, sets yaml to None.
try:
    import yaml
except ImportError:
    yaml = None

# --- Configuration paths  ---
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BIN_DIR = SCRIPT_PATH.parent
BASE_DIR = SCRIPT_BIN_DIR.parent

RSEC_DIR = BASE_DIR / "content" / "rsec"
KEYWORDS_FILEPATH = BASE_DIR / "keywords.yml"

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
# Details on how the tool was filtered
# in the final tsv file it will be written in the 'reason' column : "Metagenomics in EDAM ", or "microbiome in bio.tools description" etc.
REASON_MAPPING = {
    "EDAM_topics": "{value} in EDAM Topics",
    "EDAM_operation": "{value} in EDAM Operations",
    "biocontainers_keywords": "{value} in BioContainers keywords",
    "biotools_description": "{value} in bio.tools description",
    "biocontainers_description": "{value} in BioContainers description",
    "galaxy_description": "{value} in Galaxy description",
}

# --- Shared Loading/Parsing Functions ---


def load_keywords_from_yaml(filepath: Path) -> Dict[str, Any]:
    """Loads filtering criteria from the YAML keywords file."""
    if yaml is None:
        raise ImportError("PyYAML is required but not installed (pip install pyyaml).")

    if not filepath.exists():
        raise FileNotFoundError(f"Keywords file not found at: {filepath}")

    try:
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading YAML file: {e}")

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
                print(f" [WARNING] Could not compile regex pattern '{pattern_raw}': {e}")  # Silent error in production
                pass

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


def generate_tsv_summary(json_path: Path, tsv_path: Path):
    """Loads validated metadata and writes the summary to a TSV file."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data: List[Dict[str, Any]] = json.load(f)
    except Exception as e:
        print(f"ERROR loading/parsing JSON for TSV: {e}")
        return
    if not isinstance(data, list) or not data:
        print("ℹWARNING: JSON content is empty or not a list. Skipping TSV generation.")
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
        # Prioritize description for summary display
        description = (
            item.get("biotools_description_full", "")
            or item.get("biocontainers_description_full", "")
            or item.get("galaxy_description_full", "")
            or "N/A - No description found in any prioritized file."
        )
        entry["description"] = description

        # Find the *first* matching criteria key to determine filtered_on/reason
        for key in CRITERIA_KEYS:
            match_value = item.get(key)
            if match_value:
                entry["filtered_on"] = key
                reason_template = REASON_MAPPING.get(key, "Match found on key: {key} (value: {value})")
                formatted_value = str(match_value)
                entry["reason"] = reason_template.format(value=formatted_value)
                break
        summary_data.append(entry)

    try:
        with open(tsv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(summary_data)

        print("\nSummary successfully created.")
        print(f"TSV file created: {tsv_path.name}")

    except OSError as e:
        print(f"ERROR writing TSV file: {e}")


# -------------------------------------------------------------
#                   TOOL class
# -------------------------------------------------------------


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
        """Helper to safely load JSON or YAML content (silent failure)."""
        try:
            with open(filepath, encoding="utf-8") as fh:
                if filepath.suffix in [".json"]:
                    return json.load(fh)
                elif filepath.suffix in [".yaml"] and yaml:
                    return yaml.safe_load(fh)
        except Exception:
            pass
        return None

    def _load_all_metadata_optimized(self):
        """Loads all required metadata files."""
        self.validation_data["has_biocontainers_infos"] = False
        self.validation_data["has_biotools_infos"] = False
        self.validation_data["has_galaxy_infos"] = False
        self.validation_data["biotools_description_full"] = ""
        self.validation_data["biocontainers_description_full"] = ""
        self.validation_data["galaxy_description_full"] = ""

        for path in self.folder_path.glob("*biotools.json"):
            data = self._safe_load(path)
            if data and isinstance(data, dict):
                self.metadata["biotools"] = data
                description = data.get("description", "")
                self.descriptions["biotools"] = description
                self.validation_data["has_biotools_infos"] = True
                self.validation_data["biotools_description_full"] = description
                break
        for path in self.folder_path.glob("*.biocontainers.yaml"):
            data = self._safe_load(path)
            if data and isinstance(data, dict):
                self.metadata["biocontainers"] = data
                description = data.get("description", "")
                self.descriptions["biocontainers"] = description
                self.validation_data["has_biocontainers_infos"] = True
                self.validation_data["biocontainers_description_full"] = description
                break

        for path in self.folder_path.glob("*.galaxy.json"):
            data = self._safe_load(path)
            if data and isinstance(data, dict):
                self.metadata["galaxy"] = data
                description = data.get("description", "")
                self.descriptions["galaxy"] = description
                self.validation_data["has_galaxy_infos"] = True
                self.validation_data["galaxy_description_full"] = description
                break

    def _extract_edam_terms(self, data: Dict[str, Any], key: str) -> str:
        """Extracts and concatenates EDAM terms."""
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

    def _store_full_report_metadata(self):
        """Extracts all EDAM operations, topics, and biotools ID for the TSV."""
        data = self.metadata.get("biotools")
        biotools_id = data.get("biotoolsID", "") if data else ""
        self.validation_data["biotools_id"] = biotools_id
        if not data:
            self.validation_data["EDAM_operations_full"] = ""
            self.validation_data["EDAM_topics_full"] = ""
            return

        full_operations = self._extract_edam_terms(data, "function")
        self.validation_data["EDAM_operations_full"] = full_operations
        full_topics = self._extract_edam_terms(data, "topic")
        self.validation_data["EDAM_topics_full"] = full_topics

    def check_criteria_1(self) -> bool:
        """Check for EDAM topics then operations."""
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
                    for operation in func["operation"]:
                        if "term" in operation and operation["term"] in TARGET_OPERATIONS:
                            self.validation_data["EDAM_operation"] = operation["term"]
                            return True

        return False

    def check_criteria_2(self) -> bool:
        """Check for strict acronyms or regex fragments in biocontainers YAML keywords."""
        data = self.metadata.get("biocontainers")
        if not data:
            return False

        file_keywords = data.get("keywords")
        if not file_keywords:
            return False
        candidates_with_case = []
        if isinstance(file_keywords, list):
            candidates_with_case = [str(x).strip() for x in file_keywords if x is not None]
        elif isinstance(file_keywords, str):
            candidates_with_case = [x.strip() for x in file_keywords.replace(";", ",").split(",") if x.strip()]

        strict_keywords_set = set(STRICT_KEYWORDS)
        for kw_case in candidates_with_case:
            if kw_case.upper() in strict_keywords_set:
                self.validation_data["biocontainers_keywords"] = kw_case
                return True

        for kw_case in candidates_with_case:
            kw_lower = kw_case.lower()
            for pattern in COMPILED_FRAGMENT_PATTERNS:
                match = pattern.search(kw_lower)
                if match:
                    self.validation_data["biocontainers_keywords"] = match.group(0)
                    return True
        return False

    def check_criteria_3(self) -> bool:
        """
        search in description fields for strict keywords/acronyms or regex fragments.
        Priority order: biotools > biocontainers > galaxy.
        """
        # Priority order for checking descriptions
        description_sources = [
            ("biotools_description", self.descriptions.get("biotools", "")),
            ("biocontainers_description", self.descriptions.get("biocontainers", "")),
            ("galaxy_description", self.descriptions.get("galaxy", "")),
        ]

        for key_report, content in description_sources:
            content_lower = content.lower()
            if not content_lower:
                continue

            # 1. Strict acronym checks (Word boundary search)
            for strict_ref_upper, pattern in zip(STRICT_KEYWORDS, COMPILED_STRICT_PATTERNS):
                if pattern.search(content_lower):
                    self.validation_data[key_report] = strict_ref_upper
                    return True

            # 2. Regex checks (fragment patterns)
            for pattern in COMPILED_FRAGMENT_PATTERNS:
                match = pattern.search(content_lower)
                if match:
                    phrase = match.group(0)
                    phrase = phrase.split()
                    mot = phrase[0]
                    ponctuation = r"[.,;()?!]+$"
                    mot = re.sub(ponctuation, "", mot)
                    self.validation_data[key_report] = mot
                    return True

        return False

    def run_checks(self) -> bool:
        """Runs the three filtering checks sequentially (stop at first match)."""

        if self.check_criteria_1():
            self.keep = True
            return True
        if self.check_criteria_2():
            self.keep = True
            return True

        if self.check_criteria_3():
            self.keep = True
            return True
        self.keep = False
        return False


# -------------------------------------------------------------
#               Toolset class
# -------------------------------------------------------------


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

    def _prepare_output_dir(self, output_dir: Path):
        """Creates the output directory and cleans up previous metadata files."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Output directory {output_dir.name}/ is ready.")
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Failed to create output directory {output_dir.name}/. Error: {e}")
            sys.exit(1)  # Stop if output dir cannot be created
        for meta_file in [
            VALIDATED_METADATA_FILE,
            FAILED_METADATA_FILE,
            REPORTING_FILE,
            TSV_OUTPUT_FILE,
        ]:
            if meta_file.exists():
                meta_file.unlink()

    def run_filtering(self):
        start_time = time.time()
        self._prepare_output_dir(OUTPUT_DIR)
        subfolders_to_delete = []
        validated_metadata_list = []
        failed_metadata_list = []

        print(f"Starting filtering in : {self.root_dir}")
        print("WARNING : Non-kept folders will be PERMANENTLY DELETED.")
        all_items = [item for item in self.root_dir.iterdir() if item.is_dir() and item.name != OUTPUT_DIR.name]
        total_items = len(all_items)
        # --- Processing Loop (Utilisation de sys.stdout.write pour la progression) ---
        for i, item in enumerate(all_items):
            dossier_actuel = i + 1
            message = f"Progression: Analysis of folder {dossier_actuel} on {total_items} ({item.name})"
            sys.stdout.write("\r" + message)
            sys.stdout.flush()
            self.report_counts["total_folders"] += 1
            tool = Tool(item)
            tool.run_checks()
            self.tools.append(tool)
            if tool.keep:
                validated_metadata_list.append(tool.validation_data)
                if "EDAM_operation" in tool.validation_data or "EDAM_topics" in tool.validation_data:
                    self.report_counts["validated_filter_1"] += 1
                elif "biocontainers_keywords" in tool.validation_data:
                    self.report_counts["validated_filter_2"] += 1
                elif any(
                    key in tool.validation_data
                    for key in [
                        "biotools_description",
                        "biocontainers_description",
                        "galaxy_description",
                    ]
                ):
                    self.report_counts["validated_filter_3"] += 1
            else:
                subfolders_to_delete.append(item)
                failed_metadata_list.append(tool.validation_data)
                self.report_counts["did_not_pass_any"] += 1

        sys.stdout.write("\n")

        # --- I/O Post-Processing ---
        self._write_metadata_once(validated_metadata_list, VALIDATED_METADATA_FILE)
        self._write_metadata_once(failed_metadata_list, FAILED_METADATA_FILE)

        self._finalize_operation(subfolders_to_delete)
        end_time = time.time()
        print(f"\nFiltering execution time : {end_time - start_time:.2f} secondes.")

    def _write_metadata_once(self, data: List[Dict[str, Any]], metadata_file: Path):
        """Writes the entire list of data to a single JSON file."""
        if not data:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump([], f)
            return

        try:
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"Metadata file written: {metadata_file.name}")
        except OSError as e:
            print(f" [META ERROR] Could not write metadata file ({metadata_file.name}): {e}")

    def _finalize_operation(self, subfolders_to_delete: List[Path]):
        """Prints final stats and performs folder deletion."""
        total_deleted = len(subfolders_to_delete)
        total_kept = sum(
            self.report_counts[k] for k in ["validated_filter_1", "validated_filter_2", "validated_filter_3"]
        )

        print("\n" + "=" * 50)
        print(f"Total subfolders found : {self.report_counts['total_folders']}")
        print(f"Subfolders to KEEP (in the current directory) : {total_kept}")
        print(f"Subfolders to DELETE : {total_deleted}")

        if subfolders_to_delete:
            print("\n--- Deleting non-kept folders ---")
            for folder in subfolders_to_delete:
                try:
                    shutil.rmtree(folder)
                except OSError as e:
                    print(f" [DELETION ERROR] Could not delete {folder.name}: {e}")
        self._write_report(REPORTING_FILE, total_deleted, total_kept)
        print("\nFiltering operation completed.")

    def _write_report(self, report_file: Path, total_deleted: int, total_kept: int):
        """Writes the summary report to a text file."""
        try:
            with open(report_file, "w", encoding="utf-8") as f:
                f.write("=" * 40 + "\n")
                f.write(" SUBFOLDER FILTERING REPORT\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Total folders analyzed : {self.report_counts['total_folders']}\n")
                f.write(f"Total folders kept : {total_kept}\n")
                f.write(f"Total folders DELETED : {total_deleted}\n\n")

                f.write("-" * 25 + "\n")
                f.write("Folders kept by criterion (Stop at first match):\n")
                f.write("-" * 25 + "\n")
                f.write(f" 1. Validated by Filter 1 (Op/Topic JSON) : {self.report_counts['validated_filter_1']}\n")
                f.write(f" 2. Validated by Filter 2 (YAML Keywords) : {self.report_counts['validated_filter_2']}\n")
                f.write(
                    f" 3. Validated by Filter 3 (Description Match) : {self.report_counts['validated_filter_3']}\n\n"
                )
                f.write(f"Folders that failed ANY filter : {self.report_counts['did_not_pass_any']}\n")
            print(f"\n[REPORTING] Report written to : {report_file.name}")
        except OSError as e:
            print(f"\n[CRITICAL WRITE FAILURE] Could not write report to '{report_file.parent.name}/'. Error: {e}")


# -------------------------------------------------------------
#                    MAIN EXECUTION
# -------------------------------------------------------------

if __name__ == "__main__":
    if not RSEC_DIR.is_dir():
        print(f"ERROR: The directory to process 'content/rsec' was not found at the default location: '{RSEC_DIR}'")
        sys.exit(1)
    if not KEYWORDS_FILEPATH.is_file():
        print(
            f"ERROR: The YAML configuration file 'keywords.yml' was not found at the default location: '{KEYWORDS_FILEPATH}'"
        )
        sys.exit(1)

    ROOT_DIRECTORY = RSEC_DIR
    OUTPUT_DIR = RSEC_DIR / "infos"
    REPORTING_FILE = OUTPUT_DIR / "filtering_report.txt"
    VALIDATED_METADATA_FILE = OUTPUT_DIR / "validated_tools_metadata.json"
    FAILED_METADATA_FILE = OUTPUT_DIR / "failed_tools_metadata.json"
    TSV_OUTPUT_FILE = OUTPUT_DIR / "validated_tools_summary.tsv"

    try:
        keywords_data = load_keywords_from_yaml(KEYWORDS_FILEPATH)
        TARGET_OPERATIONS = keywords_data["operations"]
        TARGET_TOPICS = keywords_data["topics"]
        STRICT_KEYWORDS = keywords_data["stricts"]
        COMPILED_FRAGMENT_PATTERNS = keywords_data["compiled_fragments"]
        COMPILED_STRICT_PATTERNS = keywords_data["compiled_stricts"]
        print("\n--- LOADED CRITERIA ---")
        print(f"EDAM Operations: {len(TARGET_OPERATIONS)} terms")
        print(f"Strict Acronyms: {len(STRICT_KEYWORDS)} terms")
        print(f"Fragment Patterns: {len(COMPILED_FRAGMENT_PATTERNS)} regex")
        print("--------------------------\n")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to initialize keywords: {e}")
        sys.exit(1)

    tool_set = ToolSet(ROOT_DIRECTORY)
    tool_set.run_filtering()
    print("\n--- Generating TSV Summary ---")
    generate_tsv_summary(VALIDATED_METADATA_FILE, TSV_OUTPUT_FILE)
