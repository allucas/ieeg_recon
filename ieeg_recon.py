#!/usr/bin/env python


## Argument Parser
import argparse
import os
import subprocess

# Parse all the required arguments
parser = argparse.ArgumentParser()

# Global arguments
parser.add_argument("-s", "--subject", help="Subject ID" )
parser.add_argument("-rs","--reference_session")
parser.add_argument("-m","--module", help='Module to Run, -1 to run modules 2 and 3')

# Module 2 arguments
parser.add_argument("-d", "--source_directory", help="Source Directory")
parser.add_argument("-cs","--clinical_session")


# Module 3 arguments
parser.add_argument("-a", "--atlas_path")
parser.add_argument("-an", "--atlas_name")
parser.add_argument("-ri", "--roi_indices", help="ROI Indices")
parser.add_argument("-rl", "--roi_labels", help="ROI Labels")
parser.add_argument("-r","--radius", help="Radius for Electrode atlast Assignment")
parser.add_argument("-ird", "--ieeg_recon_dir", help="Source iEEG Recon Directory")
parser.add_argument("-lut", "--atlas_lookup_table", help="Atlas Lookup Table")



args = parser.parse_args()

print('Subject: ', args.subject)
print('Clinical Session: ', args.clinical_session)
print('Reference Session: ', args.reference_session)


# Organize the atlas lookup inputs
if args.atlas_lookup_table == None:
    atlas_lookup_params = " -ri "+args.roi_indices+" -rl "+args.roi_label
else:
    atlas_lookup_params = " -lut "+args.atlas_lookup_table

# Run the main pipeline
if args.module == str(-1):
    print('Running Modules 2 and 3 ... \n \n \n \n ')

    clinical_module_dir=os.path.join(args.source_directory, args.subject, 'derivatives','ieeg_recon')
    subprocess.call("python pipeline/module2.py -s "+args.subject+" -rs "+args.reference_session+" -d "+args.source_directory+" -cs "+args.clinical_session, shell=True)
    subprocess.call("python pipeline/module3.py -s "+args.subject+" -rs "+args.reference_session+" -ird "+clinical_module_dir+" -a "+args.atlas_path+" -an "+args.atlas_name+ atlas_lookup_params +" -r "+args.radius , shell=True)


if args.module == str(3):
    print('Running Module 3 ...')
    if args.ieeg_recon_dir == None:
        clinical_module_dir=os.path.join(args.source_directory, args.subject, 'derivatives','ieeg_recon')
    else:
        clinical_module_dir=args.ieeg_recon_dir

    subprocess.call("python pipeline/module3.py -s "+args.subject+" -rs "+args.reference_session+" -ird "+clinical_module_dir+" -a "+args.atlas_path+" -an "+args.atlas_name+ atlas_lookup_params +" -r "+args.radius , shell=True)

if args.module == str(2):
    print('Running Module 2 ...')
    subprocess.call("python pipeline/module2.py -s "+args.subject+" -rs "+args.reference_session+" -d "+args.source_directory+" -cs "+args.clinical_session, shell=True)