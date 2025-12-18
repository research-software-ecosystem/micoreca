---
title: 'BioHackEU25 report project 16: MiCoReCa (Microbiome Community Resource Catalogue) - Towards Centralized Curation and Integration of Microbiome Bioinformatics Resources'
title_short: 'BioHackEU25 #16: MiCoReCa'
tags:
  - microbiome
  - catalogue
  - microbiome-related bioinformatics resources
  - microbiome community
authors:
  - name: Vivek Ashokan
    orcid: 0009-0006-1470-3999
    affiliation: 1
    role: Colead, Conceptualization, Development, Data curation
  - name: Clara Emery
    orcid: 0009-0003-9572-6671
    affiliation: 2, 3
    role: Writing – original draft, Development, Data curation
  - name: Agnès Barnabé
    orcid: 0000-0002-8420-7556
    affiliation: 4, 5
    role: Development, Manual curation
  - name: Valentin Loux
    orcid: 0000-0002-8268-915X
    affiliation: 4
    role: Manual curation
  - name: Christina Pavloudi
    orcid: 0000-0001-5106-6067
    affiliation: 8
    role: Manual curation
  - name: Paul Zierep
    orcid: 0000-0003-2982-388X
    affiliation: 9
    role: Development
  - name: Nikolaos Strepis
    orcid: 0000-0002-0997-8430
    affiliation: 10
    role: Colead, Conceptualization, Manual curationWriting – review & editing
  - name: Bérénice Batut
    affiliation: 2, 11
    role: Colead, Conceptualization, Development, Manual curation, Writing – review & editing
    orcid: 0000-0001-9852-1987
affiliations:
  - name: LABGeM (Laboratory of Bioinformatics Analyses for Genomics and Metabolism), Genoscope, IBFJ, DFR, CEA, 91000 Evry-Courcouronnes, France
    ror: 028pnqf58
    index: 1 
  - name: IFB-core, Institut Français de Bioinformatique (IFB), CNRS, INSERM, INRAE, CEA, 94800 Villejuif, France
    ror: 045f7pv37
    index: 2
  - name: ABiMS - Analysis and Bioinformatics for Marine Science Roscoff Marine Station 
    ror: 03s0pzj56
    index: 3
  - name: Migale bioinformatics facility, MaIAGE, BioInfomics, INRAE, 78350 Jouy-en-Josas, France
    ror: 05qdnns64
    index: 4
  - name: Ferments du Futur (US INRAE 1503), 91400 Orsay, France
    index: 7
  - name: European Marine Biological Resource Centre (EMBRC-ERIC), Paris, France
    ror: 0038zss60
    index: 8
  - name: Bioinformatics Group, Department of Computer Science, University of Freiburg, Georges-Koehler-Allee 106, D-79110 Freiburg, Germany
    ror: 0245cg223
    index: 9
  - name: Department of Pathology and Clinical Bioinformatics, Erasmus MC Cancer Institute, Erasmus MC, Rotterdam, Netherlands
    ror: 03r4m3349
    index: 10
  - name: Plateforme AuBi, Mésocentre Clermont-Auvergne, Université Clermont Auvergne, Aubière, France
    ror: 01a8ajp46
    index: 11
date: 17 December 2025
cito-bibliography: paper.bib
event: BH25EU
biohackathon_name: "BioHackathon Europe 2025"
biohackathon_url: "https://biohackathon-europe.org/"
biohackathon_location: "Berlin, Germany, 2025"
group: Project 16
# URL to project git repo --- should contain the actual paper.md:
git_url: https://github.com/research-software-ecosystem/micoreca/
# This is the short authors description that is used at the
# bottom of the generated paper (typically the first two authors):
authors_short: Vivek Ashokan, Clara Emery, \emph{et al.}
---

# Introduction

The rapid expansion of microbiome research has led to the development of countless bioinformatics tools, workflows, and databases. However, information about these resources remains scattered across disparate, often outdated catalogs, impeding their discovery and effective use (citation). To address this critical gap, the [ELIXIR Microbiome Community](https://elixir-europe.org/communities/microbiome) [@citesForInformation:finn2025establishing] — a specialized group within [ELIXIR](https://elixir-europe.org/), Europe's leading infrastructure for biological data —proposed the creation of **MiCoReCa (Microbiome Community Resource Catalogue)**. This open-access, dynamic catalog aims to centralize and streamline access to microbiome-related bioinformatics resources, including tools, workflows, training materials, and more.

MiCoReCa integrates resources from established platforms such as [Bioconda](https://bioconda.github.io/) (a package manager for bioinformatics software) [@citesAsAuthority:gruning2018bioconda], [bio.tools](https://bio.tools/) (the registry of bioinformatics tools and services developed by ELIXIR) [@citesAsAuthority:ison2016tools; @citesAsAuthority:ison2019bio] via the [Research Software Ecosystem (RSEc) Atlas](https://research-software-ecosystem.github.io/RSEc-Atlas/), [WorkflowHub](https://workflowhub.eu/) (a repository for scientific workflows, maintained by ELIXIR) [@citesAsAuthority:gustafsson2025workflowhub], and [TeSS](https://tess.elixir-europe.org/) (the ELIXIR training materials database) [@citesAsAuthority:beard2020tess]. By aggregating resources from these sources, MiCoReCa ensures comprehensive coverage of the microbiome bioinformatics landscape.

This report presents the **work accomplished during the [ELIXIR BioHackathon 2025](https://biohackathon-europe.org/)**—an intensive collaborative event where researchers, developers, and bioinformatics experts come together to tackle scientific challenges. During this event, the MiCoReCa team initiated the development of the catalog, focusing on automating resource extraction (e.g., via weekly GitHub Actions scripts), filtering resources using community-defined keywords, and establishing a framework for collaborative curation, inspired by the [Galaxy Codex](https://github.com/galaxyproject/galaxy_codex) [@citesAsAuthority:zierep_how_2024].

To maximize interoperability, MiCoReCa leverages the **standardized ontology** [EDAM](https://edamontology.org/page) [@citesAsAuthority:ison2013edam], which provides a structured vocabulary for describing bioinformatics tools, workflows, and data. This ensures that resources in MiCoReCa are consistently annotated, making them easier to discover and integrate into research workflows.

A defining feature of MiCoReCa is its **community-driven curation process**, where experts collaboratively identify missing ontological terms and metadata, ensuring the catalog remains **accurate, up-to-date, and aligned with researchers' needs**.

Beyond serving as a vital resource for the microbiome field—enhancing research efficiency and reproducibility—MiCoReCa is designed as a **scalable and adaptable infrastructure**, potentially applicable to other ELIXIR Communities. This initiative underscores the ELIXIR Microbiome Community's commitment to **streamlining microbiome bioinformatics** and fostering collaboration across disciplines.

# Objectives before the ELIXIR BioHackathon 2025

Before the ELIXIR BioHackathon 2025, the following objectives were defined to guide the development and implementation of MiCoReCa:

1. **Extract and Expose Microbiome Resources from the ELIXIR Ecosystem and Bioconda** to create a comprehensive inventory of microbiome resources
    1. **Identify Keywords for Resource Filtering** on platforms such as **RSEc-Atlas**, **WorkflowHub**, **TeSS**, and **Bioconda**.
    2. **Coordinate with the Research Software Ecosystem (RSEc)** to ensure the inclusion of the microbiome community in the **RSEc-Atlas**.
    3. **Extract and Filter Microbiome Resources**: Automate the extraction and filtering of microbiome resources by scrapping
        1. **RSEc-Atlas** and **BioConda** for tools,
        2. **WorkflowHub** for workflows,
        3. **TeSS** for training resources.
   4. **Identify Missing Microbiome Tools in bio.tools** by comparing resources in Bioconda and WorkflowHub to those listed in bio.tools.
   5. **Create a Microbiome Resource Catalog Page** to expose all extracted microbiome resources as a searchable and accessible catalog.
   
2. **Expand, Curate, and Improve Annotation of Microbiome Resources** to ensure the accuracy, relevance, and usability of the catalog
    1. **Curate Extracted Resources** by reviewing with Microbiome community the extracted and filtered resources to ensure their quality and relevance.
    2. **Improve Tool Annotations** on **bio.tools** using standardized ontologies such as **EDAM**.
    3. **Add Microbiome tools** found in **Bioconda** and **WorkflowHub** but missing in **bio.tools**.
    4. **Engage in discussions** to refine and expand **EDAM** terms related to **Topics**, **Formats**, **Operations**, and **Data** for microbiome analysis.

3. **Document the Process**—from resource extraction and filtering to curation and annotation—**for Reusability by Other Communities** to ensure the sustainability and scalability of MiCoReCa.

These objectives laid the foundation for the work accomplished during the ELIXIR BioHackathon 2025, ensuring a structured and collaborative approach to building MiCoReCa.

# Achievements During ELIXIR BioHackathon 2025

The ELIXIR BioHackathon 2025 brought together a diverse group of participants, including both onsite and online contributors, fostering a collaborative environment to advance the MiCoReCa project. Coordination was streamlined through a dedicated **Slack channel**, where real-time discussions and updates took place, complemented by **daily morning meetings** to align on progress and priorities. To ensure clarity and efficiency, the project leads prepared a [**coordination document**](https://docs.google.com/document/d/1by0oFCX4yUC6sa2emccpaTWfL4xLOkZeHRJgVkg5tM0/edit?tab=t.0#heading=h.9xt4wmskjuvi) outlining task descriptions and a [**tracking spreadsheet**](https://docs.google.com/spreadsheets/d/1NY3d-hB_bhqRve9ItBcmCgVZ9UozWOe5j0UAGYDRJJY/edit?gid=0#gid=0) to monitor progress throughout the event. At the outset of the BioHackathon, a [**GitHub repository**](https://github.com/research-software-ecosystem/micoreca) was established inside the RSEc GitHub organization to centralize code, documentation, and collaborative efforts, providing a structured platform for version control and teamwork. This framework enabled the team to effectively tackle the objectives, resulting in significant progress toward building a comprehensive and curated microbiome resource catalog.

In this section, we highlight the key accomplishments made during the BioHackathon, demonstrating how the collective efforts of the MiCoReCa team advanced the development of the Microbiome Community Resource Catalogue.

## Establishing Community-approved Keywords For Microbiome Resources Discovery

A central objective of MiCoReCa was to define a set of keywords that accurately represent the diverse landscape of microbiome computational tools and workflows. To ensure the catalog aligns with both **user needs** and **scientific relevance**, the project engaged the microbiome research community, harnessing their collective expertise to curate a keyword set that reflects real-world research practices. The development of these keywords was guided by the need for **platform compatibility**, ensuring seamless integration with the query structures of key repositories such as the **RSEc Atlas**, **WorkflowHub**, and **Bioconda**.

The keyword strategy was designed around **three distinct types of terms**:
- **EDAM terms**, focusing on **topics** ("Metagenomics," "Metatranscriptomics", "Metabarcoding") and **operations** ("Read binning") to ensure alignment with standardized ontologies.
- **General keywords**, structured as **regular expressions** (e.g., `metage.*`, `microbiom.*`) to flexibly capture variations in terminology and maximize resource discovery.
- **Acronyms** (**ITS**, **OTU**, **ASV**), which are widely used in microbiome research and essential for identifying relevant tools and workflows.

To maintain **domain specificity**, the keyword set was deliberately scoped to **microbiome research**, explicitly excluding terms related to **general microbiology** or **single-genome analysis**. By combining **community-driven input**, **technical precision**, and **domain expertise**, this keyword framework ensures that MiCoReCa serves as a **targeted, comprehensive, and user-centric resource** for the microbiome research community. The **full list of keywords** is available in the [MiCoReCa GitHub repository](https://github.com/research-software-ecosystem/micoreca/blob/main/keywords.yml), providing transparency and enabling further community contributions and refinements.

## Automated Scraping, Filtering, and Community Curation: A Reproducible Pipeline for Microbiome Resource Discovery

To systematically identify, filter, and curate microbiome-specific resources within the ELIXIR ecosystem, we designed and implemented a **multi-stage, automated pipeline** (Figure \ref{workflow}). This approach ensures that only the most relevant tools and workflows are included in the MiCoReCa catalog, combining efficiency with scientific precision. The pipeline begins with an **automated scraping stage**, where scripts aggregate comprehensive lists of tools and workflows from key repositories such as **Bioconda** and **WorkflowHub**.

![**Workflow Diagram**: The process for populating the catalog on RSEc Atlas, starting with scraping resources from Bioconda, RSEc, WorkflowHub, and TeSS, followed by filtering for microbiome-specific resources, community curation, and final display on the RSEc Atlas. \label{workflow}](./workflow.png)

The next phase involves **automated filtering**, where a rule-based decision-tree logic (Figure \ref{flowchart}) systematically evaluates metadata fields—including **EDAM topics, tags, keywords, and free-text descriptions**—against a predefined set of microbiome-specific keywords. This step refines the dataset of **tools** and **workflows**, ensuring only microbiome-relevant resources advance to the final stage. Resources that pass this automated screening are then subjected to **community curation**, where domain experts review and validate them before they are published on the **RSEc Atlas**.

![**Filtering Logic**: A flowchart illustrating the decision-tree process for classifying resources. The system checks for EDAM topics, keywords in tags, titles, and descriptions. A match at any step classifies the resource as a MiCoReCa resource. \label{flowchart}](./decision_tree.png)

To ensure the pipeline remains **up-to-date and reproducible**, we implemented **weekly automated scraping and filtering** via **GitHub Actions**, inspired by the **Galaxy Codex** model. Automated notifications are sent to the community for curation, ensuring continuous expert input, while **comprehensive documentation** of the entire process enables adoption by other ELIXIR communities and initiatives. This pipeline not only streamlines the discovery of microbiome resources but also establishes a **scalable, community-driven framework** for maintaining and expanding the MiCoReCa catalog.

## Manual Curation of Extracted Tools and Workflows for Microbiome Relevance

Following the automated scraping and keyword-based filtering of resources from **bio.tools**, **WorkflowHub**, **Bioconda**, and **TeSS**, a rigorous **manual curation process** was conducted to ensure the inclusion of only the most relevant and high-quality resources for the microbiome research community. The primary objective of this curation was to refine the dataset by excluding resources that, despite passing the initial keyword filters, were not directly applicable to microbiome analysis. For instance, resources focused on **single-genome analysis**, **whole-genome sequencing**, **single-end ChIP-Seq data**, or other non-microbiome-specific applications were systematically removed.

To maintain a **focused and scientifically robust catalog**, resources were retained only if they aligned with one or more of the **key steps in microbiome data analysis**, including: (i) Quality Control (QC) and Filtering, (ii) Denoising or Clustering, (iii) Taxonomic Assignment and Phylogenetic Tree Construction, (iv) Functional Annotation, (v) Data Normalization, (vi) Diversity Analysis, (vii) Comparative Statistics, (viii) Association and Predictive Modeling. The **detailed curation protocol** is fully documented in the project's **[GitHub repository](https://github.com/research-software-ecosystem/micoreca/blob/main/doc/documentation_process.md)**, ensuring transparency and reproducibility for future contributions.

### Bioconda Tool Recipe Curation

The initial dataset of Bioconda recipes consisted of **10,136 recipes**. This set was reduced to **36 potential microbiome Bioconda recipes**. Unfortunately, **manual curation of the recipes** could not be initiated during the event due to **limited human resources**. This remains a priority for future work to ensure comprehensive coverage of microbiome tools.

### bio.tools Tools Curation

The **bio.tools** (via RSEc-Atlas) yielded **over 4,000 potential microbiome tools** after filtering. Due to the **sheer volume** and **time constraints**, a **community-driven curation process** was initiated, with contributions expected from the microbiome research community in the coming months. To date, **201** tools have been reviewed with **169** tools confirmed as directly relevant to microbiome research. Additionally, the **integration of missing tools** identified from other platforms (e.g., WorkflowHub) could not be completed within the BioHackathon timeline, as the process required more extensive validation and coordination.

### WorkflowHub Workflow Curation

The initial dataset from **WorkflowHub** consisted of **1,349 workflows**, which was reduced to **295 candidates** after automated filtering. Given the manageable size of this subset, a **manual review** was conducted, resulting in **208 workflows** being curated to date. Of these, **122 workflows** were confirmed as directly relevant to microbiome research and included in the final catalog.

This **multi-step curation process** ensures that MiCoReCa provides a **high-quality, relevant, and community-vetted** collection of microbiome bioinformatics resources, while also identifying areas for future improvement and expansion.

## Expanding EDAM Ontology to Support the Microbiome Community

An ongoing discussion is focused on **enhancing the EDAM ontology** to better reflect the evolving needs of the microbiome research community. As MiCoReCa progresses, it has become evident that **additional terms**—particularly those related to **taxonomic classification** and **contig binning**—are essential for comprehensive resource annotation. These terms are proposed to be integrated as **topics** and/or **operations**, respectively, ensuring that the ontology accurately captures the nuances of microbiome data analysis.

The **expansion of EDAM** is anticipated to be an iterative process, with further **topics and operations** likely to emerge as MiCoReCa continues to grow and incorporate feedback from its users. To advance this effort, **collaborative discussions** with key members of the **EDAM consortium** and with the ELIXIR Microbiome will be prioritized in the coming months. This initiative aims to establish a **standardized, community-driven vocabulary** that enhances resource discovery, interoperability, and reproducibility in microbiome research.

# Further Steps After the BioHackathon

The ELIXIR BioHackathon 2025 marked a significant milestone in the development of MiCoReCa, but the project’s evolution is far from complete. Moving forward, our focus will be on **finalizing technical implementations**, **deepening community engagement**, and **expanding the catalog’s reach** to other scientific domains. These efforts will ensure that MiCoReCa remains a **dynamic, high-quality, and sustainable resource** for microbiome research and beyond.

## Finalizing the Implementation

To ensure the **long-term sustainability and functionality** of MiCoReCa, we will prioritize several key technical enhancements. First, we will **integrate support for TeSS**, enabling the inclusion of **training materials** alongside tools and workflows, thereby providing users with a more comprehensive resource hub. Another critical step will be **finalizing the data integration process with the RSEc Atlas**, which involves establishing a **semi-automated pipeline using GitHub Actions** to seamlessly update and display curated resources. This process will be developed in close collaboration with the RSEc Atlas team to incorporate **community-specific features** that enhance usability.

We also plan to introduce an **AI-assisted evaluation step**, leveraging **Large Language Models (LLMs)** to improve metadata annotation and resource classification. This will not only enhance the accuracy of resource descriptions but also streamline the curation process. Additionally, we will **expand the catalog by incorporating resources from the Open and Sustainable AI (OSAI) Ecosystem**, ensuring that MiCoReCa includes cutting-edge AI-driven tools relevant to microbiome research. Finally, we will **refactor and strengthen the codebase** by implementing **unit tests** and improving the overall structure, ensuring robustness and ease of maintenance for future development.

## Collaboration with the ELIXIR Microbiome Community

Engagement with the **ELIXIR Microbiome Community** will remain central to MiCoReCa's growth. A key priority will be the **ongoing curation of resources and their metadata**, where community experts will review, validate, and enrich the information associated with each tool and workflow. This collaborative effort will ensure that the catalog remains **accurate, relevant, and aligned with the needs of researchers**.

Another important task will be **identifying and adding missing microbiome tools to bio.tools**, thereby improving the visibility and accessibility of these resources within the broader bioinformatics community. Additionally, we will continue our **collaboration with the EDAM consortium** to refine and finalize the **new EDAM terms** proposed during the BioHackathon. This will ensure that the ontology evolves to better represent the nuances of microbiome research, supporting more precise resource annotation and discovery.


## Expanding Beyond the ELIXIR Microbiome Community

The **modular and well-documented nature** of MiCoReCa's pipeline presents an opportunity to extend its impact beyond the microbiome community. We will work with **Single-Cell Omics and Biodiversity communities** to adapt and generalize the MiCoReCa framework, making it applicable to other biological research domains. This effort will not only broaden the utility of the catalog but also foster **cross-disciplinary collaboration** and resource sharing.

Furthermore, components of the MiCoReCa codebase will be **directly integrated into the RSEc Atlas**, enabling other ELIXIR communities to adopt and build upon this framework. By doing so, we aim to create a **versatile, cross-domain resource catalog** that supports a wide range of scientific research endeavors.

Through these efforts, MiCoReCa will continue to evolve as a **comprehensive, sustainable, and community-driven resource**, setting a standard for collaborative bioinformatics tool curation and serving as a model for other scientific communities.


# Conclusion and Perspectives

The **ELIXIR BioHackathon 2025** successfully established **MiCoReCa (Microbiome Community Resource Catalogue)**, a structured pipeline for curating microbiome-specific bioinformatics tools, workflows, and training materials from the ELIXIR ecosystem. A key achievement was the development of a **community-driven keyword**, combining **EDAM ontology terms**, **regular expressions**, and **domain-specific acronyms** to ensure both **precision** and **comprehensive coverage** of microbiome research needs. This approach demonstrated the value of **collaborative expertise** in creating a resource tailored to real-world scientific workflows.

However, the project also highlighted **critical challenges** in scaling manual curation. While automated filtering effectively narrowed down resources, **manual validation** was only feasible for smaller datasets, such as **WorkflowHub**, where **62 high-quality workflows** were curated from an initial pool of 1,349. Larger repositories like **bio.tools** (over 4,000 resources) and **Bioconda** remained **partially or entirely uncurated** due to **time and resource constraints**, emphasizing the need for a **sustained, community-wide effort** to achieve comprehensive coverage.

Moving forward, our focus will be on **deepening community engagement** to complete the curation of remaining resources and **strengthening the infrastructure** by integrating new **microbiome-specific EDAM terms** and exploring **AI-assisted curation tools** to streamline validation. The **MiCoReCa pipeline**, thoroughly documented and modular, serves as a **reusable framework** that can be adapted by other **ELIXIR communities**—such as those in **single-cell omics** or **biodiversity**—to enhance resource discoverability and interoperability.

Ultimately, MiCoReCa not only addresses a critical gap in microbiome research but also sets a **scalable precedent** for collaborative bioinformatics resource curation. Its success will depend on **ongoing community contributions** and **technological advancements**, ensuring it evolves into a **cornerstone resource** for microbiome science and beyond. We encourage researchers and bioinformatics experts to **engage, adopt, and expand** this initiative, fostering a more **connected and efficient** bioinformatics ecosystem.


## Acknowledgements

This work was developed as part of BioHackathon Europe 2025.
This work was supported by [ELIXIR](https://elixir-europe.org), the research infrastructure for life science data.
The French Institute of Bioinformatics (IFB) was founded by the Future Investment Program subsidized by the National Research Agency, number ANR-11-INBS-0013.
This work received state aid managed by the National Research Agency under France 2030 for structural research equipment / EQUIPEX+ with reference ANR-21-ESRE-0048.

## References