# Script to get Microbiome Community Resource Catalogue

## WorkflowHub

- Extract all workflows metadata from WorkflowHub as a JSON file. The list of tools is obtained either from the tool attribute of WorkflowHub if provided or from the steps description. 

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

    As explained in the decision tree above, workflows are filtered first on EDAM terms (topics and operations), then on tags, workflow name and finally description based on the keywords provided in `keywords.yml` file. 

- Curate workflows based on community curation
    
    ```
    $ python bin/extract_workflowhub.py \
        curate \
        --filtered content/workflowhub/workflows_filtered.json \
        --curated content/workflowhub/workflows_curated.json \
        --tsv-curated content/workflowhub/workflows_curated.tsv \
        --status content/workflowhub/workflows_status.tsv
    ```

    This keeps only workflows in the scope of microbiome analysis. 
