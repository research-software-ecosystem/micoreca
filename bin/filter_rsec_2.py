#!/usr/bin/env python
import os
import json
import shutil
import re 
import sys 
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import csv 

# Attempt to import YAML. If it fails, sets yaml to None.
try:
    import yaml
except ImportError:
    yaml = None

# --- Configuration paths (ROBUST PATHS) ---
SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_BIN_DIR = SCRIPT_PATH.parent
# BASE_DIR is the repository root (parent directory of 'bin')
BASE_DIR = SCRIPT_BIN_DIR.parent 

# Directory containing the RSEC data to be filtered (micoreca/content/rsec)
RSEC_DIR = BASE_DIR / "content" / "rsec"
KEYWORDS_FILEPATH = BASE_DIR / "keywords.yml"


# Global variables for file paths (initialized in __main__)
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
# OPTIMIZATION: list for pre-compiled strict word boundary regex patterns
COMPILED_STRICT_PATTERNS: List[re.Pattern] = [] 

# --- CRITERIA KEYS ( matches the filtering priority order explained in the README) ---
# Keys in the JSON that indicate a successful filter match.
CRITERIA_KEYS = [
    "EDAM_topics",
    "EDAM_operation",
    "biocontainers_keywords",
    "biotools_description",
    "biocontainers_description",
    "galaxy_description"
]

# --- REASON MAPPING (Maps internal keys to desired descriptive strings for the TSV) ---
REASON_MAPPING = {
    "EDAM_topics": "{value} in EDAM Topics",
    "EDAM_operation": "{value} in EDAM Operations",
    "biocontainers_keywords": "{value} in BioContainers keywords",
    "biotools_description": "{value} in bio.tools description",
    "biocontainers_description": "{value} in BioContainers description",
    "galaxy_description": "{value} in Galaxy description",
}


def load_keywords_from_yaml(filepath: Path) -> Dict[str, Any]:
    """
    Loads EDAM terms, fragment keywords (REGEX), and strict acronyms from the YAML file.
    """
    if yaml is None:
        raise ImportError("PyYAML is required but not installed (pip install pyyaml).")

    if not filepath.exists():
        raise FileNotFoundError(f"Keywords file not found at: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading YAML file: {e}")

    edam_data = data.get('edam', {})
    
    # 1. EDAM terms
    target_operations = edam_data.get('operations', [])
    target_topics = edam_data.get('topics', [])

    # 2. Fragments (e.g., 'metage.*')
    fragment_patterns_raw = data.get('keywords', [])
    compiled_fragments = []
    
    for pattern_raw in fragment_patterns_raw:
        if isinstance(pattern_raw, str) and pattern_raw.strip():
            try:
                # Compile regex patterns (case-insensitive)
                compiled_fragments.append(re.compile(pattern_raw, re.IGNORECASE))
            except re.error as e:
                print(f"  [WARNING] Could not compile regex pattern '{pattern_raw}': {e}")

    # 3. Acronyms (strict search, case-sensitive check, but stored as lower case match)
    strict_keywords_list = [str(k).strip() for k in data.get('acronyms', []) if isinstance(k, str) and k.strip()]
    
    # Add potentially missed "strict" keywords (like MAGs) from 'keywords' that are ALL CAPS
    for kw in fragment_patterns_raw:
        if isinstance(kw, str) and kw.strip() and not any(c in kw for c in ['.', '*', '+', '?']):
             if kw.upper() == kw: 
                strict_keywords_list.append(kw.strip())

    strict_keywords_list = list(set([k.strip().upper() for k in strict_keywords_list if k.strip()]))
    
    # NEW OPTIMIZATION: Pre-compile strict acronym patterns for word boundary search
    compiled_stricts = []
    for strict_ref in strict_keywords_list:
        # We need the word boundary \b and escape to handle special characters
        regex_pattern = re.compile(r'\b' + re.escape(strict_ref) + r'\b')
        compiled_stricts.append(regex_pattern)


    return {
        "operations": target_operations,
        "topics": target_topics,
        "compiled_fragments": compiled_fragments,
        "stricts": strict_keywords_list, # List of strict keywords (case-sensitive reference)
        "compiled_stricts": compiled_stricts # List of pre-compiled word boundary regex
    }

# --------------------------------------------------------------------------
#                           TSV GENERATION FUNCTION
# --------------------------------------------------------------------------

def generate_tsv_summary(json_path: Path, tsv_path: Path):
    """
    Loads validated metadata and writes the summary to a TSV file,
    applying description priority and reason formatting.
    """
    
    # 1. Load JSON data
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data: List[Dict[str, Any]] = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Input JSON file '{json_path}' not found. Cannot generate TSV.")
        return
    except json.JSONDecodeError:
        print(f"ERROR: Input file '{json_path}' is not valid JSON. Cannot generate TSV.")
        return
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading JSON: {e}")
        return
    
    if not isinstance(data, list) or not data:
        print("ℹWARNING: JSON content is empty or not a list. Skipping TSV generation.")
        return

    # 2. Prepare summary data
    summary_data: List[Dict[str, str]] = []
    
    # Define fixed column order (biotools_id added)
    fieldnames = [
        'tool_id', 
        'biotools_id', 
        'filtered_on', 
        'reason',      
        'to_keep',
        'EDAM_operations',
        'EDAM_topics',
        'description', 
        'has_biocontainers_infos', 
        'has_biotools_infos', 
        'has_galaxy_infos' 
    ]
    
    for item in data:
        tool_id = item.get('tool_id', 'N/A')
        
        # Extract biotools ID (can be empty string if not found, based on Tool class logic)
        biotools_id = item.get('biotools_id', '')
        
        # Extract fields for reporting
        edam_operations = item.get('EDAM_operations_full', '')
        edam_topics = item.get('EDAM_topics_full', '')
        
        # Extract file presence flags
        has_biocontainers = str(item.get('has_biocontainers_infos', False))
        has_biotools = str(item.get('has_biotools_infos', False))
        has_galaxy = str(item.get('has_galaxy_infos', False))
        
        # Logic: Description Priority (biotools > biocontainers > galaxy)
        description = item.get('biotools_description_full', '') or \
                      item.get('biocontainers_description_full', '') or \
                      item.get('galaxy_description_full', '') or \
                      'N/A - No description found in any prioritized file.'

        entry = {
            'tool_id': tool_id,
            'biotools_id': biotools_id, # Can be "" if not found
            'filtered_on': "UNKNOWN_REASON",
            'reason': "N/A - Not Matched",
            'to_keep': '',
            'EDAM_operations': edam_operations,
            'EDAM_topics': edam_topics,
            'description': description, 
            'has_biocontainers_infos': has_biocontainers, 
            'has_biotools_infos': has_biotools, 
            'has_galaxy_infos': has_galaxy 
        }
        
        # Logic: Reason Formatting (Iterate over CRITERIA_KEYS in priority order)
        for key in CRITERIA_KEYS:
            match_value = item.get(key)
            if match_value:
                entry['filtered_on'] = key
                
                # Format the reason using the global REASON_MAPPING dictionary
                reason_template = REASON_MAPPING.get(key, "Match found on key: {key} (value: {value})")
                
                # Format the descriptive string
                formatted_value = str(match_value)
                entry['reason'] = reason_template.format(value=formatted_value)
                
                break # Stop at the first successful criterion
                
        summary_data.append(entry)


    # 3. Write the TSV file
    try:
        with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=fieldnames, 
                delimiter='\t', 
                extrasaction='ignore'
            )
            
            writer.writeheader()
            writer.writerows(summary_data)

        print(f"\nSummary successfully created (Keys retained).")
        print(f"TSV file created: {tsv_path.name}")
        print(f"Path: {tsv_path.relative_to(BASE_DIR)}")
        print(f"Number of tool entries written: {len(summary_data)}")

    except IOError as e:
        print(f"ERROR writing TSV file: {e}")

# -------------------------------------------------------------
#                  TOOL class 
# -------------------------------------------------------------

class Tool:
    """
    Represents a single tool (folder) and holds its metadata 
    and validation status.
    """
    
    def __init__(self, folder_path: Path):
        self.folder_path = folder_path
        self.tool_id = folder_path.name
        self.keep = False
        self.validation_data: Dict[str, Any] = {"tool_id": self.tool_id}
        
        # OPTIMIZATION: Consolidated metadata storage
        self.metadata: Dict[str, Dict[str, Any] | List[Any]] = {} 
        self.descriptions: Dict[str, str] = {}
        
        # 1. Centralized loading of all metadata files
        self._load_all_metadata()

        # 2. Assign descriptions for easy access in checks
        self.biocontainers_description = self.descriptions.get('biocontainers', '')
        self.biotools_description = self.descriptions.get('biotools', '')
        self.galaxy_description = self.descriptions.get('galaxy', '')
        
        # 3. Extract and store full EDAM, ID, and Descriptions for reporting/TSV
        self._store_full_report_metadata()

    def _safe_load(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """Helper to safely load JSON or YAML content."""
        try:
            with open(filepath, 'r', encoding='utf-8') as fh:
                if filepath.suffix in ['.json']: 
                    return json.load(fh)
                elif filepath.suffix in ['.yaml'] and yaml: 
                    return yaml.safe_load(fh)
        except Exception as e:
            # Coherence: Log the error but don't stop the process
            print(f"  [Error Loading] {filepath.name}: {e}")
            pass
        return None

    def _load_all_metadata(self):
        """
        Loads all required metadata files (biotools, biocontainers, galaxy) 
        and stores the data once, storing descriptions in validation_data 
        for priority calculation in TSV.
        """
        
        # Track file presence for reporting
        self.validation_data['has_biocontainers_infos'] = False
        self.validation_data['has_biotools_infos'] = False
        self.validation_data['has_galaxy_infos'] = False
        
        # Initialize description fields for priority logic in TSV generation
        self.validation_data['biotools_description_full'] = ''
        self.validation_data['biocontainers_description_full'] = ''
        self.validation_data['galaxy_description_full'] = ''


        # Load biotools.json (mandatory for Check 1)
        biotools_files = list(self.folder_path.glob("*biotools.json"))
        if biotools_files:
            data = self._safe_load(biotools_files[0])
            if data and isinstance(data, dict):
                self.metadata['biotools'] = data
                description = data.get('description', '')
                self.descriptions['biotools'] = description
                self.validation_data['has_biotools_infos'] = True
                # Store for description priority in TSV (Highest Priority)
                self.validation_data['biotools_description_full'] = description

        # Load biocontainers.yaml
        biocontainers_files = list(self.folder_path.glob("*.biocontainers.yaml"))
        if biocontainers_files:
            data = self._safe_load(biocontainers_files[0])
            if data and isinstance(data, dict):
                self.metadata['biocontainers'] = data
                description = data.get('description', '')
                self.descriptions['biocontainers'] = description
                self.validation_data['has_biocontainers_infos'] = True
                # Store for description priority in TSV (Second Priority)
                self.validation_data['biocontainers_description_full'] = description

        # Load galaxy.json
        galaxy_files = list(self.folder_path.glob("*.galaxy.json"))
        if galaxy_files:
            data = self._safe_load(galaxy_files[0])
            if data and isinstance(data, dict):
                self.metadata['galaxy'] = data
                description = data.get('description', '')
                self.descriptions['galaxy'] = description
                self.validation_data['has_galaxy_infos'] = True
                # Store for description priority in TSV (Lowest Priority)
                self.validation_data['galaxy_description_full'] = description
        

    def _extract_edam_terms(self, data: Dict[str, Any], key: str) -> str:
        """
        Extracts and concatenates EDAM terms (operations or topics), 
        separated by a comma and a space (', ').
        """
        terms = set()
        
        if key == 'function' and 'function' in data and isinstance(data['function'], list):
            for func in data['function']:
                if 'operation' in func and isinstance(func['operation'], list):
                    for op in func['operation']:
                        if 'term' in op:
                            terms.add(op['term'])
                            
        elif key == 'topic' and 'topic' in data and isinstance(data['topic'], list):
            for topic in data['topic']:
                if 'term' in topic:
                    terms.add(topic['term'])
                    
        return ", ".join(sorted(list(terms)))

    def _store_full_report_metadata(self):
        """
        Extracts all EDAM operations, topics, and CRITICAL: the biotools ID 
        from cached biotools.json for the TSV.
        """
        data = self.metadata.get('biotools')
        
        # 1. biotools ID (CRITICAL: Default to "" if not found)
        # We ensure it does NOT default to self.tool_id
        biotools_id = data.get('biotoolsID', '') if data else ''
        self.validation_data['biotools_id'] = biotools_id
        
        if not data: 
            # If no biotools.json, EDAM fields remain empty
            self.validation_data['EDAM_operations_full'] = ''
            self.validation_data['EDAM_topics_full'] = ''
            return

        # 2. Full EDAM Operations List
        full_operations = self._extract_edam_terms(data, 'function')
        self.validation_data['EDAM_operations_full'] = full_operations
        
        # 3. Full EDAM Topics List
        full_topics = self._extract_edam_terms(data, 'topic')
        self.validation_data['EDAM_topics_full'] = full_topics
        

    # --- Filtering criteria checks ---

    def check_criteria_1(self) -> bool:
        """
        Check for EDAM operations or topics in the cached biotools.json metadata.
        """
        data = self.metadata.get('biotools')
        if not data: return False
        
        # Check EDAM operations
        if 'function' in data and isinstance(data['function'], list):
            for func in data['function']:
                if 'operation' in func and isinstance(func['operation'], list):
                    for operation in func['operation']:
                        if 'term' in operation and operation['term'] in TARGET_OPERATIONS:
                            self.validation_data['EDAM_operation'] = operation['term'] 
                            return True
                            
        # Check EDAM topics
        if 'topic' in data and isinstance(data['topic'], list):
            for topic in data['topic']:
                if 'term' in topic and topic['term'] in TARGET_TOPICS:
                    self.validation_data['EDAM_topics'] = topic['term']
                    return True
                            
        return False

    def check_criteria_2(self) -> bool:
        """
        Check for strict acronyms or regex fragments in biocontainers YAML keywords.
        """
        data = self.metadata.get('biocontainers')
        if not data: return False

        file_keywords = data.get('keywords')
        if not file_keywords: return False
        
        candidates_with_case = [] 
        if isinstance(file_keywords, list):
            candidates_with_case = [str(x).strip() for x in file_keywords if x is not None]
        elif isinstance(file_keywords, str):
            candidates_with_case = [x.strip() for x in file_keywords.replace(';', ',').split(',') if x.strip()]

        # 1. Strict acronyms check (Using case-insensitive keyword list for fast check)
        for kw_case in candidates_with_case:
            if kw_case.upper() in STRICT_KEYWORDS: 
                # Store the original case keyword as the match value
                self.validation_data['biocontainers_keywords'] = kw_case 
                return True

        # 2. Regex checks
        for kw_case in candidates_with_case:
            kw_lower = kw_case.lower()
            for pattern in COMPILED_FRAGMENT_PATTERNS:
                match = pattern.search(kw_lower)
                if match: 
                    # Store the fragment that matched
                    self.validation_data['biocontainers_keywords'] = match.group(0)
                    return True
            
        return False

    def _search_keywords_in_content(self, content: str) -> str | None:
        """
        Searches the given string content for fragment patterns (regex) 
        or strict acronyms (pre-compiled regex), returning the match.
        """
        if not content: return None
        
        # 1. Strict acronym checks (word boundary search using pre-compiled patterns)
        for strict_ref_upper, pattern in zip(STRICT_KEYWORDS, COMPILED_STRICT_PATTERNS): 
            if pattern.search(content):
                # Return the acronym in its uppercase reference form (e.g., MAGS)
                return strict_ref_upper 
                
        # 2. Regex checks (fragment patterns)
        content_lower = content.lower()
        for pattern in COMPILED_FRAGMENT_PATTERNS:
            match = pattern.search(content_lower)
            if match:
                # Return the matched fragment
                return match.group(0)
                
        return None

    def check_criteria_3(self) -> bool:
        """Check for keywords in file descriptions (biocontainers, biotools, galaxy)."""
        
        # Check biocontainers description
        match = self._search_keywords_in_content(self.biocontainers_description)
        if match:
            self.validation_data['biocontainers_description'] = match
            return True
        
        # Check biotools description
        match = self._search_keywords_in_content(self.biotools_description)
        if match:
            self.validation_data['biotools_description'] = match
            return True

        # Check galaxy description
        match = self._search_keywords_in_content(self.galaxy_description)
        if match:
            self.validation_data['galaxy_description'] = match
            return True

        return False

    def run_checks(self) -> bool:
        """Runs the three filtering checks sequentially (stop at first match)."""
        print(f"\n-> Processing folder : {self.tool_id}")

        # Check 1: EDAM Terms (Highest Priority)
        if self.check_criteria_1():
            print("  [KEPT] CHECK 1 PASSED (JSON Term found).")
            self.keep = True
            return True
        
        # Check 2: YAML Keywords (Medium Priority)
        print("  [CHECK 2] Moving to secondary criterion (YAML Keywords)...")
        if self.check_criteria_2():
            print("  [KEPT] CHECK 2 PASSED.")
            self.keep = True
            return True

        # Check 3: Descriptions (Lowest Priority)
        print("  [CHECK 3] Moving to tertiary criterion (File Descriptions)...")
        if self.check_criteria_3():
            print("  [KEPT] CHECK 3 PASSED.")
            self.keep = True
            return True
        
        self.keep = False
        print("  [FINAL FAILURE] All checks failed.")
        return False

# -------------------------------------------------------------
#                  Toolset class
# -------------------------------------------------------------

class ToolSet:
    """
    Manages a collection of Tool objects, runs the filtering logic, 
    and handles reporting/file operations.
    """
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.tools: List[Tool] = []
        self.report_counts = {
            "total_folders": 0,
            "validated_filter_1": 0,
            "validated_filter_2": 0,
            "validated_filter_3": 0,
            "did_not_pass_any": 0
        }

    def _prepare_output_dir(self, output_dir: Path):
        """Creates the output directory and cleans up previous metadata files."""
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Output directory {output_dir.name}/ is ready.")
        except Exception as e:
            print(f"\n[CRITICAL ERROR] Failed to create output directory {output_dir.name}/. Error: {e}")
            
        # Clean up files *before* filtering starts
        for meta_file in [VALIDATED_METADATA_FILE, FAILED_METADATA_FILE, REPORTING_FILE, TSV_OUTPUT_FILE]:
            if meta_file.exists(): 
                meta_file.unlink()

    def _store_tool_metadata(self, tool_data: dict, metadata_file: Path):
        """Appends tool validation data to the specified JSON file."""
        data = []
        if metadata_file.exists():
            try:
                # Read content first in case the file was not cleaned up
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                if isinstance(content, list): data = content
            except Exception: 
                # If file exists but is corrupted, start fresh
                pass 
        
        data.append(tool_data)
        
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"  [META ERROR] Could not write metadata file ({metadata_file.name}) to {metadata_file.parent.name}/ : {e}")


    def run_filtering(self):
        self._prepare_output_dir(OUTPUT_DIR)
        subfolders_to_delete = []

        print(f"Starting filtering in : {self.root_dir}")
        print(f"Validated metadata will be stored in : {VALIDATED_METADATA_FILE.name}")
        print(f"Failed metadata (for audit) will be stored in : {FAILED_METADATA_FILE.name}")
        print(f"WARNING : Non-kept folders will be PERMANENTLY DELETED.")

        for item in self.root_dir.iterdir():
            if item.is_dir() and item.name != OUTPUT_DIR.name: # Ensure not to process the output directory
                self.report_counts["total_folders"] += 1
                
                tool = Tool(item)
                tool.run_checks()
                self.tools.append(tool)
                
                if tool.keep:
                    # Determine which criteria was met (used for reporting)
                    if 'EDAM_operation' in tool.validation_data or 'EDAM_topics' in tool.validation_data:
                        self.report_counts["validated_filter_1"] += 1 
                    elif 'biocontainers_keywords' in tool.validation_data:
                        self.report_counts["validated_filter_2"] += 1 
                    elif 'biocontainers_description' in tool.validation_data or 'biotools_description' in tool.validation_data or 'galaxy_description' in tool.validation_data:
                        self.report_counts["validated_filter_3"] += 1 

                    self._store_tool_metadata(tool.validation_data, VALIDATED_METADATA_FILE)
                else:
                    self.report_counts["did_not_pass_any"] += 1
                    subfolders_to_delete.append(item)
                    self._store_tool_metadata(tool.validation_data, FAILED_METADATA_FILE)

        self._finalize_operation(subfolders_to_delete)

    def _finalize_operation(self, subfolders_to_delete: List[Path]):
        """Prints final stats and performs folder deletion."""
        total_deleted = len(subfolders_to_delete)
        total_kept = sum(self.report_counts[k] for k in ['validated_filter_1', 'validated_filter_2', 'validated_filter_3'])

        print("\n" + "="*50)
        print(f"Total subfolders found : {self.report_counts['total_folders']}")
        print(f"Subfolders to KEEP (in the current directory) : {total_kept}") 
        print(f"Subfolders to DELETE : {total_deleted}")

        if subfolders_to_delete:
            print("\n--- Deleting non-kept folders ---")
            for folder in subfolders_to_delete:
                print(f"DELETING : {folder.name}")
                try:
                    shutil.rmtree(folder)
                except OSError as e:
                    print(f"  [DELETION ERROR] Could not delete {folder.name}: {e}")
                
        self._write_report(REPORTING_FILE, total_deleted, total_kept)
        print("\nFiltering operation completed.")

    def _write_report(self, report_file: Path, total_deleted: int, total_kept: int):
        """Writes the summary report to a text file."""
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("="*40 + "\n")
                f.write("   SUBFOLDER FILTERING REPORT\n")
                f.write("="*40 + "\n\n")
                f.write(f"Total folders analyzed : {self.report_counts['total_folders']}\n")
                f.write(f"Total folders kept : {total_kept}\n")
                f.write(f"Total folders DELETED : {total_deleted}\n\n")

                f.write("-" * 25 + "\n")
                f.write("Folders kept by criterion (Stop at first match):\n")
                f.write("-" * 25 + "\n")
                f.write(f"  1. Validated by Filter 1 (Op/Topic JSON) : {self.report_counts['validated_filter_1']}\n")
                f.write(f"  2. Validated by Filter 2 (YAML Keywords) : {self.report_counts['validated_filter_2']}\n")
                f.write(f"  3. Validated by Filter 3 (Description) : {self.report_counts['validated_filter_3']}\n\n")
                f.write(f"Folders that failed ANY filter : {self.report_counts['did_not_pass_any']}\n")
            
            print(f"\n[REPORTING] Report written to : {report_file.name}")
            
        except IOError as e:
            print(f"\n[CRITICAL WRITE FAILURE] Could not write report to '{report_file.parent.name}/'.")


# -------------------------------------------------------------
#                       MAIN EXECUTION
# -------------------------------------------------------------

if __name__ == "__main__":
    
    # 1. Directory checks
    if not RSEC_DIR.is_dir():
        print(f"ERROR: The directory to process 'content/rsec' was not found at the default location: '{RSEC_DIR}'")
        sys.exit(1)
        
    if not KEYWORDS_FILEPATH.is_file():
        print(f"ERROR: The YAML configuration file 'keywords.yml' was not found at the default location: '{KEYWORDS_FILEPATH}'")
        sys.exit(1)
        

    ROOT_DIRECTORY = RSEC_DIR
    OUTPUT_DIR = RSEC_DIR / "infos" 
    REPORTING_FILE = OUTPUT_DIR / "filtering_report.txt"
    VALIDATED_METADATA_FILE = OUTPUT_DIR / "validated_tools_metadata.json"
    FAILED_METADATA_FILE = OUTPUT_DIR / "failed_tools_metadata.json"
    TSV_OUTPUT_FILE = OUTPUT_DIR / "validated_tools_summary.tsv" # New file path for the TSV summary

    # 3. Load keywords
    try:
        keywords_data = load_keywords_from_yaml(KEYWORDS_FILEPATH)
        
        TARGET_OPERATIONS = keywords_data["operations"]
        TARGET_TOPICS = keywords_data["topics"]
        STRICT_KEYWORDS = keywords_data["stricts"] # Acronyms
        COMPILED_FRAGMENT_PATTERNS = keywords_data["compiled_fragments"] # Regex 
        # NEW: Global assignment of pre-compiled strict patterns
        COMPILED_STRICT_PATTERNS = keywords_data["compiled_stricts"] 
        
        print("\n--- LOADED CRITERIA ---")
        print(f"EDAM Operations: {TARGET_OPERATIONS}")
        print(f"EDAM Topics: {TARGET_TOPICS}")
        print(f"Fragment Patterns (REGEX): {[p.pattern for p in COMPILED_FRAGMENT_PATTERNS]}")
        print(f"Strict Acronyms (Word Boundary Search): {STRICT_KEYWORDS}")
        print("--------------------------\n")

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Failed to initialize keywords: {e}")
        sys.exit(1)

    # 4. Start filtering
    tool_set = ToolSet(ROOT_DIRECTORY)
    tool_set.run_filtering()
    
    # 5. Generate TSV summary after successful filtering
    print("\n--- Generating TSV Summary ---")
    generate_tsv_summary(VALIDATED_METADATA_FILE, TSV_OUTPUT_FILE)