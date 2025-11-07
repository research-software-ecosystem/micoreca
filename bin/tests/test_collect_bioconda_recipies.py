import unittest
import tempfile
import os
from pathlib import Path
import json
import textwrap

from collect_bioconda_recipes import filter_conda_by_keywords, save_filtered_conda_to_json, load_keywords_from_file, parse_bioconda, fake

class TestBiocondaFunctions(unittest.TestCase):

    def setUp(self):
        # Sample Bioconda recipes
        self.sample_conda = {
            "pkg1": {
                "about": {
                    "summary": "Analysis of 16S rRNA microbial communities",
                    "description": "This tool profiles microbial diversity in metagenomics studies"
                },
                "package": {"name": "pkg1", "version": "1.0"}
            },
            "pkg2": {
                "about": {
                    "summary": "A completely unrelated package",
                    "description": "bla"
                },
                "package": {"name": "pkg2", "version": "1.0"}
            },
            "pkg3": {
                "about": {
                    "summary": "Metagenome assembly pipeline",
                    "description": "Assembles metagenomic reads into contigs"
                },
                "package": {"name": "pkg3", "version": "1.0"}
            }
        }
        # Keywords to test (including wildcard)
        self.keywords = ["microbiome", "16S", "metagenom*"]

    def test_parse_bioconda_single_recipe(self):
        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            recipe_dir = Path(tmpdir) / "example_package"
            recipe_dir.mkdir(parents=True, exist_ok=True)

            # Use textwrap.dedent to remove indentation
            meta_content = textwrap.dedent("""\
                package:
                  name: example_package
                  version: "1.0"

                about:
                  summary: "A test package"
                  description: "This is a test package description"
            """)

            meta_yaml_path = recipe_dir / "meta.yaml"
            meta_yaml_path.write_text(meta_content)

            # Call parse_bioconda
            parsed = parse_bioconda(tmpdir)

            # There should be exactly one entry
            self.assertEqual(len(parsed), 1)

            # The key should be the absolute path of meta.yaml
            self.assertIn(str(meta_yaml_path.absolute()), parsed)

            # Check parsed content
            conda_data = parsed[str(meta_yaml_path.absolute())]
            self.assertIsNotNone(conda_data, "Parsed YAML should not be None")
            self.assertEqual(conda_data["package"]["name"], "example_package")
            self.assertEqual(conda_data["about"]["summary"], "A test package")
            self.assertEqual(conda_data["about"]["description"], "This is a test package description")


    def test_filter_conda_by_keywords(self):
        filtered = filter_conda_by_keywords(self.sample_conda, self.keywords, verbose=False)
        # pkg1 should match exact keyword '16S'
        self.assertIn("pkg1", filtered)
        # pkg2 should NOT match any keyword
        self.assertNotIn("pkg2", filtered)
        # pkg3 should match wildcard 'metagenom*'
        self.assertIn("pkg3", filtered)

    def test_save_and_load_json(self):
        filtered = filter_conda_by_keywords(self.sample_conda, self.keywords, verbose=False)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_name = tmp.name
        save_filtered_conda_to_json(filtered, tmp_name)
        with open(tmp_name, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        # Only pkg1 and pkg3 should be present
        self.assertEqual(set(loaded.keys()), {"pkg1", "pkg3"})
        os.remove(tmp_name)

    def test_load_keywords_from_file(self):
        # Write a temporary keyword file
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp.write("microbiome\n16S\nmetagenom*\n")
            tmp_name = tmp.name
        loaded_keywords = load_keywords_from_file(tmp_name)
        self.assertEqual(loaded_keywords, ["microbiome", "16S", "metagenom*"])
        os.remove(tmp_name)


if __name__ == "__main__":
    unittest.main()
