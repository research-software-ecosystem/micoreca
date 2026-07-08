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

- Extract tools used in curated workflows as JSON

    ```
    $ python bin/extract_workflowhub.py \
        extract_tools \
        --workflows content/workflowhub/workflows_curated.json \
        --tools content/workflowhub/tools_from_workflows.json
    ```

## RSEC

The RSEc [content repository](https://github.com/research-software-ecosystem/content) is the single upstream source. It is never committed here: `filter` sparse-clones it into a temporary directory, filters it, then removes the clone. Only the post-filter outputs are committed.

Three trees are filtered from one clone:

- `data/` (bio.tools-mapped tools) → `content/rsec/` (`validated_tools_metadata.json`, `validated_tools_summary.tsv`, `filtering_report.txt`).
- `imports/bioconda/` (conda recipes not mapped to bio.tools) → `content/bioconda/` (`bioconda_filtered.json/.tsv`).
- `imports/galaxy/` (Galaxy tools not mapped to bio.tools) → `content/galaxy/` (`galaxy_filtered.json/.tsv`).

- Filter all three trees based on EDAM terms and keywords defined in `keywords.yml`.

    ```
    $ python bin/extract_rsec.py filter --kw keywords.yml
    ```

    `data/` tools are filtered against three successive criteria: EDAM topics/operations from bio.tools metadata, keywords and acronyms from BioContainers metadata, then the same matching on free-text descriptions from bio.tools, BioContainers and Galaxy. A tool is kept if it passes any of them. bioconda imports are matched on their `about` summary/description; galaxy imports on EDAM topics/operations then name/description.

    Each filter also writes a `*_status.tsv` with a keep column for later community review. The curation step that consumes it is not part of this pipeline yet.

