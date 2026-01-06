"""Unit tests for extract_workflowhub.py"""

import unittest
from unittest.mock import (
    Mock,
    patch,
)

from extract_workflowhub import (
    Workflow,
    Workflows,
)


class TestWorkflow(unittest.TestCase):
    """Test cases for Workflow class"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.workflow = Workflow()

    def test_init(self) -> None:
        """Test Workflow initialization"""
        self.assertEqual(self.workflow.source, "")
        self.assertEqual(self.workflow.id, 0)
        self.assertEqual(self.workflow.link, "")
        self.assertEqual(self.workflow.name, "")
        self.assertEqual(self.workflow.creators, [])
        self.assertEqual(self.workflow.tags, [])
        self.assertEqual(self.workflow.create_time, "")
        self.assertEqual(self.workflow.update_time, "")
        self.assertEqual(self.workflow.latest_version, 0)
        self.assertEqual(self.workflow.versions, 0)
        self.assertEqual(self.workflow.number_of_steps, 0)
        self.assertEqual(self.workflow.tools, [])
        self.assertEqual(self.workflow.edam_operation, [])
        self.assertEqual(self.workflow.edam_topic, [])
        self.assertEqual(self.workflow.license, "")
        self.assertEqual(self.workflow.doi, "")
        self.assertEqual(self.workflow.projects, [])
        self.assertEqual(self.workflow.keep, False)
        self.assertEqual(self.workflow.curation_date, "0000-00-00")
        self.assertEqual(self.workflow.type, "")
        self.assertEqual(self.workflow.description, "")
        self.assertEqual(self.workflow.filtered_on, "")

    def test_init_by_importing(self) -> None:
        """Test init_by_importing method"""
        wf_dict = {
            "source": "WorkflowHub",
            "id": 123,
            "link": "https://workflowhub.eu/workflows/123",
            "name": "Test Workflow",
            "creators": ["John Doe"],
            "tags": ["metagenomics", "analysis"],
            "create_time": "2023-01-01",
            "update_time": "2023-06-01",
            "latest_version": 2,
            "versions": 3,
            "number_of_steps": 5,
            "tools": ["tool1", "tool2"],
            "edam_operation": ["Annotation"],
            "edam_topic": ["Metagenomics"],
            "license": "MIT",
            "doi": "10.1234/test",
            "projects": ["Project A"],
            "type": "Galaxy",
            "description": "Test description",
            "curation_date": "2023-12-01",
            "filtered_on": "edam",
            "keep": True,
        }

        self.workflow.init_by_importing(wf_dict)

        self.assertEqual(self.workflow.source, "WorkflowHub")
        self.assertEqual(self.workflow.id, 123)
        self.assertEqual(self.workflow.link, "https://workflowhub.eu/workflows/123")
        self.assertEqual(self.workflow.name, "Test Workflow")
        self.assertEqual(self.workflow.creators, ["John Doe"])
        self.assertEqual(self.workflow.tags, ["metagenomics", "analysis"])
        self.assertEqual(self.workflow.keep, True)
        self.assertEqual(self.workflow.curation_date, "2023-12-01")
        self.assertEqual(self.workflow.filtered_on, "edam")

    def test_init_from_search(self) -> None:
        """Test init_from_search method"""
        extracted_wf = {
            "data": {
                "id": "456",
                "links": {"self": "/workflows/456"},
                "attributes": {
                    "title": "Search Workflow",
                    "tags": ["RNA-Seq", "Analysis"],
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-06-01T00:00:00Z",
                    "latest_version": 3,
                    "versions": [1, 2, 3],
                    "internals": {
                        "steps": [
                            {"description": "tool1", "name": "Tool 1"},
                            {"description": "tool2", "name": "Tool 2"},
                        ]
                    },
                    "license": "Apache-2.0",
                    "doi": "10.5678/search",
                    "topic_annotations": [{"label": "Metagenomics"}],
                    "operation_annotations": [{"label": "Sequence analysis"}],
                    "workflow_class": {"title": "Galaxy"},
                    "description": "Search test description",
                    "creators": [],
                    "other_creators": "Jane Smith,Bob Johnson",
                    "tools": [],
                },
                "relationships": {"projects": {"data": []}},
            }
        }

        self.workflow.init_from_search(extracted_wf, "WorkflowHub")

        self.assertEqual(self.workflow.source, "WorkflowHub")
        self.assertEqual(self.workflow.id, "456")
        self.assertEqual(self.workflow.link, "https://workflowhub.eu/workflows/456")
        self.assertEqual(self.workflow.name, "Search Workflow")
        self.assertEqual(self.workflow.tags, ["rna-seq", "analysis"])
        self.assertEqual(self.workflow.latest_version, 3)
        self.assertEqual(self.workflow.versions, 3)
        self.assertEqual(self.workflow.number_of_steps, 2)
        self.assertEqual(self.workflow.type, "Galaxy")

    def test_add_creators_with_creators_list(self) -> None:
        """Test add_creators with creators present"""
        wf_data = {
            "data": {
                "attributes": {
                    "creators": [
                        {"given_name": "John", "family_name": "Doe"},
                        {"given_name": "Jane", "family_name": "Smith"},
                    ],
                    "other_creators": "",
                }
            }
        }

        self.workflow.add_creators(wf_data)

        self.assertEqual(self.workflow.creators, ["John Doe", "Jane Smith"])

    def test_add_creators_with_other_creators(self) -> None:
        """Test add_creators with other_creators string"""
        wf_data = {
            "data": {
                "attributes": {
                    "creators": [],
                    "other_creators": "Alice Brown,Charlie White",
                }
            }
        }

        self.workflow.add_creators(wf_data)

        self.assertEqual(self.workflow.creators, ["Alice Brown", "Charlie White"])

    def test_add_tools_from_steps(self) -> None:
        """Test add_tools extracting from steps"""
        wf_data = {
            "data": {
                "attributes": {
                    "tools": [],
                    "internals": {
                        "steps": [
                            {"description": "Tool_A", "name": None},
                            {"description": "Tool_B", "name": None},
                            {"description": None, "name": "Tool_C"},
                        ]
                    },
                }
            }
        }
        self.workflow.type = "Galaxy"

        self.workflow.add_tools(wf_data)

        self.assertIn("Tool_A", self.workflow.tools)
        self.assertIn("Tool_B", self.workflow.tools)
        self.assertIn("Tool_C", self.workflow.tools)

    def test_add_tools_from_attributes(self) -> None:
        """Test add_tools from tools attribute"""
        wf_data = {"data": {"attributes": {"tools": [{"name": "FastQC"}, {"name": "Bowtie2"}]}}}
        self.workflow.type = "CWL"

        self.workflow.add_tools(wf_data)

        self.assertEqual(self.workflow.tools, ["FastQC", "Bowtie2"])

    @patch("utils.get_request_json")
    def test_add_projects(self, mock_get_request: Mock) -> None:
        """Test add_projects method"""
        mock_get_request.return_value = {"data": {"attributes": {"title": "Test Project"}}}

        wf_data = {"data": {"relationships": {"projects": {"data": [{"id": "1"}]}}}}
        self.workflow.source = "WorkflowHub"

        self.workflow.add_projects(wf_data)

        self.assertEqual(self.workflow.projects, ["Test Project"])

    def test_test_tags_match(self) -> None:
        """Test test_tags with matching keywords"""
        keywords = {"keywords": ["genomics", "proteomics"], "acronyms": ["RNA"]}
        self.workflow.tags = ["genomics", "analysis"]

        result = self.workflow.test_tags(keywords)

        self.assertTrue(result)
        self.assertEqual(self.workflow.filtered_on, "genomics in tags")

    def test_test_tags_no_match(self) -> None:
        """Test test_tags without matching keywords"""
        keywords = {"keywords": ["metabolomics"], "acronyms": ["DNA"]}
        self.workflow.tags = ["genomics", "analysis"]

        result = self.workflow.test_tags(keywords)

        self.assertFalse(result)
        self.assertEqual(self.workflow.filtered_on, "")

    def test_test_edam_terms_topic_match(self) -> None:
        """Test test_edam_terms with topic match"""
        edam_keywords = {
            "topics": ["Metagenomics"],
            "operations": ["Annotation"],
        }
        self.workflow.edam_topic = ["Metagenomics", "Metabolomics"]
        self.workflow.edam_operation = ["Visualization"]

        result = self.workflow.test_edam_terms(edam_keywords)

        self.assertTrue(result)
        self.assertEqual(self.workflow.filtered_on, "edam")

    def test_test_edam_terms_operation_match(self) -> None:
        """Test test_edam_terms with operation match"""
        edam_keywords = {
            "topics": ["Metabolomics"],
            "operations": ["Annotation", "Visualization"],
        }
        self.workflow.edam_topic = ["Metagenomics"]
        self.workflow.edam_operation = ["Annotation"]

        result = self.workflow.test_edam_terms(edam_keywords)

        self.assertTrue(result)
        self.assertEqual(self.workflow.filtered_on, "edam")

    def test_test_edam_terms_no_match(self) -> None:
        """Test test_edam_terms without match"""
        edam_keywords = {"topics": ["Metabolomics"], "operations": ["Prediction"]}
        self.workflow.edam_topic = ["Genomics"]
        self.workflow.edam_operation = ["Annotation"]

        result = self.workflow.test_edam_terms(edam_keywords)

        self.assertFalse(result)

    def test_test_name_match(self) -> None:
        """Test test_name with matching keywords"""
        keywords = {"keywords": ["metage.*"]}
        self.workflow.name = "Metagenomics Analysis Pipeline"

        result = self.workflow.test_name(keywords)

        self.assertTrue(result)
        self.assertEqual(self.workflow.filtered_on, "metage.* in name")

    def test_test_name_no_match(self) -> None:
        """Test test_name without matching keywords"""
        keywords = {"keywords": ["metage.*"], "acronyms": ["ITS"]}
        self.workflow.name = "Proteomics Analysis Pipeline"

        result = self.workflow.test_name(keywords)

        self.assertFalse(result)

    def test_test_description_match(self) -> None:
        """Test test_description with matching keywords"""
        keywords = {"keywords": ["metage.*"]}
        self.workflow.description = "This workflow analyzes metagenomics data"

        result = self.workflow.test_description(keywords)

        self.assertTrue(result)
        self.assertEqual(self.workflow.filtered_on, "metage.* in description")

    def test_test_description_no_match(self) -> None:
        """Test test_description without matching keywords"""
        keywords = {"keywords": ["metage.*"], "acronyms": ["ITS"]}
        self.workflow.description = "This workflow analyzes RNA-seq data"

        result = self.workflow.test_description(keywords)

        self.assertFalse(result)

    def test_update_status(self) -> None:
        """Test update_status method"""
        wf_status = {"To keep": True, "Curation date": "2025-12-15"}

        self.workflow.update_status(wf_status)

        self.assertTrue(self.workflow.keep)
        self.assertEqual(self.workflow.curation_date, "2025-12-15")


class TestWorkflows(unittest.TestCase):
    """Test cases for Workflows class"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.workflows = Workflows()

    def test_init(self) -> None:
        """Test Workflows initialization"""
        self.assertEqual(self.workflows.workflows, [])
        self.assertFalse(self.workflows.test)
        self.assertEqual(self.workflows.grouped_workflows, {})

    def test_init_with_test_flag(self) -> None:
        """Test Workflows initialization with test flag"""
        workflows = Workflows(test=True)
        self.assertTrue(workflows.test)

    def test_init_by_searching(self) -> None:
        """Test init_by_searching method"""
        self.workflows.test = True
        self.workflows.init_by_searching()

    def test_init_by_importing(self) -> None:
        """Test init_by_importing method"""
        wfs_to_import = [
            {
                "source": "WorkflowHub",
                "id": 1,
                "link": "https://workflowhub.eu/workflows/1",
                "name": "Workflow 1",
                "creators": [],
                "tags": [],
                "create_time": "",
                "update_time": "",
                "latest_version": 1,
                "versions": 1,
                "number_of_steps": 3,
                "tools": [],
                "edam_operation": [],
                "edam_topic": [],
                "license": "",
                "doi": "",
                "projects": [],
                "type": "",
                "description": "",
            },
            {
                "source": "WorkflowHub",
                "id": 2,
                "link": "https://workflowhub.eu/workflows/2",
                "name": "Workflow 2",
                "creators": [],
                "tags": [],
                "create_time": "",
                "update_time": "",
                "latest_version": 1,
                "versions": 1,
                "number_of_steps": 5,
                "tools": [],
                "edam_operation": [],
                "edam_topic": [],
                "license": "",
                "doi": "",
                "projects": [],
                "type": "",
                "description": "",
            },
        ]

        self.workflows.init_by_importing(wfs_to_import)

        self.assertEqual(len(self.workflows.workflows), 2)
        self.assertEqual(self.workflows.workflows[0].id, 1)
        self.assertEqual(self.workflows.workflows[1].id, 2)

    def test_add_workflows_from_workflowhub(self) -> None:
        """Test add_workflows_from_workflowhub method"""
        workflows = Workflows(test=True)
        workflows.add_workflows_from_workflowhub()

        self.assertGreaterEqual(len(workflows.workflows), 10)

    def test_export_workflows_to_dict(self) -> None:
        """Test export_workflows_to_dict method"""
        wf1 = Workflow()
        wf1.name = "Workflow 1"
        wf1.id = 1

        wf2 = Workflow()
        wf2.name = "Workflow 2"
        wf2.id = 2

        self.workflows.workflows = [wf1, wf2]

        result = self.workflows.export_workflows_to_dict()

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "Workflow 1")
        self.assertEqual(result[1]["name"], "Workflow 2")

    def test_filter_workflows_by_tags(self) -> None:
        """Test filter_workflows_by_tags method"""
        wf1 = Workflow()
        wf1.name = "Genomics Workflow"
        wf1.tags = ["genomics"]
        wf1.link = "https://workflowhub.eu/workflows/1"
        wf1.edam_topic = []
        wf1.edam_operation = []
        wf1.description = ""
        wf1.keep = False

        wf2 = Workflow()
        wf2.name = "Proteomics Workflow"
        wf2.tags = ["proteomics"]
        wf2.link = "https://workflowhub.eu/workflows/2"
        wf2.edam_topic = []
        wf2.edam_operation = []
        wf2.description = ""
        wf2.keep = False

        self.workflows.workflows = [wf1, wf2]

        keywords = {
            "keywords": ["genomics"],
            "acronyms": [],
            "edam": {"topics": [], "operations": []},
        }
        wf_status: dict = {}

        self.workflows.filter_workflows_by_tags(keywords, wf_status)

        self.assertEqual(len(self.workflows.workflows), 1)
        self.assertEqual(self.workflows.workflows[0].name, "Genomics Workflow")

    def test_filter_workflows_by_tags_with_status(self) -> None:
        """Test filter_workflows_by_tags with existing status"""
        wf1 = Workflow()
        wf1.link = "https://workflowhub.eu/workflows/1"
        wf1.keep = False

        self.workflows.workflows = [wf1]

        keywords = {
            "keywords": [],
            "acronyms": [],
            "edam": {"topics": [], "operations": []},
        }
        wf_status = {
            "https://workflowhub.eu/workflows/1": {
                "To keep": True,
                "Curation date": "2023-12-15",
                "Filtered on": "manual",
            }
        }

        self.workflows.filter_workflows_by_tags(keywords, wf_status)

        self.assertEqual(len(self.workflows.workflows), 1)
        self.assertTrue(self.workflows.workflows[0].keep)
        self.assertEqual(self.workflows.workflows[0].filtered_on, "manual")

    def test_curate_workflows(self) -> None:
        """Test curate_workflows method"""
        wf1 = Workflow()
        wf1.link = "https://workflowhub.eu/workflows/1"
        wf1.keep = True

        wf2 = Workflow()
        wf2.link = "https://workflowhub.eu/workflows/2"
        wf2.keep = False

        self.workflows.workflows = [wf1, wf2]

        wf_status: dict = {}
        self.workflows.curate_workflows(wf_status)

        self.assertEqual(len(self.workflows.workflows), 1)
        self.assertEqual(self.workflows.workflows[0].link, "https://workflowhub.eu/workflows/1")

    def test_curate_workflows_with_status_update(self) -> None:
        """Test curate_workflows with status update"""
        wf1 = Workflow()
        wf1.link = "https://workflowhub.eu/workflows/1"
        wf1.keep = False
        wf1.curation_date = "0000-00-00"

        self.workflows.workflows = [wf1]

        wf_status = {
            "https://workflowhub.eu/workflows/1": {
                "To keep": True,
                "Curation date": "2023-12-15",
            }
        }

        self.workflows.curate_workflows(wf_status)

        self.assertEqual(len(self.workflows.workflows), 1)
        self.assertTrue(self.workflows.workflows[0].keep)

    def test_export_workflows_to_tsv(self) -> None:
        """Test export_workflows_to_tsv method"""
        wf = Workflow()
        wf.name = "Test Workflow"
        wf.source = "WorkflowHub"
        wf.tools = ["tool1", "tool2"]
        wf.edam_operation = []
        wf.edam_topic = []
        wf.creators = ["John Doe", "Jane Smith"]
        wf.tags = ["metagenomics"]
        wf.projects = ["Project A"]

        self.workflows.workflows = [wf]
        self.workflows.export_workflows_to_tsv("output.tsv")

    def test_export_workflows_to_tsv_with_columns(self) -> None:
        """Test export_workflows_to_tsv with specific columns"""
        wf = Workflow()
        wf.name = "Test Workflow"
        wf.link = "https://workflowhub.eu/workflows/1"

        self.workflows.workflows = [wf]

        to_keep_columns = ["Name", "Link"]
        self.workflows.export_workflows_to_tsv("output.tsv", to_keep_columns)

    @patch("utils.export_to_json")
    def test_extract_tools(self, mock_export: Mock) -> None:
        """Test extract_tools method"""
        wf1 = Workflow()
        wf1.name = "Workflow 1"
        wf1.tools = ["FastQC", "Bowtie2"]

        wf2 = Workflow()
        wf2.name = "Workflow 2"
        wf2.tools = ["FastQC", "STAR"]

        wf3 = Workflow()
        wf3.name = "Workflow 3"
        wf3.tools = []  # Test empty tool name

        self.workflows.workflows = [wf1, wf2, wf3]

        self.workflows.extract_tools("tools.json")

        mock_export.assert_called_once()
        call_args = mock_export.call_args[0]
        tools_dict = call_args[0][0]

        self.assertIn("FastQC", tools_dict)
        self.assertIn("Bowtie2", tools_dict)
        self.assertIn("STAR", tools_dict)
        self.assertEqual(len(tools_dict["FastQC"]), 2)
        self.assertNotIn("", tools_dict)


if __name__ == "__main__":
    unittest.main()
