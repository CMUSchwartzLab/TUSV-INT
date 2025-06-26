# Deconvolution and Phylogeny Inference of Diverse Variant Types Integrating Bulk DNA-seq with Single-cell RNA-seq

We develop TUSV-INT, a tool for clonal evolution studies integrating bulk DNA-seq and scRNA-seq with diverse variant types (SNV, CNA, and SV).  The work uses a general integer linear programming (ILP) framework for clonal lineage reconstruction.

## Contents
1. [Installation](#installation) 
2. [Running TUSV-INT](#running)
	- [Input](#input)
	- [Output](#output)
3. [Input Settings](#settings)
4. [Example](#example)

<a name="installation"></a>
## Installation
TUSV-INT is built with python 2.7. We provide the following commands to set up the environment - 

```
conda create -n tusvint python=2.7
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

<a name="running"></a>
## Running TUSV-INT

<a name="input"></a>
### Input 
The method requires two types of inputs. The first is a directory with the bulk DNAseq samples containing SNVs, CNAs and SVs. The second is the allele-specific CNA calls from scRNA-seq. The details of the inputs are given below - 

- **Bulk DNA-seq samples**: A directory containing the processed variant calls of the bulk DNAseq samples in `VCF` format. An example can be found in `simulation_data/input/samples/`. 
- **ScRNA-seq**: The allele-specific clonal copy numbers from scRNA-seq in `.tsv` format. For each scRNA clone, the file will have one row. The first `r` columns will contain the major copy numbers, the later `r` columns will contain the minor copy numbers. Here is a tab-separated version of the file where the first line is the header and rows correspond to scRNA clones -  

| chr_start_end_p |  ..   |  chr_start_end_p  | .. | chr_start_end_m     |  .. | chr_start_end_m |
| -------- | ------- | ------- | ------- | ------- | ------- | ------- |
| 1 | .. | 1 | .. | 2 | .. | 1 |
| 2 | .. | 1 | .. | 1 | .. | 1 |
| 1 | .. | 1 | .. | 1 | .. | 1 |

 
  An example of the inputs can be found in the `simulation_data/input/` folder. 

<a name="output"></a>
### Output 
- T.dot: Output tree with the `clone assignments` in the nodes and  `phylogenetic cost/number of SNV and SV mapped` in the branches.
- M.tsv: Bulk DNA-seq clone in the tree to ScRNA-seq clonal assignment matrix.
- C.tsv: The variant copy number profile matrix (Size: clones * variants)
- U.tsv: The clonal Mixture fraction matrix (Size: sample * clones)

<a name="settings"></a>
## Input Settings

Following inputs are mandatory:
- `-i` : input directory containing bulk DNA-seq VCF files
-  `-f` : input `.tsv` file containing scRNA-seq CNAs
- `-o` : output directory
- `-n` : number of leaves
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
- `-anc` : binary flag, infers missing ancestral clones when set
<a name="example"></a>
## Example

```
python -u tusv-int.py -i simulation_data/input/sample/ -f simulation_data/input/C_scRNA_CNVs.tsv -o simulation_data/output/ -n 2 -c 10 -t 3 -r 3 -m 1000 -b -C 120 -sv_ub 80
```
