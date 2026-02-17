from pathlib import Path
from typing import List
import re

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

# # Global variables (initialized in __main__)
# ROOT_DIRECTORY: Path
# OUTPUT_DIR: Path
# REPORTING_FILE: Path
# VALIDATED_METADATA_FILE: Path
# FAILED_METADATA_FILE: Path
# TSV_OUTPUT_FILE: Path

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
