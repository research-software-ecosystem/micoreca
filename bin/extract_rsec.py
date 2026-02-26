#!/usr/bin/env python
import json
import re
import shutil
import sys
import time
import argparse
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
    def __init__(
        self,
        folder_path: Path,
        target_ops: list,
        target_topics: list,
        strict_kw: list,
        frag_patterns: list,
    ):
        self.folder_path = folder_path
        self.tool_id = folder_path.name
        self.keep = False
        self.validation_data: Dict[str, Any] = {"tool_id": self.tool_id}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.descriptions: Dict[str, str] = {}

        # Kewords and EDAM terms (ops and topics) for filtering
        self.target_ops = target_ops
        self.target_topics = target_topics
        self.strict_kw = strict_kw
        self.frag_patterns = frag_patterns

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
                if "term" in topic and topic["term"] in self.target_topics:
                    self.validation_data["EDAM_topics"] = topic["term"]
                    return True
        if "function" in data and isinstance(data["function"], list):
            for func in data["function"]:
                if "operation" in func and isinstance(func["operation"], list):
                    for op in func["operation"]:
                        if "term" in op and op["term"] in self.target_ops:
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
            # Case-sensitive substring search: "OTU" matches "xOTUanalysis" but not "xotuanalysis"
            matched_acronym = next((acr for acr in self.strict_kw if acr in kw_s), None)
            if matched_acronym:
                self.validation_data["biocontainers_keywords"] = matched_acronym
                return True
            kw_l = kw_s.lower()
            for pattern in self.frag_patterns:
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
            if not content:
                continue
            # Case-sensitive substring search: "OTU" matches "xOTUanalysis" but not "xotuanalysis"
            for strict_up in self.strict_kw:
                if strict_up in content:
                    self.validation_data[key] = strict_up
                    return True
            content_l = content.lower()
            for pattern in self.frag_patterns:
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
    def __init__(self, root_dir: Path, json_out: Path, tsv_out: Path, kw_file: Path):
        self.root_dir = root_dir
        self.json_out = json_out
        self.tsv_out = tsv_out
        self.kw_file = kw_file

        # output paths for reporting files, all in the same directory as json_out
        self.output_dir = json_out.parent
        self.report_txt_out = self.output_dir / "filtering_report.txt"

        self.tools: List[Tool] = []
        self.report_counts = {
            "total_folders": 0,
            "validated_filter_1": 0,
            "validated_filter_2": 0,
            "validated_filter_3": 0,
            "did_not_pass_any": 0,
        }

        # keywords loading
        kw = load_keywords_from_yaml(self.kw_file)
        self.kw_data = kw

    def _prepare_output_dir(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        for f in [self.json_out, self.report_txt_out, self.tsv_out]:
            if f.exists():
                f.unlink()

    def run_filtering(self) -> None:
        start_time = time.time()
        self._prepare_output_dir()
        to_delete, validated_meta = [], []

        print(f"Start of filtering in : {self.root_dir}")
        all_items = [item for item in self.root_dir.iterdir() if item.is_dir() and item.name != self.output_dir.name]
        total = len(all_items)

        for i, item in enumerate(all_items):
            sys.stdout.write(f"\rProgression : {i+1}/{total} ({item.name})")
            sys.stdout.flush()
            self.report_counts["total_folders"] += 1

            tool = Tool(
                item,
                self.kw_data["operations"],
                self.kw_data["topics"],
                self.kw_data["stricts"],
                self.kw_data["compiled_fragments"],
            )

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
                self.report_counts["did_not_pass_any"] += 1

        sys.stdout.write("\n")
        self._write_json(validated_meta, self.json_out)
        self._finalize(to_delete)
        print(f"\nFiltering time : {time.time() - start_time:.2f}s")

    def _write_json(self, data: List[Dict[str, Any]], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _finalize(self, to_delete: List[Path]) -> None:
        total_kept = (
            self.report_counts["validated_filter_1"]
            + self.report_counts["validated_filter_2"]
            + self.report_counts["validated_filter_3"]
        )
        print(f"\nAnalysed : {self.report_counts['total_folders']} | Kept : {total_kept} | Deleted : {len(to_delete)}")
        for folder in to_delete:
            try:
                shutil.rmtree(folder)
            except Exception:
                pass
        self._write_report(self.report_txt_out, len(to_delete), total_kept)

    def _write_report(self, path: Path, deleted: int, kept: int) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Total: {self.report_counts['total_folders']}\nKept: {kept}\nDeleted: {deleted}\n")
            f.write(f"Filter 1: {self.report_counts['validated_filter_1']}\n")
            f.write(f"Filter 2: {self.report_counts['validated_filter_2']}\n")
            f.write(f"Filter 3: {self.report_counts['validated_filter_3']}\n")


# -------------------------------------------------------------
#                    MAIN EXECUTION (CLI)
# -------------------------------------------------------------


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Extract and filter tools and associated metadata from RSEC, "
            "according to specified EDAM terms and keywords. "
            "Clones the RSEC repository, applies keyword/EDAM filtering, "
            "and outputs the results as JSON and TSV files."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # CLI arguments
    parser.add_argument(
        "--kw",
        type=str,
        default=str(KEYWORDS_FILEPATH),
        metavar="PATH",
        help=(
            "Path to the YAML keywords file used for filtering. "
            "Must contain 'edam.topics', 'edam.operations', 'keywords', and 'acronyms' sections. "
            f"(default: {KEYWORDS_FILEPATH})"
        ),
    )
    parser.add_argument(
        "--json-output",
        type=str,
        metavar="PATH",
        help=(
            "Path to the output JSON file for validated tools metadata. "
            f"(default: <rsec_dir>/infos/validated_tools_metadata.json)"
        ),
    )
    parser.add_argument(
        "--tsv-output",
        type=str,
        metavar="PATH",
        help=(
            "Path to the output TSV file for the validated tools summary. "
            f"(default: <rsec_dir>/infos/validated_tools_summary.tsv)"
        ),
    )

    args = parser.parse_args()

    # Default paths if not provided via CLI
    kw_path = Path(args.kw)
    output_dir = RSEC_DIR / "infos"
    json_path = Path(args.json_output) if args.json_output else output_dir / "validated_tools_metadata.json"
    tsv_path = Path(args.tsv_output) if args.tsv_output else output_dir / "validated_tools_summary.tsv"

    # --- STEP 1 : Cloning ---
    try:
        if not clone_rsec_data(
            repo_url=RSEC_REPO_URL,
            temp_dir=TEMP_CLONE_DIR,
            target_dir=RSEC_DIR,
            subdir_in_repo=TARGET_SUBDIR_IN_REPO,
        ):
            print("Cloning failed.")
            sys.exit(1)
    except Exception as e:
        print(f"Cloning error: {e}")
        sys.exit(1)

    # --- STEP 2 : Configuration verification ---
    if not kw_path.is_file():
        print(f"ERROR : {kw_path} not found .")
        sys.exit(1)

    # --- STEP 3 : Filtering ---
    try:
        tool_set = ToolSet(root_dir=RSEC_DIR, json_out=json_path, tsv_out=tsv_path, kw_file=kw_path)
        tool_set.run_filtering()
        generate_tsv_summary(json_path, tsv_path)
        print(f"Done : results in : {json_path.parent}")
    except Exception as e:
        print(f"Execution error: {e}")
        sys.exit(1)
