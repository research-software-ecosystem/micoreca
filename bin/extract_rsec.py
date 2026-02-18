#!/usr/bin/env python
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import yaml
from utils import (
    clone_rsec_data,
    generate_tsv_summary,
    KEYWORDS_FILEPATH,
    load_keywords_from_yaml,
    RSEC_DIR,
    RSEC_REPO_URL,
    TARGET_SUBDIR_IN_REPO,
    TEMP_CLONE_DIR,
)


class Tool:
    def __init__(self, folder_path: Path):
        self.folder_path = folder_path
        self.tool_id = folder_path.name
        self.keep = False
        self.validation_data: Dict[str, Any] = {"tool_id": self.tool_id}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.descriptions: Dict[str, str] = {}
        self._load_all_metadata()
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

    def _load_all_metadata(self) -> None:
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
    if not clone_rsec_data(
        repo_url=RSEC_REPO_URL,
        temp_dir=TEMP_CLONE_DIR,
        target_dir=RSEC_DIR,  # local rsec dir (micoreca/content/rsec)
        subdir_in_repo=TARGET_SUBDIR_IN_REPO,  # content/data subdir from rsec repo
    ):
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
