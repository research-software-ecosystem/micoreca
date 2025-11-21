#!/usr/bin/env python

import argparse
import fnmatch
import json
import os
from collections import defaultdict
from pathlib import Path

import jinja2
import yaml
from tqdm import tqdm


def fake(foo, **args):
    pass


def parse_bioconda(directory):
    """
    Load Bioconda recipes into memory.
    Uses 'package.name' from meta.yaml instead of folder name or absolute path.
    Raises exceptions if rendering or parsing fails.
    """
    data = {}
    paths = list(Path(directory).glob("./*/meta.yaml"))

    for p in tqdm(paths, desc="Parsing Bioconda recipes", unit="file"):
        try:
            # Read and render the Jinja2 template
            template = jinja2.Template(p.read_text())
            rendered = template.render(
                {
                    "os": os,
                    "compiler": fake,
                    "environ": "",
                    "cdt": fake,
                    "pin_compatible": fake,
                    "pin_subpackage": fake,
                    "exact": fake,
                    "stdlib": fake,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Failed to render Jinja2 template in {p}") from e

        try:
            # Parse YAML
            conda = yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            raise RuntimeError(f"Failed to parse YAML in {p}") from e

        # Validate package name
        if not conda or "package" not in conda or "name" not in conda["package"]:
            raise ValueError(f"Missing 'package.name' in {p}")

        pkg_name = conda["package"]["name"]
        data[pkg_name] = conda

    return data


def filter_conda_by_keywords(conda, keywords, verbose=True):
    """
    Filter Bioconda recipes whose description or summary contains any of the given keywords.
    Supports wildcard '*' in keywords.

    Args:
        conda (dict): Parsed Bioconda metadata (from parse_bioconda()).
        keywords (list): List of keyword strings to search for (supports '*').
        verbose (bool): If True, prints matches during filtering.

    Returns:
        dict: Filtered dictionary of matching recipes.
    """
    counter = 0
    filtered_conda = {}

    for name, recipe in conda.items():
        about = recipe.get("about", {})
        text = (about.get("description", "") + " " + about.get("summary", "")).lower()

        matched = []
        for kw in keywords:
            kw_lower = kw.lower()
            if "*" in kw_lower:
                # Use fnmatch for wildcard pattern
                if any(fnmatch.fnmatch(word, kw_lower) for word in text.split()):
                    matched.append(kw)
            else:
                if kw_lower in text:
                    matched.append(kw)

        if matched:
            if verbose:
                print(f"Match found in: {name} | Matched keywords: {matched}")
            filtered_conda[name] = recipe
            counter += 1

    if verbose:
        print(f"Total matches: {counter}")

    return filtered_conda


def save_filtered_conda_to_json(filtered_conda, output_file="filtered_bioconda.json"):
    """
    Save the filtered Bioconda recipes dictionary to a JSON file.

    Args:
        filtered_conda (dict): Filtered dictionary of Bioconda recipes.
        output_file (str): Path to the JSON file to write.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(filtered_conda, f, indent=4, ensure_ascii=False)

    print(f"Filtered metadata written to: {output_file}")


def load_keywords_from_yaml(keyword_file):
    """Load keywords from a YAML file with structure:
    keywords:
      - word1
      - word2
      ...
    """
    with open(keyword_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "keywords" not in data:
        raise ValueError(f"No 'keywords' key found in {keyword_file}")

    keywords = data["keywords"]
    if not isinstance(keywords, list):
        raise TypeError(f"'keywords' in {keyword_file} must be a list")

    print(f"Loaded {len(keywords)} keywords from {keyword_file}")
    return keywords


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter Bioconda recipes by microbiome-related keywords and export to JSON."
    )
    parser.add_argument(
        "--bioconda-path",
        required=True,
        help="Path to the Bioconda recipes directory (e.g., /path/to/bioconda-recipes/recipes)",
    )
    parser.add_argument(
        "--keywords-file",
        required=True,
        help="Path to a text file containing one keyword per line",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to the output JSON file (e.g., filtered_bioconda.json)",
    )

    args = parser.parse_args()

    # Load resources
    keywords = load_keywords_from_yaml(args.keywords_file)
    conda = parse_bioconda(args.bioconda_path)
    conda_filtered = filter_conda_by_keywords(conda, keywords)
    save_filtered_conda_to_json(conda_filtered, args.output_file)
