# iEEG-Recon
iEEG electrode reconstruction pipeline

# Overview

iEEG-Recon is a pipeline used to reconstruct intracranial electrode coordinates from a post-implant CT scan, into a pre-implant MRI. iEEG-Recon is divided into 3 modules:

- Module 1 consists of an electrode labeling GUI called VoxTool, available here: https://github.com/penn-cnt/voxTool. VoxTool allows the user to label the electrode locations in the post-implant CT scan.
- Module 2 registers the CT scan to the pre-implant MRI and transforms the VoxTool generated coordinates from CT space to MRI space
- Module 3 maps each electrode to a specific ROI defined by a brain atlas registered to the pre-implant MRI

# Installation

## Docker

We recommend using the Docker container available here: https://hub.docker.com/repository/docker/lucasalf11/ieeg_recon

## Python 

For a standalone python installation, we recommend you have Anaconda (https://www.anaconda.com/products/distribution) with at least Python 3.7

With Anaconda and Python installed, clone the repository, and open a terminal window in the directory where the repository was cloned into. Type the following command:

```
conda env create -f ieeg_recon_config.yml
```

This will create a conda virtual environment called `ieeg_recon` that contains all of the dependencies. To activate the environment type:

```
conda activate ieeg_recon
```

### Installing FSL

When using the standalone Python version, FSL must also be installed (https://fsl.fmrib.ox.ac.uk/fsl/fslwiki/FslInstallation). Make sure the `$FSLDIR` variable is properly defined and FSL is sourced before running the `ieeg_recon` script

# Usage

For an overview of the pipeline as well as its usage see here: https://github.com/allucas/ieeg_recon/blob/main/figures/ieeg_recon.pdf


