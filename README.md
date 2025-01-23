# Deconvolution and Phylogeny Inference of Diverse Variant Types Integrating Bulk DNA-seq with Single-cell RNA-seq

We develop TUSV-INT, a platform for clonal evolution studies integrating bulk DNA-seq and scRNA-seq to produce clonal evolution models that are unprecendented in their comprehensive accounting for fine clonal structure, genomic coverage, and diverse variant types (SNV, CNA, and SV).  The work uses a general integer linear programming (ILP) framework of clonal lineage reconstruction


## Installation
The method is built with python 2. To run the program, a python 2.7 conda environment is required. We provide the following commands with the specific packages to install the dependencies - 

```conda create -n tusvint python=2.7
conda activate tusvint
conda config --add channels conda-forge
conda config --add channels bioconda
```

Then, you will need the following packages in the  `tusvint` environment. <br>
      - `numpy` <br>
      - `pandas` <br>
      - `ete2` <br>
      - `gurobipy` <br>
      - `graphviz` <br>
      - `biopython=1.76` <br>
      - `scipy` <br>
      - `PyVCF`
- We use the Gurobi optimzer for our method. To acquire Gurobi license, you can sign up as an academic user in the Gurobi website - [https://www.gurobi.com/downloads/end-user-license-agreement-academic/](https://www.gurobi.com/downloads/end-user-license-agreement-academic/). 
  
## Inputs and Outputs
### Input
The input folder should contain the processed variant called scDNAseq files in VCF format. An example can be found in the `simulation_data/input/` folder. 

### Outputs
- T.dot: Output tree with the `clone assignments` in the nodes and  `phylogenetic cost/number of SNV and SV mapped` in the branches.
- M.tsv: Bulk DNA-seq clone in the tree to ScRNA-seq clonal assignment matrix.
- C.tsv: The variant copy number profile matrix (Size: clones * variants)
- U.tsv: The clonal Mixture fraction matrix (Size: sample * clones)


## Instructions for running

```
python -u tusv-int.py -i simulation_data/input/sample/ -f simulation_data/input/C_scRNA_CNVs.tsv -o simulation_data/output/ -n 2 -c 10 -t 1 -r 1 -m 20 -b -C 20 -sv_ub 10
```
Following inputs are mandatory:
- `-i` : input folder
- `-o` : output folder
- `-n` : number of leaves.
- `-c` : maximum copy number allowed for any breakpoint or segment on any node
- `-t` : maximum number of coordinate-descent iterations
- `-r` : number of random initializations of the coordinate-descent algorithm
- `-col` : binary flag whether to collapse the redundant nodes
- `-sv_ub` : the number of subsampled SV breakpoints 
- `-const` : number of total subsampled breakpoints and SNVs
- `-m` : maximum time (seconds) in each coordinate descent iteration

Optional parameters:
- `-x` : cell consensus percentage within each clone (default = 34)
- `-b` : binary flag for the regularization parameters to be set automatically
- `-l` : lambda regularization parameter for weighting the phylogenetic cost
- `-p` : number of processors to use (uses all the available cores by default)
- `-s` : number of segments (in addition to those containing breakpoints) that are randomly kept (default keeps all the segments)
