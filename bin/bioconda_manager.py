#!/usr/bin/env python
import argparse
import logging
import os
import zipfile
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import jinja2
import pandas as pd
import requests
import utils
import yaml
from tqdm import tqdm

logger = logging.getLogger(__name__)


class BiocondaRecipe:
    """Represents a single Bioconda recipe and its metadata."""

    def __init__(self) -> None:
        self.metadata: Dict[str, Any] = {
            "keep": False,
            "about": {
                "description": "",
                "summary": "",
            },
            "package": {"name": ""},
        }

    def parse(self, meta_yaml_path: Path) -> bool:
        """Parse the meta.yaml file and extract the recipe metadata."""

        def fake(foo: Any, **args: Any) -> None:
            """Fake function for Jinja2 rendering."""
            pass

        try:
            template = jinja2.Template(meta_yaml_path.read_text())
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
            logging.error(f"Failed to render Jinja2 template in {meta_yaml_path}: {e}")
            raise

        try:
            self.metadata = yaml.safe_load(rendered)
        except yaml.YAMLError as e:
            logging.error(f"Failed to parse YAML in {meta_yaml_path}: {e}")
            raise
        self.update_status(False)
        if not self.metadata or self.get_name() == "":
            logging.error(f"Missing 'package.name' in {meta_yaml_path}")
            return False
        return True

    def load(self, metadata: Dict[str, Any]) -> None:
        self.metadata = metadata

    def get_package(self) -> Dict[str, Any]:
        """Return the 'package' section of the recipe."""
        return self.metadata.get("package", {"name": ""})

    def get_name(self) -> str:
        """Return the package name."""
        return self.get_package().get("name", "")

    def get_about(self) -> Dict[str, Any]:
        """Return the 'about' section of the recipe."""
        return self.metadata.get(
            "about",
            {
                "description": "",
                "summary": "",
            },
        )

    def get_description(self) -> str:
        """Return the description of the recipe."""
        return self.get_about().get("description", "")

    def get_summary(self) -> str:
        """Return the summary of the recipe."""
        return self.get_about().get("summary", "")

    def get_status(self) -> bool:
        """Return the status of the recipe."""
        return bool(self.metadata.get("keep", False))

    def update_status(self, status: bool) -> None:
        """Update status"""
        self.metadata["keep"] = status

    def test_about(self, keywords: Dict[str, Any]) -> bool:
        """Test if description and/or summary have keywords"""
        text = (self.get_description() + " " + self.get_summary()).lower()
        filtered_on = utils.has_keyword(keywords, text, "description")
        return filtered_on != ""

    def export_to_dict(self) -> dict:
        """Export workflows as list of dictionary"""
        return self.metadata


class BiocondaRecipes:
    """Manages a collection of Bioconda recipes."""

    def __init__(self) -> None:
        self.recipes: Dict[str, BiocondaRecipe] = {}

    def parse_all(self, directory: str) -> None:
        """Parse all Bioconda recipes in the directory."""

        def to_keep(x: Path) -> bool:
            return not str(x).endswith("esme/meta.yaml")

        paths = [x for x in Path(directory).glob("./recipes/*/meta.yaml") if to_keep(x)]
        for p in tqdm(paths, desc="Parsing Bioconda recipes", unit="file"):
            recipe = BiocondaRecipe()
            status = recipe.parse(p)
            if status:
                self.recipes[recipe.get_name()] = recipe

    def load_json(self, filepath: str) -> None:
        """Load recipes from a JSON file"""
        recipes = utils.load_json(filepath)
        for r in recipes:
            recipe = BiocondaRecipe()
            recipe.load(r)
            self.recipes[recipe.get_name()] = recipe

    def filter_by_keywords(self, keywords: dict, status: dict) -> None:
        """Filter recipes by keywords in description or summary."""
        filtered_recipes = {}
        logging.info(f"Total recipes: {len(self.recipes)}")
        for name, recipe in self.recipes.items():
            if name in status:
                recipe.update_status(status[name]["keep"])
            if recipe.get_status() or recipe.test_about(keywords):
                filtered_recipes[name] = recipe
        self.recipes = filtered_recipes
        logging.info(f"Filtered recipes: {len(self.recipes)}")

    def curate(self, status: Dict) -> None:
        """Curate recipes based on community feedback"""
        logging.info(f"Filtered recipes: {len(self.recipes)}")
        curated_recipes = {}
        for name, recipe in self.recipes.items():
            if name in status:
                recipe.update_status(status[name])
            if recipe.get_status():
                curated_recipes[name] = recipe
        self.recipes = curated_recipes
        logging.info(f"Curated recipes: {len(self.recipes)}")

    def export_recipes_to_list(self) -> List:
        """Export workflows as list of dictionary"""
        return [r.export_to_dict() for r in self.recipes.values()]

    def export_to_json(self, output_file: str) -> None:
        """Export recipes to a JSON file."""
        recipes = self.export_recipes_to_list()
        utils.export_to_json(recipes, output_file)
        logging.info(f"Recipes written as JSON to: {output_file}")

    def export_to_tsv(self, output_file: str, to_keep_columns: Optional[List[str]] = None) -> None:
        """Export recipes to a TSV file."""
        df = pd.json_normalize(
            self.export_recipes_to_list(),
            meta_prefix="",
            record_prefix="",
        )
        if not df.empty:
            df = df.set_index("package.name")

        if to_keep_columns is not None:
            df = df[to_keep_columns]

        df.to_csv(output_file, sep="\t")
        logging.info(f"Recipes written as TSV to: {output_file}")


def download_and_extract_bioconda_recipes(tmp_dir: str = "./tmp") -> Path:
    """Download and extract Bioconda recipes from GitHub."""
    tmp_path = Path(tmp_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)
    zip_url = "https://codeload.github.com/bioconda/bioconda-recipes/zip/master"
    zip_path = tmp_path / "bioconda-recipes.zip"
    logging.info(f"Downloading {zip_url}...")
    # Download ZIP file
    response = requests.get(zip_url, stream=True)
    response.raise_for_status()  # Raise an error for bad status codes
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    # Extract ZIP file
    logging.info(f"Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(tmp_path)
    # Remove the ZIP file
    zip_path.unlink()
    extracted_dir = tmp_path / "bioconda-recipes-master"
    return extracted_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract, filter, and curate Bioconda recipes.")
    parser.add_argument(
        "-v",
        "--verbose",
        type=int,
        default=3,
        choices=[0, 1, 2, 3, 4],
        help="Verbosity level (0=CRITICAL, 1=ERROR, 2=WARN, 3=INFO, 4=DEBUG)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extract subcommand
    extract_parser = subparsers.add_parser("extract", help="Extract all Bioconda recipes.")
    extract_parser.add_argument(
        "--all",
        "-o",
        required=True,
        help="Filepath to JSON with all extracted recipes",
    )
    extract_parser.add_argument(
        "--bioconda-path",
        help="Path to the Bioconda recipes directory. If not provided, the script will download the latest version.",
    )

    # Filter subcommand
    filter_parser = subparsers.add_parser("filter", help="Filter Bioconda recipes by keywords.")
    filter_parser.add_argument(
        "--all",
        "-a",
        required=True,
        help="Filepath to JSON with all extracted recipes",
    )
    filter_parser.add_argument(
        "--json-filtered",
        "-f",
        required=True,
        help="Filepath to JSON with filtered recipes",
    )
    filter_parser.add_argument(
        "--tsv-filtered",
        "-t",
        required=True,
        help="Filepath to TSV with filtered recipes",
    )
    filter_parser.add_argument(
        "--keywords",
        "-k",
        required=True,
        help="Path to a YAML file with keywords for filtering",
    )
    filter_parser.add_argument(
        "--status",
        "-s",
        required=True,
        help="Path to a TSV file with at least column 'name' and 'To keep'",
    )

    # Curate subcommand
    curate_parser = subparsers.add_parser("curate", help="Curate Bioconda recipes based on status.")
    curate_parser.add_argument(
        "--filtered",
        "-f",
        required=True,
        help="Filepath to JSON with filtered recipes",
    )
    curate_parser.add_argument(
        "--json-curated",
        "-c",
        required=True,
        help="Filepath to JSON with curated recipes",
    )
    curate_parser.add_argument(
        "--tsv-curated",
        "-t",
        required=True,
        help="Filepath to TSV with curated recipes",
    )
    curate_parser.add_argument(
        "--status",
        "-s",
        required=True,
        help="Path to a TSV file with at least column 'name' and 'To keep'",
    )

    args = parser.parse_args()
    utils.setup_logger(args.verbose)

    if args.command == "extract":
        # Download and extract if no path is provided
        if not args.bioconda_path:
            logging.info("No Bioconda path provided. Downloading the latest version...")
            args.bioconda_path = download_and_extract_bioconda_recipes()
        recipes = BiocondaRecipes()
        recipes.parse_all(args.bioconda_path)
        recipes.export_to_json(args.all)

    elif args.command == "filter":
        # Load all recipes
        recipes = BiocondaRecipes()
        recipes.load_json(args.all)

        # Load status
        if args.status:
            try:
                status = pd.read_csv(args.status, sep="\t", index_col="package.name").to_dict("index")
            except Exception:
                status = {}
        else:
            status = {}

        # Load keywords
        keywords = utils.load_yaml(args.keywords)

        # Filter recipes
        recipes.filter_by_keywords(keywords, status)
        recipes.export_to_json(args.json_filtered)
        recipes.export_to_tsv(args.tsv_filtered)
        recipes.export_to_tsv(
            args.status,
            to_keep_columns=[
                "keep",
                "about.summary",
                "about.description",
                "about.home",
            ],
        )

    elif args.command == "curate":
        # Load filtered recipes
        recipes = BiocondaRecipes()
        recipes.load_json(args.filtered)

        # Load status
        try:
            status = pd.read_csv(args.status, sep="\t", index_col="name").to_dict("index")
        except Exception as ex:
            logging.info(f"Failed to load {args.status} file or no 'name' column with:\n{ex}")
            logging.info("Not assigning tool status for this community !")
            status = {}

        # Curate recipes
        recipes.curate(status)
        recipes.export_to_json(args.json_curated)
        recipes.export_to_tsv(args.tsv_curated)


if __name__ == "__main__":
    main()
