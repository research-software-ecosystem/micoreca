import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
)

import pandas as pd
import requests
import yaml


def format_date(date: str) -> str:
    return datetime.fromisoformat(date).strftime("%Y-%m-%d")


def format_list_column(col: pd.Series) -> pd.Series:
    """
    Format a column that could be a list before exporting
    """
    return col.apply(lambda x: ", ".join(str(i) for i in x))


def format_regex(pattern: str) -> str:
    """
    Format regex to allow various separators before and after the pattern
    """
    return rf"(?<![A-Za-z]){pattern}(?![A-Za-z])"


def load_yaml(input_df: str) -> Dict:
    """
    Read a YAML file
    """
    with Path(input_df).open("r") as t:
        content = yaml.safe_load(t)
    return content


def load_json(input_df: str) -> Any:
    """
    Read a JSON file
    """
    with Path(input_df).open("r") as t:
        content = json.load(t)
    return content

def tags_has_keyword(keywords_list: dict, target_tags: List[str]) -> str:
    """
    Search for keywords and acronyms in tags with IGNORECASE
    """
    for tag in keywords_list:
        regex = re.compile(format_regex(tag), re.IGNORECASE)
        if any(regex.search(wtag) for wtag in target_tags):
            return f"{tag} in tags"
    return ""

def has_keyword(tags: dict, target: str, target_name: str) -> str:
    """
    Search for keywords and acronyms in target
    """
    for tag in tags["keywords"]:
        regexk = re.compile(format_regex(tag), re.IGNORECASE)
        if regexk.search(target):
            return f"{tag} in {target_name}"

    for acron in tags["acronyms"]:
        regexa = re.compile(format_regex(acron))
        if regexa.search(target):
            return f"{acron} in {target_name}"

    return ""


def export_to_json(data: List[Dict], output_fp: str) -> None:
    """
    Export to a JSON file
    """
    with Path(output_fp).open("w") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def get_edam_operation_from_tools(selected_tools: list, all_tools: dict) -> List:
    """
    NOT RUN

    Get list of EDAM operations of the tools

    :param selected_tools: list of tool suite ids
    :param all_tools: dictionary with information about all tools
    """
    edam_operation = set()
    for t in selected_tools:
        if t in all_tools:
            edam_operation.update(set(all_tools[t]["EDAM operations"]))
        else:
            print(f"{t} not found in all tools")
    return list(edam_operation)


def shorten_tool_id(tool: str) -> str:
    """
    Shorten tool id
    """
    if "toolshed" in tool:
        return tool.split("/")[-2]
    else:
        return tool


def get_request_json(url: str, headers: dict, retries: int = 3, delay: float = 2.0) -> dict:
    """
    Perform a GET request to retrieve JSON output from a specified URL, with retry on ConnectionError.

    :param url: URL to send the GET request to.
    :param headers: Headers to include in the GET request.
    :param retries: Number of retry attempts in case of a ConnectionError (default is 3).
    :param delay: Delay in seconds between retries (default is 2.0 seconds).
    :return: JSON response as a dictionary, or None if all retries fail.
    :raises ConnectionError: If all retry attempts fail due to a connection error.
    :raises SystemExit: For any other request-related errors.
    """
    attempt = 0  # Track the number of attempts

    while attempt < retries:
        try:
            r = requests.get(url, auth=None, headers=headers)
            r.raise_for_status()  # Raises an HTTPError for unsuccessful status codes
            return r.json()  # Return JSON response if successful
        except ConnectionError as e:
            attempt += 1
            if attempt == retries:
                raise ConnectionError(
                    "Connection aborted after multiple retries: Remote end closed connection without response"
                ) from e
            print(f"Connection error on attempt {attempt}/{retries}. Retrying in {delay} seconds...")
            time.sleep(delay)  # Wait before retrying
        except requests.exceptions.RequestException as e:
            # Handles all other exceptions from the requests library
            raise SystemExit(f"Request failed: {e}")
        except ValueError as e:
            # Handles cases where the response isn't valid JSON
            raise ValueError("Response content is not valid JSON") from e

    # Return None if all retries are exhausted and no response is received
    return {}
