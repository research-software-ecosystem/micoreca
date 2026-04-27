import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import (
    Any,
    Dict,
)

import utils
from bioconda_manager import (
    BiocondaRecipe,
    BiocondaRecipes,
)


class TestBiocondaRecipe(unittest.TestCase):
    def setUp(self) -> None:
        # Sample Bioconda recipe
        self.sample_recipe = {
            "about": {
                "summary": "Analysis of 16S rRNA microbial communities",
                "description": "This tool profiles microbial diversity in metagenomics studies",
            },
            "package": {"name": "pkg1", "version": "1.0"},
        }
        # Keywords to test (including wildcard)
        self.keywords = {"keywords": ["microbiome", "16S", "metagenom*"]}

    def test_init(self) -> None:
        recipe = BiocondaRecipe()
        self.assertEqual(recipe.get_name(), "")
        self.assertFalse(recipe.get_status())

    def test_parse(self) -> None:
        # Create a temporary directory and meta.yaml
        with tempfile.TemporaryDirectory() as tmpdir:
            recipe_dir = Path(tmpdir) / "example_package"
            recipe_dir.mkdir(parents=True, exist_ok=True)
            meta_content = textwrap.dedent(
                """\
                package:
                  name: example_package
                  version: "1.0"
                about:
                  summary: "A test package"
                  description: "This is a test package description"
            """
            )
            meta_yaml_path = recipe_dir / "meta.yaml"
            meta_yaml_path.write_text(meta_content)

            # Parse the recipe
            recipe = BiocondaRecipe()
            success = recipe.parse(meta_yaml_path)
            self.assertTrue(success)
            self.assertEqual(recipe.get_name(), "example_package")
            self.assertEqual(recipe.get_summary(), "A test package")
            self.assertEqual(recipe.get_description(), "This is a test package description")

    def test_load(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        self.assertEqual(recipe.get_name(), "pkg1")
        self.assertEqual(recipe.get_summary(), "Analysis of 16S rRNA microbial communities")
        self.assertEqual(recipe.get_description(), "This tool profiles microbial diversity in metagenomics studies")

    def test_get_package(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        package = recipe.get_package()
        self.assertEqual(package["name"], "pkg1")
        self.assertEqual(package["version"], "1.0")

    def test_get_name(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        self.assertEqual(recipe.get_name(), "pkg1")

    def test_get_about(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        about = recipe.get_about()
        self.assertEqual(about["summary"], "Analysis of 16S rRNA microbial communities")
        self.assertEqual(about["description"], "This tool profiles microbial diversity in metagenomics studies")

    def test_get_description(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        self.assertEqual(recipe.get_description(), "This tool profiles microbial diversity in metagenomics studies")

    def test_get_summary(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        self.assertEqual(recipe.get_summary(), "Analysis of 16S rRNA microbial communities")

    def test_get_status(self) -> None:
        recipe = BiocondaRecipe()
        self.assertFalse(recipe.get_status())
        recipe.update_status(True)
        self.assertTrue(recipe.get_status(), True)

    def test_update_status(self) -> None:
        recipe = BiocondaRecipe()
        recipe.update_status(True)
        self.assertTrue(recipe.get_status(), True)
        recipe.update_status(False)
        self.assertFalse(recipe.get_status(), False)

    def test_test_about(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        self.assertTrue(recipe.test_about(self.keywords))

    def test_export_to_dict(self) -> None:
        recipe = BiocondaRecipe()
        recipe.load(self.sample_recipe)
        exported = recipe.export_to_dict()
        self.assertEqual(exported["package"]["name"], "pkg1")
        self.assertEqual(exported["about"]["summary"], "Analysis of 16S rRNA microbial communities")


class TestBiocondaRecipes(unittest.TestCase):
    def setUp(self) -> None:
        # Sample Bioconda recipes (as metadata dicts)
        self.sample_conda = {
            "pkg1": {
                "about": {
                    "summary": "Analysis of 16S rRNA microbial communities",
                    "description": "This tool profiles microbial diversity in metagenomics studies",
                },
                "package": {"name": "pkg1", "version": "1.0"},
            },
            "pkg2": {
                "about": {"summary": "A completely unrelated package", "description": "bla"},
                "package": {"name": "pkg2", "version": "1.0"},
            },
            "pkg3": {
                "about": {
                    "summary": "Metagenome assembly pipeline",
                    "description": "Assembles metagenomic reads into contigs",
                },
                "package": {"name": "pkg3", "version": "1.0"},
            },
        }
        # Keywords to test (including wildcard)
        self.keywords = {
            "keywords": ["microbiome", "16S", "metagenom.*"],
            "acronyms": ["OTU"],
        }

    def test_init(self) -> None:
        recipes = BiocondaRecipes()
        self.assertEqual(len(recipes.recipes), 0)

    def test_parse_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a temporary directory with sample recipes
            recipes_dir = Path(tmpdir) / "recipes"
            recipes_dir.mkdir(parents=True, exist_ok=True)

            for name, meta in self.sample_conda.items():
                recipe_dir = recipes_dir / name
                recipe_dir.mkdir(parents=True, exist_ok=True)
                meta_content = textwrap.dedent(
                    f"""\
                    package:
                      name: {name}
                      version: "1.0"
                    about:
                      summary: "{meta['about']['summary']}"
                      description: "{meta['about']['description']}"
                """
                )
                meta_yaml_path = recipe_dir / "meta.yaml"
                meta_yaml_path.write_text(meta_content)

            # Parse all recipes
            recipes = BiocondaRecipes()
            recipes.parse_all(str(recipes_dir.parent))

            # Check parsed content
            self.assertEqual(len(recipes.recipes), 3)
            self.assertIn("pkg1", recipes.recipes)
            self.assertIn("pkg2", recipes.recipes)
            self.assertIn("pkg3", recipes.recipes)

    def test_load_json(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_name = tmp.name
            utils.export_to_json(list(self.sample_conda.values()), tmp_name)

        recipes = BiocondaRecipes()
        recipes.load_json(tmp_name)

        self.assertEqual(len(recipes.recipes), 3)
        self.assertIn("pkg1", recipes.recipes)
        self.assertIn("pkg2", recipes.recipes)
        self.assertIn("pkg3", recipes.recipes)

        Path(tmp_name).unlink()

    def test_filter_by_keywords(self) -> None:
        recipes = BiocondaRecipes()
        recipes.recipes = {
            "pkg1": BiocondaRecipe(),
            "pkg2": BiocondaRecipe(),
            "pkg3": BiocondaRecipe(),
        }
        for name, meta in self.sample_conda.items():
            recipes.recipes[name].load(meta)

        status: Dict[str, Any] = {}

        recipes.filter_by_keywords(self.keywords, status)

        self.assertEqual(len(recipes.recipes), 2)
        self.assertIn("pkg1", recipes.recipes)
        self.assertIn("pkg3", recipes.recipes)
        self.assertNotIn("pkg2", recipes.recipes)

    def test_curate(self) -> None:
        recipes = BiocondaRecipes()
        recipes.recipes = {
            "pkg1": BiocondaRecipe(),
            "pkg2": BiocondaRecipe(),
            "pkg3": BiocondaRecipe(),
        }
        for name, meta in self.sample_conda.items():
            recipes.recipes[name].load(meta)

        status = {"pkg1": {"keep": True}, "pkg3": {"keep": True}}

        recipes.curate(status)

        self.assertEqual(len(recipes.recipes), 2)
        self.assertIn("pkg1", recipes.recipes)
        self.assertIn("pkg3", recipes.recipes)
        self.assertNotIn("pkg2", recipes.recipes)

    def test_export_recipes_to_list(self) -> None:
        recipes = BiocondaRecipes()
        recipes.recipes = {
            "pkg1": BiocondaRecipe(),
            "pkg3": BiocondaRecipe(),
        }
        for name, meta in {k: v for k, v in self.sample_conda.items() if k in ["pkg1", "pkg3"]}.items():
            recipes.recipes[name].load(meta)

        exported = recipes.export_recipes_to_list()
        self.assertEqual(len(exported), 2)
        names = [r["package"]["name"] for r in exported]
        self.assertIn("pkg1", names)
        self.assertIn("pkg3", names)

    def test_export_to_json(self) -> None:
        recipes = BiocondaRecipes()
        recipes.recipes = {
            "pkg1": BiocondaRecipe(),
            "pkg3": BiocondaRecipe(),
        }
        for name, meta in {k: v for k, v in self.sample_conda.items() if k in ["pkg1", "pkg3"]}.items():
            recipes.recipes[name].load(meta)

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_path = tmp.name

        recipes.export_to_json(tmp_path)
        loaded = utils.load_json(tmp_path)

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["package"]["name"], "pkg1")
        self.assertEqual(loaded[1]["package"]["name"], "pkg3")
        Path(tmp_path).unlink()

    def test_export_to_tsv(self) -> None:
        recipes = BiocondaRecipes()
        recipes.recipes = {
            "pkg1": BiocondaRecipe(),
            "pkg3": BiocondaRecipe(),
        }
        for name, meta in {k: v for k, v in self.sample_conda.items() if k in ["pkg1", "pkg3"]}.items():
            recipes.recipes[name].load(meta)

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        recipes.export_to_tsv(str(tmp_path))

        with tmp_path.open(encoding="utf-8") as f:
            lines = f.readlines()

        self.assertGreater(len(lines), 0)
        tmp_path.unlink()


if __name__ == "__main__":
    unittest.main()
