# Curation processes

## Curation of the workflows

To have the most relevant workflows to the microbiome community, we manually curated the workflows extracted from WorkflowHub and programmatically filtered using the keywords defined. 
To do so, we excluded the workfows where the description evolved around terms like: 
- Single genome analysis  
- whole genome sequencing 
- single-end ChIP-Seq data
- reference genome annotation
- biomedical
- Human
- rare diseases 
- NGS SARS-Cov2 samples
- Calculation not related to the microbiome (LU matrix factorization on a sparse blocked matrix)
- Images and Image reconstruction 
- molecular network


The workflows that were retrieved and kept if corresponding to one or more of the following steps for microbiome analysis.

- **Quality Control (QC) and Filtering**: trimming, removing sequencing errors, adapter sequences, and too-short reads.

- Denoising or Clustering (Feature Table Generation): denoise reads into Amplicon Sequence Variants (ASVs) or Exact Sequence Variants (ESVs) for example.

- Taxonomic Assignment and Phylogenetic Tree Construction: ASV/OTU sequences compared against curated reference databases using a classifier, phylogenetic tree constructed from aligning of the sequences and inferring evolutionary distance. 

- Functional Annotation (for Metagenomics/Shotgun Sequencing): it is difficult to dedifferentiate with whole genome annotation tool

- Data Normalization: address the compositional nature of microbiome data (the counts are relative, not absolute) and account for differences in sequencing depth (library size).

- Diversity Analysis (Community Characterization): quantify the complexity and dissimilarity of microbial communities, through their Alpha and Beta Diversity

- **Comparative Statistics**: identifying specific microbial features (ASVs/OTUs or taxa) that are significantly different in abundance between experimental groups with methods like differential abundance testing or multivariate statistical tests (PERMANOVA or ADONIS)

- Association and Predictive Modeling: link the microbial profile to host metadata (e.g., phenotype) and build predictive models with correlation/regression test or algorithms like Random Forests or Linear Discriminant Analysis Effect Size (LEfSe) to identify microbial signatures or features that can accurately predict a phenotype.

