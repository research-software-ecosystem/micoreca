"""
Unit tests for extract_rsec.py and the utils functions it imports.


Within each class, test methods follow the exact definition order of the
function they cover in the source file.

"""

import contextlib
import csv
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Make sure Python can find the source modules in bin/
# This works whether you run pytest from the project root or from tests/.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Import the classes and utils functions under test
# ---------------------------------------------------------------------------
from extract_rsec import (  # noqa: E402
    Tool,
    ToolSet,
)
from utils import (  # noqa: E402
    clone_rsec_data,
    generate_tsv_summary,
    load_keywords_from_yaml,
)

# ===========================================================================
#  Shared test fixtures / factories
# ===========================================================================

# Canonical sample data reused across all test classes
SAMPLE_BIOTOOLS = {
    "biotoolsID": "mytool",
    "description": "A tool for sequence alignment and variant calling",
    "topic": [{"term": "Genomics"}, {"term": "Proteomics"}],
    "function": [
        {
            "operation": [
                {"term": "Sequence alignment"},
                {"term": "Variant calling"},
            ]
        }
    ],
}

SAMPLE_BIOCONTAINERS = {
    "description": "Container for genomics pipelines",
    "keywords": ["genomics", "alignment", "FASTA"],
}

SAMPLE_GALAXY = {
    "description": "Galaxy wrapper for variant calling",
}

# Minimal keyword sets that match the SAMPLE_* data above
DEFAULT_TARGET_OPS = ["Sequence alignment", "Variant calling"]
DEFAULT_TARGET_TOPICS = ["Genomics", "Proteomics"]
DEFAULT_STRICT_KW = ["FASTA", "VCF"]
DEFAULT_FRAG_PATTERNS = [
    re.compile(r"(?<![A-Za-z])genomic[s]?(?![A-Za-z])", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z])variant(?![A-Za-z])", re.IGNORECASE),
]
DEFAULT_STRICT_PATTERNS = [
    re.compile(r"\bFASTA\b"),
    re.compile(r"\bVCF\b"),
]


def _make_tool_folder(
    base: Path,
    tool_id: str = "tool_abc",
    biotools: dict | None = None,
    biocontainers: dict | None = None,
    galaxy: dict | None = None,
) -> Path:
    """Create a minimal fake tool folder with optional metadata files."""
    folder = base / tool_id
    folder.mkdir(parents=True, exist_ok=True)
    if biotools is not None:
        (folder / f"{tool_id}.biotools.json").write_text(json.dumps(biotools), encoding="utf-8")
    if biocontainers is not None:
        (folder / f"{tool_id}.biocontainers.yaml").write_text(yaml.dump(biocontainers), encoding="utf-8")
    if galaxy is not None:
        (folder / f"{tool_id}.galaxy.json").write_text(json.dumps(galaxy), encoding="utf-8")
    return folder


def _make_tool(
    folder: Path,
    target_ops: list[str] | None = None,
    target_topics: list[str] | None = None,
    strict_kw: list[str] | None = None,
    frag_patterns: list[re.Pattern] | None = None,
) -> Tool:
    """Instantiate a Tool with sensible defaults for keyword args."""
    return Tool(
        folder,
        target_ops=target_ops if target_ops is not None else DEFAULT_TARGET_OPS,
        target_topics=target_topics if target_topics is not None else DEFAULT_TARGET_TOPICS,
        strict_kw=strict_kw if strict_kw is not None else DEFAULT_STRICT_KW,
        frag_patterns=frag_patterns if frag_patterns is not None else DEFAULT_FRAG_PATTERNS,
    )


def _make_keywords_yaml(base: Path, content: dict | None = None) -> Path:
    """Write a keywords YAML file and return its path."""
    if content is None:
        content = {
            "edam": {
                "operations": DEFAULT_TARGET_OPS,
                "topics": DEFAULT_TARGET_TOPICS,
            },
            "keywords": [r"genomic[s]?", r"variant"],
            "acronyms": ["FASTA", "VCF"],
        }
    p = base / "keywords.yml"
    p.write_text(yaml.dump(content), encoding="utf-8")
    return p


def _make_toolset(tmp_path: Path, kw_file: Path | None = None) -> ToolSet:
    """Return a ToolSet pointing at tmp_path, with a real keywords file."""
    if kw_file is None:
        kw_file = _make_keywords_yaml(tmp_path)
    out_dir = tmp_path / "infos"
    return ToolSet(
        root_dir=tmp_path,
        json_out=out_dir / "validated_tools_metadata.json",
        tsv_out=out_dir / "validated_tools_summary.tsv",
        kw_file=kw_file,
    )


# ===========================================================================
#  TestTool  —  methods in definition order
# ===========================================================================


class RsecTestCase(unittest.TestCase):
    """Base TestCase that provides a temporary directory like pytest's tmp_path.

    Each test gets a fresh temporary directory available as self.tmp_path (Path).
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="rsec_test_")
        self.tmp_path = Path(self._tmpdir)

    def tearDown(self) -> None:
        try:
            shutil.rmtree(self._tmpdir)
        except Exception:
            pass


class TestTool(RsecTestCase):
    """Tests for the Tool class defined in extract_rsec.py."""

    # ------------------------------------------------------------------ __init__

    def test_init_sets_tool_id_from_folder_name(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, "my_tool")
        tool = _make_tool(folder)
        assert tool.tool_id == "my_tool"

    def test_init_keep_defaults_to_false(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.keep is False

    def test_init_validation_data_contains_tool_id(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, "tool_xyz")
        tool = _make_tool(folder)
        assert tool.validation_data["tool_id"] == "tool_xyz"

    def test_init_keyword_attributes_stored(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder, target_ops=["Op1"], target_topics=["Topic1"])
        assert tool.target_ops == ["Op1"]
        assert tool.target_topics == ["Topic1"]

    # ------------------------------------------------------------------ _safe_load

    def test_safe_load_reads_json_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        p = tmp_path / "test.json"
        p.write_text(json.dumps({"key": "value"}), encoding="utf-8")
        assert tool._safe_load(p) == {"key": "value"}

    def test_safe_load_reads_yaml_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump({"num": 42}), encoding="utf-8")
        assert tool._safe_load(p) == {"num": 42}

    def test_safe_load_returns_none_for_malformed_json(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        p = tmp_path / "bad.json"
        p.write_text("{{not valid json}}", encoding="utf-8")
        assert tool._safe_load(p) is None

    def test_safe_load_returns_none_for_missing_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool._safe_load(tmp_path / "ghost.json") is None

    # ------------------------------------------------------------------ _load_all_metadata

    def test_load_all_metadata_detects_biotools_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder)
        assert tool.validation_data["has_biotools_infos"] is True
        assert "sequence alignment" in tool.validation_data["biotools_description_full"].lower()

    def test_load_all_metadata_detects_biocontainers_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers=SAMPLE_BIOCONTAINERS)
        tool = _make_tool(folder)
        assert tool.validation_data["has_biocontainers_infos"] is True
        assert "genomics" in tool.validation_data["biocontainers_description_full"].lower()

    def test_load_all_metadata_detects_galaxy_file(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, galaxy=SAMPLE_GALAXY)
        tool = _make_tool(folder)
        assert tool.validation_data["has_galaxy_infos"] is True
        assert "galaxy" in tool.validation_data["galaxy_description_full"].lower()

    def test_load_all_metadata_empty_folder_all_false(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.validation_data["has_biotools_infos"] is False
        assert tool.validation_data["has_biocontainers_infos"] is False
        assert tool.validation_data["has_galaxy_infos"] is False

    def test_load_all_metadata_all_three_sources(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(
            tmp_path,
            biotools=SAMPLE_BIOTOOLS,
            biocontainers=SAMPLE_BIOCONTAINERS,
            galaxy=SAMPLE_GALAXY,
        )
        tool = _make_tool(folder)
        assert tool.validation_data["has_biotools_infos"] is True
        assert tool.validation_data["has_biocontainers_infos"] is True
        assert tool.validation_data["has_galaxy_infos"] is True

    # ------------------------------------------------------------------ _extract_edam_terms

    def test_extract_edam_terms_returns_function_operations(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        result = tool._extract_edam_terms(SAMPLE_BIOTOOLS, "function")
        assert "Sequence alignment" in result
        assert "Variant calling" in result

    def test_extract_edam_terms_returns_topics(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        result = tool._extract_edam_terms(SAMPLE_BIOTOOLS, "topic")
        assert "Genomics" in result
        assert "Proteomics" in result

    def test_extract_edam_terms_returns_sorted_comma_separated(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        data = {"topic": [{"term": "Zzz"}, {"term": "Aaa"}]}
        assert tool._extract_edam_terms(data, "topic") == "Aaa, Zzz"

    def test_extract_edam_terms_empty_data_returns_empty_string(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool._extract_edam_terms({}, "function") == ""
        assert tool._extract_edam_terms({}, "topic") == ""

    def test_extract_edam_terms_deduplicates(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        data = {"topic": [{"term": "Genomics"}, {"term": "Genomics"}]}
        result = tool._extract_edam_terms(data, "topic")
        assert result.count("Genomics") == 1

    # ------------------------------------------------------------------ _store_full_report_metadata

    def test_store_full_report_metadata_fills_biotools_id(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder)
        assert tool.validation_data["biotools_id"] == "mytool"

    def test_store_full_report_metadata_fills_edam_operations(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder)
        assert "Sequence alignment" in tool.validation_data["EDAM_operations_full"]

    def test_store_full_report_metadata_fills_edam_topics(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder)
        assert "Genomics" in tool.validation_data["EDAM_topics_full"]

    def test_store_full_report_metadata_empty_without_biotools(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.validation_data["biotools_id"] == ""
        assert tool.validation_data["EDAM_operations_full"] == ""
        assert tool.validation_data["EDAM_topics_full"] == ""

    # ------------------------------------------------------------------ check_criteria_1

    def test_check_criteria_1_matches_on_topic(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder, target_topics=["Genomics"])
        assert tool.check_criteria_1() is True
        assert tool.validation_data.get("EDAM_topics") == "Genomics"

    def test_check_criteria_1_matches_on_operation(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder, target_topics=[], target_ops=["Sequence alignment"])
        assert tool.check_criteria_1() is True
        assert tool.validation_data.get("EDAM_operation") == "Sequence alignment"

    def test_check_criteria_1_returns_false_when_no_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder, target_topics=["Unknown"], target_ops=["Unknown op"])
        assert tool.check_criteria_1() is False

    def test_check_criteria_1_returns_false_without_biotools(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.check_criteria_1() is False

    def test_check_criteria_1_topic_takes_priority_over_operation(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(
            folder,
            target_topics=["Genomics"],
            target_ops=["Sequence alignment"],
        )
        tool.check_criteria_1()
        # topic is checked first in the function
        assert "EDAM_topics" in tool.validation_data

    # ------------------------------------------------------------------ check_criteria_2

    def test_check_criteria_2_matches_strict_keyword(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["FASTA", "other"]})
        tool = _make_tool(folder, strict_kw=["FASTA"], frag_patterns=[])
        assert tool.check_criteria_2() is True
        assert tool.validation_data.get("biocontainers_keywords") == "FASTA"

    def test_check_criteria_2_matches_fragment_pattern(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["genomics"]})
        pat = re.compile(r"(?<![A-Za-z])genomic[s]?(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_2() is True

    def test_check_criteria_2_handles_keyword_string_with_semicolons(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": "FASTA; alignment"})
        tool = _make_tool(folder, strict_kw=["FASTA"], frag_patterns=[])
        assert tool.check_criteria_2() is True

    def test_check_criteria_2_handles_keyword_string_with_commas(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": "alignment,FASTA"})
        tool = _make_tool(folder, strict_kw=["FASTA"], frag_patterns=[])
        assert tool.check_criteria_2() is True

    def test_check_criteria_2_returns_false_when_no_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["protein", "mass-spec"]})
        tool = _make_tool(folder, strict_kw=["VCF"], frag_patterns=[])
        assert tool.check_criteria_2() is False

    def test_check_criteria_2_returns_false_without_biocontainers(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.check_criteria_2() is False

    def test_check_criteria_2_fragment_matches_uppercase_keyword(self) -> None:
        # "METAGENOMICS" (uppercase) must match a pattern compiled with re.IGNORECASE
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["METAGENOMICS"]})
        pat = re.compile(r"(?<![A-Za-z])metage[a-z]*(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_2() is True

    def test_check_criteria_2_fragment_matches_mixed_case_keyword(self) -> None:
        # "Metagenomics" (title case) must also match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["Metagenomics"]})
        pat = re.compile(r"(?<![A-Za-z])metage[a-z]*(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_2() is True

    def test_check_criteria_2_strict_does_not_match_substring(self) -> None:
        # "ITS" must NOT match "Inherits" — strict keywords require an exact word match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["Inherits", "distributed"]})
        tool = _make_tool(folder, strict_kw=["ITS"], frag_patterns=[])
        assert tool.check_criteria_2() is False

    def test_check_criteria_2_fragment_matches_acronym_inside_compound_word(self) -> None:
        # "OTU" MUST match "xOTUanalysis" — biological compound terms embed acronyms
        # This requires a fragment pattern (substring search), not a strict exact match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["xOTUanalysis"]})
        pat = re.compile(r"OTU", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_2() is True

    # ------------------------------------------------------------------ check_criteria_3

    def test_check_criteria_3_matches_strict_in_biotools_description(self) -> None:
        tmp_path = self.tmp_path
        bt = {**SAMPLE_BIOTOOLS, "description": "Processes FASTA files for alignment"}
        folder = _make_tool_folder(tmp_path, biotools=bt)
        tool = _make_tool(folder, strict_kw=["FASTA"], frag_patterns=[])
        assert tool.check_criteria_3() is True
        assert tool.validation_data.get("biotools_description") == "FASTA"

    def test_check_criteria_3_matches_fragment_in_biocontainers_description(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"description": "genomics pipeline"})
        pat = re.compile(r"(?<![A-Za-z])genomic[s]?(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_3() is True
        assert "biocontainers_description" in tool.validation_data

    def test_check_criteria_3_matches_fragment_in_galaxy_description(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, galaxy={"description": "Tool for variant detection"})
        pat = re.compile(r"(?<![A-Za-z])variant(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_3() is True
        assert "galaxy_description" in tool.validation_data

    def test_check_criteria_3_returns_false_when_no_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(
            folder,
            strict_kw=["UNMATCHABLE_TERM"],
            frag_patterns=[re.compile(r"unmatchable_fragment")],
        )
        assert tool.check_criteria_3() is False

    def test_check_criteria_3_returns_false_with_all_empty_descriptions(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(folder)
        assert tool.check_criteria_3() is False

    def test_check_criteria_3_biotools_checked_before_galaxy(self) -> None:
        tmp_path = self.tmp_path
        bt = {**SAMPLE_BIOTOOLS, "description": "FASTA processing"}
        folder = _make_tool_folder(
            tmp_path,
            biotools=bt,
            galaxy={"description": "FASTA tool"},
        )
        tool = _make_tool(folder, strict_kw=["FASTA"], frag_patterns=[])
        tool.check_criteria_3()
        assert "biotools_description" in tool.validation_data
        assert "galaxy_description" not in tool.validation_data

    def test_check_criteria_3_fragment_matches_uppercase_in_description(self) -> None:
        # Description in uppercase: "METAGENOMICS TOOL" must match re.IGNORECASE pattern
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "METAGENOMICS TOOL"})
        pat = re.compile(r"(?<![A-Za-z])metage[a-z]*(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_3() is True

    def test_check_criteria_3_fragment_matches_mixed_case_in_description(self) -> None:
        # "Metagenomics" (title case) in description must match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "Metagenomics analysis tool"})
        pat = re.compile(r"(?<![A-Za-z])metage[a-z]*(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(folder, strict_kw=[], frag_patterns=[pat])
        assert tool.check_criteria_3() is True

    def test_check_criteria_3_strict_does_not_match_substring_in_description(self) -> None:
        # "ITS" must NOT match when it appears inside a longer word like "Inherits"
        tmp_path = self.tmp_path
        folder = _make_tool_folder(
            tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "Inherits properties from base"}
        )
        tool = _make_tool(folder, strict_kw=["ITS"], frag_patterns=[])
        assert tool.check_criteria_3() is False

    def test_check_criteria_3_strict_does_not_match_word_containing_acronym(self) -> None:
        # "MAG" must NOT match "image" or "magnitude" — only standalone word
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "image magnitude processing"})
        tool = _make_tool(folder, strict_kw=["MAG"], frag_patterns=[])
        assert tool.check_criteria_3() is False

    def test_check_criteria_3_strict_matches_acronym_inside_compound_word(self) -> None:
        # "xOTUanalysis" contains uppercase "OTU" → strict case-sensitive search must match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "xOTUanalysis pipeline"})
        tool = _make_tool(folder, strict_kw=["OTU"], frag_patterns=[])
        assert tool.check_criteria_3() is True
        assert tool.validation_data.get("biotools_description") == "OTU"

    def test_check_criteria_3_strict_does_not_match_lowercase_in_compound_word(self) -> None:
        # "xotuanalysis" contains "otu" in lowercase → must NOT match "OTU" (case-sensitive)
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "xotuanalysis pipeline"})
        tool = _make_tool(folder, strict_kw=["OTU"], frag_patterns=[])
        assert tool.check_criteria_3() is False

    def test_check_criteria_3_strict_matches_acronym_with_suffix(self) -> None:
        # "OTUs" contains uppercase "OTU" → must match
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "OTUs clustering analysis"})
        tool = _make_tool(folder, strict_kw=["OTU"], frag_patterns=[])
        assert tool.check_criteria_3() is True

    def test_check_criteria_3_strict_does_not_match_lowercase_with_suffix(self) -> None:
        # "motus" contains "otu" in lowercase → must NOT match "OTU" (case-sensitive)
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools={**SAMPLE_BIOTOOLS, "description": "motus profiling tool"})
        tool = _make_tool(folder, strict_kw=["OTU"], frag_patterns=[])
        assert tool.check_criteria_3() is False

    # ------------------------------------------------------------------ run_checks

    def test_run_checks_returns_true_and_sets_keep_on_criteria_1_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biotools=SAMPLE_BIOTOOLS)
        tool = _make_tool(folder, target_topics=["Genomics"])
        assert tool.run_checks() is True
        assert tool.keep is True

    def test_run_checks_returns_true_and_sets_keep_on_criteria_2_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, biocontainers={"keywords": ["FASTA"]})
        tool = _make_tool(
            folder,
            target_topics=[],
            target_ops=[],
            strict_kw=["FASTA"],
            frag_patterns=[],
        )
        assert tool.run_checks() is True
        assert tool.keep is True

    def test_run_checks_returns_true_and_sets_keep_on_criteria_3_match(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path, galaxy={"description": "variant detection tool"})
        pat = re.compile(r"(?<![A-Za-z])variant(?![A-Za-z])", re.IGNORECASE)
        tool = _make_tool(
            folder,
            target_topics=[],
            target_ops=[],
            strict_kw=[],
            frag_patterns=[pat],
        )
        assert tool.run_checks() is True
        assert tool.keep is True

    def test_run_checks_returns_false_and_sets_keep_false_when_all_fail(self) -> None:
        tmp_path = self.tmp_path
        folder = _make_tool_folder(tmp_path)
        tool = _make_tool(
            folder,
            target_topics=[],
            target_ops=[],
            strict_kw=[],
            frag_patterns=[],
        )
        assert tool.run_checks() is False
        assert tool.keep is False


# ===========================================================================
#  TestToolSet  —  methods in definition order
# ===========================================================================


class TestToolSet(RsecTestCase):
    """Tests for the ToolSet class defined in extract_rsec.py."""

    # ------------------------------------------------------------------ __init__

    def test_init_sets_root_dir(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert ts.root_dir == tmp_path

    def test_init_output_dir_derived_from_json_out(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert ts.output_dir == tmp_path / "infos"

    def test_init_report_txt_out_in_output_dir(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert ts.report_txt_out.parent == ts.output_dir

    def test_init_report_counts_all_zero(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        for v in ts.report_counts.values():
            assert v == 0

    def test_init_tools_list_empty(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert ts.tools == []

    def test_init_kw_data_loaded_from_file(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert "operations" in ts.kw_data
        assert "topics" in ts.kw_data

    # ------------------------------------------------------------------ _prepare_output_dir

    def test_prepare_output_dir_creates_directory(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        assert not ts.output_dir.exists()
        ts._prepare_output_dir()
        assert ts.output_dir.is_dir()

    def test_prepare_output_dir_removes_existing_output_files(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts.output_dir.mkdir(parents=True)
        stale = ts.json_out
        stale.write_text("{}")
        ts._prepare_output_dir()
        assert not stale.exists()

    def test_prepare_output_dir_is_idempotent(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts._prepare_output_dir()
        ts._prepare_output_dir()  # second call must not raise
        assert ts.output_dir.is_dir()

    # ------------------------------------------------------------------ run_filtering

    def test_run_filtering_counts_all_tool_folders(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        _make_tool_folder(tmp_path, "tool_1")
        _make_tool_folder(tmp_path, "tool_2")
        _make_tool_folder(tmp_path, "tool_3")
        ts = _make_toolset(tmp_path, kw_file=kw)
        ts.run_filtering()
        assert ts.report_counts["total_folders"] == 3

    def test_run_filtering_keeps_matching_tool_in_validated_json(self) -> None:
        kw_content = {
            "edam": {"operations": [], "topics": ["Genomics"]},
            "keywords": [],
            "acronyms": [],
        }
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path, content=kw_content)
        _make_tool_folder(tmp_path, "good_tool", biotools=SAMPLE_BIOTOOLS)
        _make_tool_folder(tmp_path, "bad_tool")
        ts = _make_toolset(tmp_path, kw_file=kw)
        ts.run_filtering()
        validated = json.loads(ts.json_out.read_text())
        ids = [v["tool_id"] for v in validated]
        assert "good_tool" in ids
        assert "bad_tool" not in ids

    def test_run_filtering_deletes_rejected_folders(self) -> None:
        kw_content = {
            "edam": {"operations": [], "topics": []},
            "keywords": [],
            "acronyms": [],
        }
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path, content=kw_content)
        doomed = _make_tool_folder(tmp_path, "doomed")
        ts = _make_toolset(tmp_path, kw_file=kw)
        ts.run_filtering()
        assert not doomed.exists()

    def test_run_filtering_does_not_delete_output_dir(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        ts = _make_toolset(tmp_path, kw_file=kw)
        ts.run_filtering()
        assert ts.output_dir.is_dir()

    def test_run_filtering_increments_filter_1_counter_for_edam_match(self) -> None:
        tmp_path = self.tmp_path
        kw_content = {
            "edam": {"operations": [], "topics": ["Genomics"]},
            "keywords": [],
            "acronyms": [],
        }
        kw = _make_keywords_yaml(tmp_path, content=kw_content)
        _make_tool_folder(tmp_path, "edam_tool", biotools=SAMPLE_BIOTOOLS)
        ts = _make_toolset(tmp_path, kw_file=kw)
        ts.run_filtering()
        assert ts.report_counts["validated_filter_1"] == 1

    # ------------------------------------------------------------------ _write_json

    def test_write_json_creates_valid_json_file(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        out = tmp_path / "out.json"
        ts._write_json([{"a": 1}], out)
        assert json.loads(out.read_text()) == [{"a": 1}]

    def test_write_json_overwrites_existing_file(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        out = tmp_path / "out.json"
        out.write_text("[1, 2, 3]")
        ts._write_json([{"new": True}], out)
        assert json.loads(out.read_text()) == [{"new": True}]

    def test_write_json_handles_empty_list(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        out = tmp_path / "empty.json"
        ts._write_json([], out)
        assert json.loads(out.read_text()) == []

    # ------------------------------------------------------------------ _finalize

    def test_finalize_deletes_listed_folders(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts._prepare_output_dir()
        folder = tmp_path / "to_delete"
        folder.mkdir()
        ts._finalize([folder])
        assert not folder.exists()

    def test_finalize_writes_report_file(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts._prepare_output_dir()
        ts.report_counts["total_folders"] = 10
        ts.report_counts["validated_filter_1"] = 4
        ts.report_counts["validated_filter_2"] = 2
        ts.report_counts["validated_filter_3"] = 1
        ts._finalize([])
        content = ts.report_txt_out.read_text()
        assert "Total: 10" in content
        assert "Kept: 7" in content

    def test_finalize_does_not_raise_if_folder_already_deleted(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts._prepare_output_dir()
        phantom = tmp_path / "phantom"
        # do NOT create it — _finalize must handle missing folder gracefully
        ts._finalize([phantom])  # should not raise

    # ------------------------------------------------------------------ _write_report

    def test_write_report_contains_all_required_fields(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        ts.report_counts = {
            "total_folders": 20,
            "validated_filter_1": 5,
            "validated_filter_2": 3,
            "validated_filter_3": 2,
            "did_not_pass_any": 10,
        }
        report_file = tmp_path / "report.txt"
        ts._write_report(report_file, deleted=10, kept=10)
        content = report_file.read_text()
        assert "Total: 20" in content
        assert "Kept: 10" in content
        assert "Deleted: 10" in content
        assert "Filter 1: 5" in content
        assert "Filter 2: 3" in content
        assert "Filter 3: 2" in content

    def test_write_report_creates_file_if_missing(self) -> None:
        tmp_path = self.tmp_path
        ts = _make_toolset(tmp_path)
        report_file = tmp_path / "new_report.txt"
        assert not report_file.exists()
        ts._write_report(report_file, deleted=0, kept=0)
        assert report_file.exists()


# ===========================================================================
#  TestCloneRsecData  —  function in utils.py (imported in extract_rsec)
#  All subprocess/git calls are mocked so no network or git is needed.
# ===========================================================================


class TestCloneRsecData(RsecTestCase):
    """Tests for utils.clone_rsec_data."""

    def _patch_run(self, return_value: bool = True) -> Any:
        return patch("utils.run_command_rsec", return_value=return_value)

    # ------------------------------------------------------------------ early-exit failure paths

    def test_returns_false_when_clone_command_fails(self) -> None:
        tmp_path = self.tmp_path
        with self._patch_run(False):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=tmp_path / "temp",
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )
        assert result is False

    def test_returns_false_when_sparse_checkout_config_fails(self) -> None:
        # The git-config call (core.sparseCheckout) must fail → False expected.
        # We make run_command_rsec return False whenever "config" appears in the command,
        # True otherwise. This is order-independent.
        def side_effect(cmd: Any, cwd: Any = None) -> bool:
            return "config" not in cmd

        tmp_path = self.tmp_path
        with patch("utils.run_command_rsec", side_effect=side_effect):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=tmp_path / "temp",
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )
        assert result is False

    def test_returns_false_when_checkout_command_fails(self) -> None:
        # The final "git checkout" call must fail → False expected.
        # We make run_command_rsec return False only when "checkout" is the git sub-command.
        def side_effect(cmd: Any, cwd: Any = None) -> bool:
            return "checkout" not in cmd

        tmp_path = self.tmp_path
        with patch("utils.run_command_rsec", side_effect=side_effect):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=tmp_path / "temp",
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )
        assert result is False

    def test_returns_false_when_subdir_absent_after_checkout(self) -> None:
        """All git commands succeed but the expected subdir was never created."""
        tmp_path = self.tmp_path
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / ".git" / "info").mkdir(parents=True)
        # No "data/" subdirectory is created, simulating a git sparse-checkout
        # that returned nothing.
        with self._patch_run(True):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=temp_dir,
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )
        assert result is False

    # ------------------------------------------------------------------ side-effects on filesystem

    def test_removes_existing_target_dir_before_cloning(self) -> None:
        tmp_path = self.tmp_path
        target = tmp_path / "target"
        target.mkdir()
        stale = target / "old.txt"
        stale.write_text("stale")
        with self._patch_run(False):  # clone fails, but target must still be wiped
            clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=tmp_path / "temp",
                target_dir=target,
                subdir_in_repo="data",
            )
        assert not target.exists()

    def test_removes_leftover_temp_dir_before_cloning(self) -> None:
        tmp_path = self.tmp_path
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        leftover = temp_dir / "leftover.txt"
        leftover.write_text("leftover")
        with self._patch_run(False):
            clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=temp_dir,
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )
        # temp dir is cleaned up at the start
        assert not temp_dir.exists()

    def test_writes_sparse_checkout_file_with_correct_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp) / "temp"
            temp_dir.mkdir()
            # On crée manuellement le dossier .git/info pour le test
            (temp_dir / ".git" / "info").mkdir(parents=True)

            captured_contents = []

            def mock_run(cmd: Any, cwd: Any = None) -> bool:
                sc_file = temp_dir / ".git" / "info" / "sparse-checkout"
                if sc_file.exists():
                    captured_contents.append(sc_file.read_text(encoding="utf-8"))
                return True

            with patch("utils.run_command_rsec", side_effect=mock_run):
                clone_rsec_data(
                    repo_url="https://example.com/repo.git",
                    temp_dir=temp_dir,
                    target_dir=Path(tmp) / "target",
                    subdir_in_repo="mydata",
                )

            self.assertTrue(any("/mydata\n" in c for c in captured_contents))

    # ------------------------------------------------------------------ happy path

    def test_returns_true_and_moves_subdir_to_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp) / "temp"
            temp_dir.mkdir()
            (temp_dir / ".git" / "info").mkdir(parents=True)

            # On simule un fichier qui aurait été téléchargé par git
            subdir = temp_dir / "data"
            subdir.mkdir()
            (subdir / "sample.json").write_text("{}")

            target = Path(tmp) / "target"

            with patch("utils.run_command_rsec", return_value=True):
                result = clone_rsec_data(
                    repo_url="https://example.com/repo.git",
                    temp_dir=temp_dir,
                    target_dir=target,
                    subdir_in_repo="data",
                )

            self.assertTrue(result)
            self.assertTrue(target.is_dir())
            self.assertTrue((target / "sample.json").exists())

    def test_cleans_up_temp_dir_after_success(self) -> None:
        tmp_path = self.tmp_path
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()
        (temp_dir / ".git" / "info").mkdir(parents=True)
        (temp_dir / "data").mkdir()

        with self._patch_run(True):
            clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=temp_dir,
                target_dir=tmp_path / "target",
                subdir_in_repo="data",
            )

        assert not temp_dir.exists()

    def test_return_value_is_bool(self) -> None:
        # clone_rsec_data must return a bool so callers can do `if not clone_rsec_data(...)`.
        # Returning None silently would make the __main__ guard ineffective.
        with self._patch_run(False):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=self.tmp_path / "temp",
                target_dir=self.tmp_path / "target",
                subdir_in_repo="data",
            )
        assert isinstance(result, bool)

    def test_failure_returns_false_not_none(self) -> None:
        # Explicitly False (not None): `if not clone_rsec_data(...)` must trigger sys.exit on failure
        with self._patch_run(False):
            result = clone_rsec_data(
                repo_url="https://example.com/repo.git",
                temp_dir=self.tmp_path / "temp",
                target_dir=self.tmp_path / "target",
                subdir_in_repo="data",
            )
        assert result is False


# ===========================================================================
#  TestLoadKeywordsFromYaml  —  function in utils.py (imported in extract_rsec)
# ===========================================================================


class TestLoadKeywordsFromYaml(RsecTestCase):
    """Tests for utils.load_keywords_from_yaml."""

    # ------------------------------------------------------------------ return structure

    def test_returns_dict_with_all_required_keys(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        assert set(result.keys()) == {"operations", "topics", "compiled_fragments", "stricts", "compiled_stricts"}

    def test_operations_list_loaded_correctly(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        assert "Sequence alignment" in result["operations"]
        assert "Variant calling" in result["operations"]

    def test_topics_list_loaded_correctly(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        assert "Genomics" in result["topics"]
        assert "Proteomics" in result["topics"]

    def test_compiled_fragments_are_compiled_regex_patterns(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        for pat in result["compiled_fragments"]:
            assert hasattr(pat, "search"), "Expected a compiled regex pattern"

    def test_stricts_are_all_uppercase(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        for s in result["stricts"]:
            assert s == s.upper(), f"Strict keyword '{s}' is not uppercased"

    def test_stricts_include_acronyms_from_yaml(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        assert "FASTA" in result["stricts"]
        assert "VCF" in result["stricts"]

    def test_compiled_stricts_are_compiled_regex_patterns(self) -> None:
        tmp_path = self.tmp_path
        kw = _make_keywords_yaml(tmp_path)
        result = load_keywords_from_yaml(kw)
        for pat in result["compiled_stricts"]:
            assert hasattr(pat, "search"), "Expected a compiled regex pattern"

    # ------------------------------------------------------------------ edge cases

    def test_raises_file_not_found_for_missing_file(self) -> None:
        tmp_path = self.tmp_path
        with self.assertRaises(FileNotFoundError):
            load_keywords_from_yaml(tmp_path / "nonexistent.yml")

    def test_invalid_regex_in_keywords_is_skipped_with_warning(self) -> None:
        tmp_path = self.tmp_path
        content = {
            "edam": {"operations": [], "topics": []},
            "keywords": ["valid_pattern", "[invalid_regex"],
            "acronyms": [],
        }
        kw = _make_keywords_yaml(tmp_path, content=content)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = load_keywords_from_yaml(kw)
        captured = buf.getvalue()
        assert "WARNING" in captured
        assert len(result["compiled_fragments"]) == 1  # only valid pattern compiled

    def test_empty_yaml_returns_all_empty_collections(self) -> None:
        tmp_path = self.tmp_path
        content = {"edam": {"operations": [], "topics": []}, "keywords": [], "acronyms": []}
        kw = _make_keywords_yaml(tmp_path, content=content)
        result = load_keywords_from_yaml(kw)
        assert result["operations"] == []
        assert result["topics"] == []
        assert result["compiled_fragments"] == []
        assert result["stricts"] == []
        assert result["compiled_stricts"] == []

    def test_stricts_are_deduplicated(self) -> None:
        tmp_path = self.tmp_path
        content = {
            "edam": {"operations": [], "topics": []},
            "keywords": [],
            "acronyms": ["FASTA", "fasta", "FASTA"],  # duplicates
        }
        kw = _make_keywords_yaml(tmp_path, content=content)
        result = load_keywords_from_yaml(kw)
        assert result["stricts"].count("FASTA") == 1


# ===========================================================================
#  TestGenerateTsvSummary  —  function in utils.py (imported in extract_rsec)
# ===========================================================================


class TestGenerateTsvSummary(RsecTestCase):
    """Tests for utils.generate_tsv_summary."""

    def _write_json(self, path: Path, records: list) -> None:
        path.write_text(json.dumps(records), encoding="utf-8")

    def _read_tsv(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f, delimiter="\t"))

    # ------------------------------------------------------------------ file creation

    def test_creates_tsv_file(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1"}])
        generate_tsv_summary(json_path, tsv_path)
        assert tsv_path.exists()

    def test_tsv_has_expected_headers(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1"}])
        generate_tsv_summary(json_path, tsv_path)
        rows = self._read_tsv(tsv_path)
        for col in ["tool_id", "biotools_id", "filtered_on", "reason", "to_keep", "description"]:
            assert col in rows[0], f"Column '{col}' missing from TSV"

    def test_tsv_row_count_matches_input(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        records = [{"tool_id": f"tool_{i}"} for i in range(7)]
        self._write_json(json_path, records)
        generate_tsv_summary(json_path, tsv_path)
        assert len(self._read_tsv(tsv_path)) == 7

    # ------------------------------------------------------------------ filtered_on / reason mapping

    def test_filtered_on_edam_topics(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "EDAM_topics": "Genomics"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "EDAM_topics"
        assert "Genomics" in row["reason"]

    def test_filtered_on_edam_operation(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "EDAM_operation": "Alignment"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "EDAM_operation"

    def test_filtered_on_biocontainers_keywords(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "biocontainers_keywords": "FASTA"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "biocontainers_keywords"

    def test_filtered_on_biotools_description(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "biotools_description": "VCF"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "biotools_description"

    def test_filtered_on_biocontainers_description(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "biocontainers_description": "variant"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "biocontainers_description"

    def test_filtered_on_galaxy_description(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1", "galaxy_description": "genomics"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "galaxy_description"

    def test_unknown_reason_when_no_criteria_key_present(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1"}])
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "UNKNOWN_REASON"

    def test_criteria_priority_edam_topics_over_operation(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        # Both keys present: EDAM_topics should win (it's first in CRITERIA_KEYS)
        self._write_json(
            json_path,
            [{"tool_id": "t1", "EDAM_topics": "Genomics", "EDAM_operation": "Alignment"}],
        )
        generate_tsv_summary(json_path, tsv_path)
        row = self._read_tsv(tsv_path)[0]
        assert row["filtered_on"] == "EDAM_topics"

    # ------------------------------------------------------------------ description fallback

    def test_description_uses_biotools_first(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(
            json_path,
            [
                {
                    "tool_id": "t1",
                    "biotools_description_full": "BioTools desc",
                    "biocontainers_description_full": "BioContainers desc",
                }
            ],
        )
        generate_tsv_summary(json_path, tsv_path)
        assert self._read_tsv(tsv_path)[0]["description"] == "BioTools desc"

    def test_description_falls_back_to_biocontainers(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(
            json_path,
            [
                {
                    "tool_id": "t1",
                    "biotools_description_full": "",
                    "biocontainers_description_full": "BioContainers desc",
                }
            ],
        )
        generate_tsv_summary(json_path, tsv_path)
        assert self._read_tsv(tsv_path)[0]["description"] == "BioContainers desc"

    def test_description_falls_back_to_na_when_all_empty(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1"}])
        generate_tsv_summary(json_path, tsv_path)
        assert self._read_tsv(tsv_path)[0]["description"] == "N/A"

    # ------------------------------------------------------------------ error / edge cases

    def test_does_nothing_for_empty_list(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [])
        generate_tsv_summary(json_path, tsv_path)
        assert not tsv_path.exists()

    def test_prints_error_and_returns_for_missing_json(self) -> None:
        tmp_path = self.tmp_path
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            generate_tsv_summary(tmp_path / "missing.json", tmp_path / "out.tsv")
        out = buf.getvalue()
        assert "ERROR" in out

    def test_prints_error_and_returns_for_invalid_json(self) -> None:
        tmp_path = self.tmp_path
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            generate_tsv_summary(bad, tmp_path / "out.tsv")
        out = buf.getvalue()
        assert "ERROR" in out

    def test_to_keep_column_always_true(self) -> None:
        tmp_path = self.tmp_path
        json_path = tmp_path / "v.json"
        tsv_path = tmp_path / "out.tsv"
        self._write_json(json_path, [{"tool_id": "t1"}, {"tool_id": "t2"}])
        generate_tsv_summary(json_path, tsv_path)
        for row in self._read_tsv(tsv_path):
            assert row["to_keep"] == "True"
