#!/usr/bin/env python
import argparse
import csv
import json
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
)

import pandas as pd
import yaml
from utils import (
    BIOCONDA_DIR,
    clone_rsec_content,
    CRITERIA_KEYS,
    export_to_json,
    GALAXY_DIR,
    generate_tsv_summary,
    has_edam_terms,
    has_keyword,
    KEYWORDS_FILEPATH,
    load_json,
    load_keywords_from_yaml,
    load_yaml,
    REASON_MAPPING,
    RSEC_DIR,
    RSEC_REPO_URL,
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
        validated_meta: List[Dict[str, Any]] = []

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
                self.report_counts["did_not_pass_any"] += 1

        sys.stdout.write("\n")
        self._write_json(validated_meta, self.json_out)
        self._write_report(self.report_txt_out)
        print(f"\nFiltering time : {time.time() - start_time:.2f}s")

    def _write_json(self, data: List[Dict[str, Any]], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _write_report(self, path: Path) -> None:
        total_kept = (
            self.report_counts["validated_filter_1"]
            + self.report_counts["validated_filter_2"]
            + self.report_counts["validated_filter_3"]
        )
        rejected = self.report_counts["did_not_pass_any"]
        print(f"\nAnalysed : {self.report_counts['total_folders']} | Kept : {total_kept} | Rejected : {rejected}")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Total: {self.report_counts['total_folders']}\nKept: {total_kept}\nRejected: {rejected}\n")
            f.write(f"Filter 1: {self.report_counts['validated_filter_1']}\n")
            f.write(f"Filter 2: {self.report_counts['validated_filter_2']}\n")
            f.write(f"Filter 3: {self.report_counts['validated_filter_3']}\n")


# -------------------------------------------------------------
#          RSEC data filter outputs / status round-trip
# -------------------------------------------------------------

# rsec output files (all live directly under content/rsec/)
RSEC_METADATA_JSON = RSEC_DIR / "validated_tools_metadata.json"
RSEC_SUMMARY_TSV = RSEC_DIR / "validated_tools_summary.tsv"
RSEC_STATUS_TSV = RSEC_DIR / "validated_tools_status.tsv"

RSEC_STATUS_FIELDS = ["tool_id", "to_keep", "reason"]


def _match_reason(item: Dict[str, Any]) -> str:
    """Derive the match reason for a validated tool entry."""
    for key in CRITERIA_KEYS:
        match_value = item.get(key)
        if match_value:
            template = REASON_MAPPING.get(key, "Match found on key: {key}")
            return template.format(value=str(match_value))
    return "N/A - Not Matched"


def _read_status_keep(status_path: Path, key_col: str, keep_col: str = "to_keep") -> Dict[str, bool]:
    """Read a community status TSV as {id: keep}. Only an explicit 'False' drops an entry."""
    result: Dict[str, bool] = {}
    if not status_path.exists():
        return result
    with open(status_path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            key = row.get(key_col, "")
            if key:
                result[key] = str(row.get(keep_col, "True")).strip().lower() != "false"
    return result


def write_rsec_status(json_path: Path, status_path: Path) -> None:
    """Write the community-editable status TSV; new tools default to_keep=False (opt-in),
    preserving prior community approvals."""
    data: List[Dict[str, Any]] = load_json(str(json_path))
    existing = _read_status_keep(status_path, "tool_id")
    with open(status_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RSEC_STATUS_FIELDS, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for item in data:
            tool_id = item.get("tool_id", "")
            writer.writerow(
                {
                    "tool_id": tool_id,
                    "to_keep": str(existing.get(tool_id, False)),
                    "reason": _match_reason(item),
                }
            )
    print(f"Status TSV written: {status_path.name}")


def filter_rsec_data(data_dir: Path, kw_path: Path) -> None:
    """Filter the cloned RSEc data/ tools and write metadata, summary, report and status."""
    tool_set = ToolSet(root_dir=data_dir, json_out=RSEC_METADATA_JSON, tsv_out=RSEC_SUMMARY_TSV, kw_file=kw_path)
    tool_set.run_filtering()
    generate_tsv_summary(RSEC_METADATA_JSON, RSEC_SUMMARY_TSV)
    write_rsec_status(RSEC_METADATA_JSON, RSEC_STATUS_TSV)
    print(f"Done : rsec results in {RSEC_DIR}")


# -------------------------------------------------------------
#          bioconda / galaxy import filters (full-recipe)
# -------------------------------------------------------------


class ImportCollection:
    """A flat collection of RSEc import files (full-dict entries) filtered by a match callback.

    Each kept entry is the entire parsed import file (plus a ``keep`` flag). Filtering
    proposes candidates (keep defaults False) and writes the ``keep`` column to the
    status TSV for later community review.
    """

    def __init__(
        self,
        index_col: str,
        name_fn: Callable[[Dict[str, Any]], str],
        match_fn: Callable[[Dict[str, Any]], bool],
    ):
        self.index_col = index_col
        self.name_fn = name_fn
        self.match_fn = match_fn
        self.entries: Dict[str, Dict[str, Any]] = {}

    def load_entries(self, entries: List[Dict[str, Any]]) -> None:
        for entry in entries:
            name = self.name_fn(entry)
            if name:
                self.entries[name] = entry

    def filter_entries(self, status: Dict[str, bool]) -> None:
        """Keep entries matching the keywords, or already accepted by the community."""
        filtered: Dict[str, Dict[str, Any]] = {}
        for name, entry in self.entries.items():
            keep = status.get(name, False)
            if keep or self.match_fn(entry):
                entry["keep"] = keep
                filtered[name] = entry
        self.entries = filtered

    def export_to_json(self, path: Path) -> None:
        export_to_json(list(self.entries.values()), str(path))

    def export_to_tsv(self, path: Path, columns: Optional[List[str]] = None) -> None:
        df = pd.json_normalize(list(self.entries.values()))
        if not df.empty and self.index_col in df.columns:
            df = df.set_index(self.index_col)
        if columns is not None:
            df = df[[c for c in columns if c in df.columns]]
        df.to_csv(path, sep="\t")


def _read_import_status(status_path: Path, index_col: str) -> Dict[str, bool]:
    """Read an import status TSV as {id: keep}. Only an explicit 'False' drops an entry."""
    if not status_path.exists():
        return {}
    try:
        df = pd.read_csv(status_path, sep="\t", index_col=index_col)
    except Exception:
        return {}
    if "keep" not in df.columns:
        return {}
    return {str(idx): str(val).strip().lower() != "false" for idx, val in df["keep"].items()}


def _bioconda_name(entry: Dict[str, Any]) -> str:
    return str((entry.get("package") or {}).get("name", ""))


def _bioconda_match(keywords: Dict[str, Any]) -> Callable[[Dict[str, Any]], bool]:
    def match(entry: Dict[str, Any]) -> bool:
        about = entry.get("about") or {}
        text = (str(about.get("description", "")) + " " + str(about.get("summary", ""))).lower()
        return has_keyword(keywords, text, "description") != ""

    return match


def _load_bioconda_imports(directory: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and _bioconda_name(data):
            entries.append(data)
    return entries


def _galaxy_name(entry: Dict[str, Any]) -> str:
    return str(entry.get("id", ""))


def _galaxy_match(keywords: Dict[str, Any]) -> Callable[[Dict[str, Any]], bool]:
    edam = keywords.get("edam", {}) or {}

    def match(entry: Dict[str, Any]) -> bool:
        topics = entry.get("EDAM_topics") or []
        operations = entry.get("EDAM_operations") or []
        if has_edam_terms(topics, operations, edam):
            return True
        text = (str(entry.get("id", "")) + " " + str(entry.get("Description", ""))).lower()
        return has_keyword(keywords, text, "description") != ""

    return match


def _load_galaxy_imports(directory: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        name = path.name
        for suffix in (".galaxy.json", ".json"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        data["id"] = name
        entries.append(data)
    return entries


# bioconda / galaxy output files
BIOCONDA_FILTERED_JSON = BIOCONDA_DIR / "bioconda_filtered.json"
BIOCONDA_FILTERED_TSV = BIOCONDA_DIR / "bioconda_filtered.tsv"
BIOCONDA_STATUS_TSV = BIOCONDA_DIR / "bioconda_status.tsv"
BIOCONDA_STATUS_COLUMNS = ["keep", "about.summary", "about.description", "about.home"]

GALAXY_FILTERED_JSON = GALAXY_DIR / "galaxy_filtered.json"
GALAXY_FILTERED_TSV = GALAXY_DIR / "galaxy_filtered.tsv"
GALAXY_STATUS_TSV = GALAXY_DIR / "galaxy_status.tsv"
GALAXY_STATUS_COLUMNS = ["keep", "Description", "Homepage", "EDAM_operations", "EDAM_topics"]


def filter_bioconda_imports(imports_dir: Path, keywords: Dict[str, Any]) -> None:
    BIOCONDA_DIR.mkdir(parents=True, exist_ok=True)
    coll = ImportCollection("package.name", _bioconda_name, _bioconda_match(keywords))
    coll.load_entries(_load_bioconda_imports(imports_dir))
    coll.filter_entries(_read_import_status(BIOCONDA_STATUS_TSV, "package.name"))
    coll.export_to_json(BIOCONDA_FILTERED_JSON)
    coll.export_to_tsv(BIOCONDA_FILTERED_TSV)
    coll.export_to_tsv(BIOCONDA_STATUS_TSV, columns=BIOCONDA_STATUS_COLUMNS)
    print(f"Filtered {len(coll.entries)} bioconda imports -> {BIOCONDA_DIR}")


def filter_galaxy_imports(imports_dir: Path, keywords: Dict[str, Any]) -> None:
    GALAXY_DIR.mkdir(parents=True, exist_ok=True)
    coll = ImportCollection("id", _galaxy_name, _galaxy_match(keywords))
    coll.load_entries(_load_galaxy_imports(imports_dir))
    coll.filter_entries(_read_import_status(GALAXY_STATUS_TSV, "id"))
    coll.export_to_json(GALAXY_FILTERED_JSON)
    coll.export_to_tsv(GALAXY_FILTERED_TSV)
    coll.export_to_tsv(GALAXY_STATUS_TSV, columns=GALAXY_STATUS_COLUMNS)
    print(f"Filtered {len(coll.entries)} galaxy imports -> {GALAXY_DIR}")


# -------------------------------------------------------------
#                    MAIN EXECUTION (CLI)
# -------------------------------------------------------------

RSEC_SUBDIRS = ["data", "imports/bioconda", "imports/galaxy"]


def run_filter(kw: str) -> None:
    """Clone RSEc content to a temp dir, filter it, then remove the clone."""
    kw_path = Path(kw)
    if not kw_path.is_file():
        print(f"ERROR : {kw_path} not found .")
        sys.exit(1)

    keywords = load_yaml(str(kw_path))
    temp_dir = Path(tempfile.mkdtemp(prefix="rsec_clone_"))
    try:
        if not clone_rsec_content(RSEC_REPO_URL, temp_dir, RSEC_SUBDIRS):
            print("Cloning failed.")
            sys.exit(1)
        filter_rsec_data(temp_dir / "data", kw_path)
        filter_bioconda_imports(temp_dir / "imports" / "bioconda", keywords)
        filter_galaxy_imports(temp_dir / "imports" / "galaxy", keywords)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Filter tools and associated metadata from RSEC according to "
            "specified EDAM terms and keywords."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparser = parser.add_subparsers(dest="command")

    # Filter: clone RSEc content to a temp dir and filter it into content/
    filter_parser = subparser.add_parser(
        "filter",
        help="Clone RSEc content to a temp dir and filter it by keywords and EDAM terms",
    )
    filter_parser.add_argument(
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

    args = parser.parse_args(argv)

    if args.command == "filter":
        run_filter(args.kw)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
