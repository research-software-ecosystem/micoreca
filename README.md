# Microbiome Community Resource Catalogue (MiCoReCa)

The rapid growth of microbiome research has led to the development of numerous bioinformatics tools and databases, but information about them remains fragmented across disparate, often outdated cataloging efforts, hindering resource discovery and utilization.

To address this critical gap, the [ELIXIR Microbiome Community](https://elixir-europe.org/communities/microbiome) collaborates with the [Research Software Ecosystem](https://research-software-ecosystem.github.io/) to create MiCoReCa (Microbiome Community Resource Catalogue), a comprehensive, dynamic, open-access catalogue of microbiome-related bioinformatics resources:
- Tools from [Research Software Ecosystem Atlas](https://research-software-ecosystem.github.io/RSEc-Atlas/)
- Workflows from [WorkflowHub](https://workflowhub.eu/)
- Training
- Standards
- Databases

The extraction, filtering and curation are done following the workflow below and using the defined keywords in the [`keywords.yml` file](keywords.yml):

![A workflow diagram illustrating the process for populating the RSEC Atlas, starting with 'Scrapping' resources from Bioconda, WorkflowHub, and Elixir, which yields over 40,000 tools and 1,300 workflows. This pool is reduced by the 'Filtering for Microbiome Resources' step to about 5,000 tools and 600 workflows. After 'Community Curation,' the items are 'Displayed on RSEC Atlas.' A detailed flowchart on the right explains the filtering logic: it sequentially checks if EDAM topics are found, if defined keywords are in the tags, if keywords are in the title, and finally if keywords are in the description. A 'Yes' at any step classifies the item as a 'MiCoCo resource,' while a 'No' at all steps classifies it as 'Not a MiCoCo resource.'](doc/main_figure_poster.png)

# Prepare environment

- Install virtualenv (if not already there)

    ```
    $ python3 -m pip install --user virtualenv
    ```

- Create virtual environment

    ```
    $ python3 -m venv env
    ```

- Activate virtual environment

    ```
    $ source env/bin/activate
    ```

- Install requirements

    ```
    $ python3 -m pip install -r requirements.txt
    ```

# Extract workflows from WorkflowHub

- Extract all workflows metadata from WorkflowHub as a JSON file

    ```
    $ python bin/extract_workflowhub.py \
        extract \
        --all content/workflowhub/workflows_full.json
    ```

- Filter workflows based on keywords and EDAM terms

    ```
    $ python bin/extract_workflowhub.py \
        filter \
        --all content/workflowhub/workflows_full.json \
        --filtered content/workflowhub/workflows_filtered.json \
        --tsv-filtered content/workflowhub/workflows_filtered.tsv \
        --tags keywords.yml \
        --status content/workflowhub/workflows_status.tsv
    ```
# RSEc

- Extract all metadata from RSEc/content/data 

    ```
    $ python bin/extract_rsec.py 
    ```

- Filter RSEc tools based on keywords and EDAM terms, place them in content/rsec

    ```
    $ python bin/filter_rsec.py
    ```
    As explained in the decision tree above, workflows are filtered first on EDAM terms (topics and operations), then on tags, workflow name and finally description based on the keywords provided in `keywords.yml` file.


# Run the unit tests locally

```
PYTHONPATH=bin python -m unittest discover -s bin/tests
```

# Contributing

To contribute to the MiCoReCa Source code:
1. Fork the repository,
2. Create a branch and add your changes
3. Add a unit test for your changes (see [unittests](sources/bin/tests) for examples).  
    **Warning:** new functions now require a unit test to be merged!
4. Make a pull request.

The `unittest` framework will run on your PR. Please fix the tests if required.

Upon review the maintainer will merge your pull request. 
Automatic tests will run on the dev branch. 


