"""Script for WorkflowHub extraction"""
#!/usr/bin/env python

import argparse
import re
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

import pandas as pd
import utils


class Workflow:
    """
    Class for workflow
    """

    def __init__(self) -> None:
        self.source = ""
        self.id = 0
        self.link = ""
        self.name = ""
        self.creators: List[str] = []
        self.tags: List[str] = []
        self.create_time = ""
        self.update_time = ""
        self.latest_version = 0
        self.versions = 0
        self.number_of_steps = 0
        self.tools: List[str] = []
        self.edam_operation: List[str] = []
        self.edam_topic: List[str] = []
        self.license = ""
        self.doi = ""
        self.projects: List[str] = []
        self.keep = False
        self.type = ""
        self.description = ""
        self.filtered_on = ""

    def init_by_importing(self, wf: dict) -> None:
        """
        Init Workflow instance by importing
        
        :param wf: workflow metadata
        :type wf: dict
        """
        self.source = wf["source"]
        self.id = wf["id"]
        self.link = wf["link"]
        self.name = wf["name"]
        self.creators = wf["creators"]
        self.tags = wf["tags"]
        self.create_time = wf["create_time"]
        self.update_time = wf["update_time"]
        self.latest_version = wf["latest_version"]
        self.versions = wf["versions"]
        self.number_of_steps = wf["number_of_steps"]
        self.tools = wf["tools"]
        self.edam_operation = wf["edam_operation"]
        self.edam_topic = wf["edam_topic"]
        self.license = wf["license"]
        self.doi = wf["doi"]
        self.projects = wf["projects"]
        self.type = wf["type"]
        self.description = wf["description"]
        if "keep" in wf:
            self.keep = wf["keep"]

    def init_from_search(self, wf: dict, source: str) -> None:
        """
        Init Workflow instance from search
        
        :param wf: workflow metadata
        :type wf: dict
        :param source: extraction source
        :type source: str
        """
        self.source = source
        self.id = wf["data"]["id"]
        self.link = f"https:/{ source.lower() }.eu{ wf['data']['links']['self'] }"
        self.name = wf["data"]["attributes"]["title"]
        self.tags = [w.lower() for w in wf["data"]["attributes"]["tags"]]
        self.create_time = utils.format_date(wf["data"]["attributes"]["created_at"])
        self.update_time = utils.format_date(wf["data"]["attributes"]["updated_at"])
        self.latest_version = wf["data"]["attributes"]["latest_version"]
        self.versions = len(wf["data"]["attributes"]["versions"])
        internals = wf["data"]["attributes"].get("internals", {})
        steps = internals.get("steps")
        if steps is not None:
            self.number_of_steps = len(steps)
        else:
            self.number_of_steps = 0
        self.license = wf["data"]["attributes"]["license"]
        self.doi = wf["data"]["attributes"]["doi"]
        self.edam_topic = [t["label"] for t in wf["data"]["attributes"]["topic_annotations"]]
        self.edam_operation = [
            t["label"] for t in wf["data"]["attributes"]["operation_annotations"]]
        self.type = wf["data"]["attributes"]["workflow_class"]["title"]
        self.description = wf["data"]["attributes"]["description"]

        self.add_creators(wf)
        self.add_tools(wf)
        # self.edam_operation = utils.get_edam_operation_from_tools(self.tools)
        self.add_projects(wf)

    def add_creators(self, wf: dict) -> None:
        """
        Get workflow creators
        """
        self.creators = []
        creators = wf["data"]["attributes"]["creators"]
        if len(creators) == 0:
            other = wf["data"]["attributes"]["other_creators"]
            if other and len(other) > 0:
                self.creators.extend(wf["data"]["attributes"]["other_creators"].split(","))
        else:
            self.creators.extend([f"{c['given_name']} {c['family_name']}" for c in creators])

    def add_tools(self, wf: dict) -> None:
        """
        Extract list of tool ids from workflow
        """
        tools = set()
        # Use steps description when no tools are provided or for Galaxy workflows
        if len(wf["data"]["attributes"]["tools"]) == 0 or self.type == "Galaxy":
            internals = wf["data"]["attributes"].get("internals", {})
            steps = internals.get("steps")
            if steps is not None:
                for tool in steps:
                    if tool.get("description") is not None:
                        tools.add(utils.shorten_tool_id(tool["description"]))
                    elif tool.get("name") is not None:
                        tools.add(tool["name"])

            self.tools = list(tools)
        else:
            self.tools = [t["name"] for t in wf["data"]["attributes"]["tools"]]

    def add_projects(self, wf: dict) -> None:
        """
        Extract projects associated to workflow on WorkflowHub
        """
        for project in wf["data"]["relationships"]["projects"]["data"]:
            wfhub_project = utils.get_request_json(
                f"https://{ self.source.lower() }.eu/projects/{project['id']}",
                {"Accept": "application/json"},
            )
            wf_data = wfhub_project["data"]
            wf_attributes = wfhub_project["data"]["attributes"]
            if "attributes" in wf_data and "title" in wf_attributes:
                self.projects.append(wf_attributes["title"])

    def test_tags(self, keywords_to_search: dict) -> bool:
        """
        Test if there are overlap between workflow tags and target tags
        """
        # Put keywords and acronyms together since tags are saved in lowercase
        keywords_list = keywords_to_search["keywords"] + keywords_to_search["acronyms"]
        for tag in keywords_list:
            regex = re.compile(utils.format_regex(tag), re.IGNORECASE)
            if any(regex.search(wtag) for wtag in self.tags):
                self.filtered_on = f"{tag} in tags"
                return True
        return False

    def test_edam_terms(self, edam_keywords: dict) -> bool:
        """
        Test if workflow topics or operations are in keywords
        """
        matches_topic = set(self.edam_topic) & set(edam_keywords["topics"])
        matches_operation = set(self.edam_operation) & set(edam_keywords["operations"])

        if len(matches_topic) != 0 or len(matches_operation) != 0:
            self.filtered_on = "edam"

        return len(matches_topic) != 0 or len(matches_operation) != 0

    def test_name(self, keywords_to_search: dict) -> bool:
        """
        Test if there are overlap between workflow name and target tags
        """
        filtered_on = utils.has_keyword(keywords_to_search, self.name, "name")
        if filtered_on != "":
            self.filtered_on = filtered_on
            return True
        return False

    def test_description(self, keywords_to_search: dict) -> bool:
        """
        Test if there are overlap between workflow description and target tags
        """
        filtered_on = utils.has_keyword(keywords_to_search, self.description, "description")
        if filtered_on != "":
            self.filtered_on = filtered_on
            return True
        return False

    def update_status(self, wf_status: dict) -> None:
        """
        Update status from status table
        """
        self.keep = wf_status["To keep"]

    def get_import_link(self) -> str:
        """
        Get import link
        """
        return (
            "{{ galaxy_base_url }}"
            + f"/workflows/trs_import?trs_server={ self.source.lower() }\
            .eu&run_form=true&trs_id={ self.id }"
        )

    def get_description(self) -> str:
        """
        Get description with EDAM operations and EDAM topics
        """
        description = ""
        prefix = "Workflow covering"
        if len(self.edam_operation) > 0:
            description += f"{ prefix } operations related to { ','.join(self.edam_operation) }"
            prefix = "on"
        if len(self.edam_topic) > 0:
            description += f"{ prefix } topics related to { ','.join(self.edam_topic) }"
        return description


class Workflows:
    """
    Class Workflows
    """

    def __init__(self, test: bool = False) -> None:
        self.workflows: List[Workflow] = []
        self.test = test
        self.grouped_workflows: Dict[Any, Any] = {}

    def init_by_searching(self) -> None:
        """
        Search for workflows in workflowhub
        """
        self.add_workflows_from_workflowhub()

    def init_by_importing(self, wfs_to_import: dict) -> None:
        """
        Loads the workflows from a dict following the structure 
        in communities/all/resources/test_workflows.json
        (the json created by init_by_searching)
        """
        for iwf in wfs_to_import:
            wf = Workflow()
            wf.init_by_importing(iwf)
            self.workflows.append(wf)

    def add_workflows_from_workflowhub(self, prefix: str = "") -> None:
        """
        Add workflows from WorkflowHub
        """
        header = {"Accept": "application/json"}
        wfhub_wfs = utils.get_request_json(
            f"https://{ prefix }workflowhub.eu/workflows",
            header,
        )
        print(f"Workflows from WorkflowHub: {len(wfhub_wfs['data'])}")
        data = wfhub_wfs["data"]
        print(data[1])
        if self.test:
            data = data[:10]
        for wf in data:
            wfhub_wf = utils.get_request_json(
                f"https://{ prefix }workflowhub.eu{wf['links']['self']}",
                header,
            )
            if wfhub_wf:
                wf = Workflow()
                wf.init_from_search(wf=wfhub_wf, source=f"{ prefix }WorkflowHub")
                self.workflows.append(wf)

            if len(self.workflows) / 10 % 1 == 0:
                print(f"Workflows saved: {len(self.workflows)}")
        print(len(self.workflows))

    def export_workflows_to_dict(self) -> List:
        """
        Export workflows as dictionary
        """
        return [w.__dict__ for w in self.workflows]

    def filter_workflows_by_tags(self, keywords: dict, wf_status: Dict) -> None:
        """
        Filter workflows by keywords
        """
        to_keep_wf = []
        for w in self.workflows:
            if w.link in wf_status:
                w.update_status(wf_status[w.link])
            # If workflow status is True, skip test and keep it
            if w.keep:
                to_keep_wf.append(w)
                w.filtered_on = wf_status[w.link]["Filtered on"]
            elif w.test_edam_terms(keywords["edam"]):
                to_keep_wf.append(w)
            elif w.test_tags(keywords):
                to_keep_wf.append(w)
            elif w.test_name(keywords):
                to_keep_wf.append(w)
            elif w.test_description(keywords):
                to_keep_wf.append(w)
        self.workflows = to_keep_wf

    def curate_workflows(self, wf_status: Dict) -> None:
        """
        Curate workflows based on community feedback
        """
        curated_wfs = []
        for w in self.workflows:
            if w.link in wf_status:
                w.update_status(wf_status[w.link])
            if w.keep:
                curated_wfs.append(w)
        self.workflows = curated_wfs

    def export_workflows_to_tsv(self, output_fp: str,
                                to_keep_columns: Optional[List[str]] = None) -> None:
        """
        Export workflows to a TSV file
        """
        renaming = {
            "name": "Name",
            "source": "Source",
            "id": "ID",
            "link": "Link",
            "creators": "Creators",
            "type": "Type",
            "tags": "Tags",
            "create_time": "Creation time",
            "update_time": "Update time",
            "latest_version": "Latest version",
            "versions": "Versions",
            "number_of_steps": "Number of steps",
            "tools": "Tools",
            "edam_operation": "EDAM operations",
            "edam_topic": "EDAM topics",
            "license": "License",
            "doi": "DOI",
            "projects": "Projects",
            "filtered_on": "Filtered on",
            "keep": "To keep",
        }

        df = pd.DataFrame(self.export_workflows_to_dict())

        for col in ["tools", "edam_operation", "edam_topic", "creators", "tags", "projects"]:
            df[col] = utils.format_list_column(df[col])

        df = (
            df.sort_values(by=["projects"]).rename(columns=renaming)
            .fillna("").reindex(columns=list(renaming.values()))
        )

        if to_keep_columns is not None:
            df = df[to_keep_columns]

        df.to_csv(output_fp, sep="\t", index=False)

    def extract_tools(self, output_tools: str):
        """
        Extract tools information for workflows
        
        :param output_tools: Path to JSON to save tools
        :type output_tools: str
        """
        tools_dict = {}
        for wf in self.workflows:
            tools_list = wf.tools
            for tool in tools_list:
                clean_tool_name = tool.replace("\n ", "")
                if clean_tool_name != "":
                    if clean_tool_name in tools_dict:
                        tools_dict[clean_tool_name].append(wf.name)
                    else:
                        tools_dict[clean_tool_name] = [wf.name]

        utils.export_to_json(tools_dict, output_tools)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract Workflows from WorkflowHub")
    subparser = parser.add_subparsers(dest="command")

    # Extract Workflows
    extract = subparser.add_parser("extract", help="Extract all workflows")
    extract.add_argument("--all", "-o", required=True,
                         help="Filepath to JSON with all extracted workflows")
    extract.add_argument(
        "--test",
        action="store_true",
        default=False,
        required=False,
        help="Run a small test case only on one topic",
    )

    # Filter workflows
    filterwf = subparser.add_parser("filter", help="Filter workflows based on their tags")
    filterwf.add_argument(
        "--all",
        "-a",
        required=True,
        help="Filepath to JSON with all extracted workflows, generated by extract command",
    )
    filterwf.add_argument(
        "--filtered",
        "-f",
        required=True,
        help="Filepath to JSON with filtered workflows",
    )
    filterwf.add_argument(
        "--tsv-filtered",
        "-t",
        required=True,
        help="Filepath to TSV with filtered workflows",
    )
    filterwf.add_argument(
        "--tags",
        "-c",
        required=True,
        help="Path to a YAML file with the EDAM terms and keywords for the filtering",
    )
    filterwf.add_argument(
        "--status",
        "-s",
        help="Path to a TSV file with workflow status",
    )

    # Curate workflow
    curatewf = subparser.add_parser("curate", help="Curate workflows based on community review")
    curatewf.add_argument(
        "--filtered",
        "-f",
        required=True,
        help="Filepath to JSON with workflows filtered based on tags",
    )
    curatewf.add_argument(
        "--curated",
        "-c",
        required=True,
        help="Filepath to JSON with curated workflows",
    )
    curatewf.add_argument(
        "--tsv-curated",
        "-t",
        required=True,
        help="Filepath to TSV with curated workflows",
    )
    curatewf.add_argument(
        "--status",
        "-s",
        required=True,
        help="Path to a TSV file with at least column 'link' and 'To keep'",
    )

    # Extract tools from workflows
    extractools = subparser.add_parser("extract_tools", help="Extract tools ")
    extractools.add_argument(
        "--workflows",
        "-w",
        required=True,
        help="Filepath to JSON with curated workflows"
    )
    extractools.add_argument(
        "--tools",
        "-t",
        required=True,
        help="Filepath to a JSON file to save tools"
    )

    args = parser.parse_args()

    # Extract all workflows from WorkflowHub
    if args.command == "extract":
        wfs = Workflows(test=args.test)
        wfs.init_by_searching()
        utils.export_to_json(wfs.export_workflows_to_dict(), args.all)

    # Filter the workflows
    elif args.command == "filter":
        wfs = Workflows()
        wfs.init_by_importing(wfs_to_import=utils.load_json(args.all))
        tags = utils.load_yaml(args.tags)
        # get status if file provided
        if args.status:
            try:
                status = pd.read_csv(args.status, sep="\t", index_col="Link").to_dict("index")
            except FileNotFoundError:
                status = {}
        else:
            status = {}
        wfs.filter_workflows_by_tags(tags, status)
        utils.export_to_json(wfs.export_workflows_to_dict(), args.filtered)
        wfs.export_workflows_to_tsv(args.tsv_filtered)
        wfs.export_workflows_to_tsv(
            args.status,
            to_keep_columns=[
                "Link",
                "Name",
                "Source",
                "Projects",
                "Creators",
                "Creation time",
                "Update time",
                "Filtered on",
                "To keep",
            ],
        )

    # Curate workflows list based on status column
    elif args.command == "curate":
        wfs = Workflows()
        wfs.init_by_importing(wfs_to_import=utils.load_json(args.filtered))
        try:
            status = pd.read_csv(args.status, sep="\t", index_col="Link").to_dict("index")
        except ValueError as ex:
            print(f"Failed to load {args.status} file or no 'Link' column with:\n{ex}")
            print("Not assigning tool status for this community !")
            status = {}
        wfs.curate_workflows(status)
        try:
            utils.export_to_json(wfs.export_workflows_to_dict(), args.curated)
            wfs.export_workflows_to_tsv(args.tsv_curated)
        except Warning:
            print("No workflow extracted after curation.")

    # Extract all tools used in a list of workflows
    elif args.command == "extract_tools":
        wfs = Workflows()
        wfs.init_by_importing(wfs_to_import=utils.load_json(args.workflows))
        try:
            wfs.extract_tools(output_tools=args.tools)
        except FileNotFoundError as ex:
            print(f"Failed to load JSON file {args.workflows} or to extract tools.\n{ex}")
