import nibabel as nib
import numpy as np

from email import header
from nipype.interfaces import (
    utility as niu,
    freesurfer as fs,
    fsl
)

from nipype import Node, Workflow, SelectFiles, MapNode
from nipype.interfaces.utility import Function

import os

# 
# subject = 'sub-RID0031'
# radius = 1
# atlas = nib.load('/Users/allucas/Documents/research/CNT/P30_ieeg_fmri/source_data/penn_freesurfer/sub-RID0031/mri/aparc+aseg.vep.nii.gz')
# roi_indices = np.loadtxt('/Users/allucas/Documents/research/CNT/P33_ieeg_recon/source_data/DKTatlas+aseg+VEP_indices.txt', dtype=int)
# roi_labels = np.loadtxt('/Users/allucas/Documents/research/CNT/P33_ieeg_recon/source_data/DKTatlas+aseg+VEP_labels.txt', dtype=object)
# atlas_name = 'DKT+aseg+VEP'
# clinical_module_dir = '/Users/allucas/Documents/research/CNT/P33_ieeg_recon/source_data/sample_bids/sub-RID0031/derivatives/ieeg_recon/clinical_module/'

## Argument Parser
import argparse
parser = argparse.ArgumentParser()

#-db DATABSE -u USERNAME -p PASSWORD -size 20
parser.add_argument("-s", "--subject", help="Subject ID")
parser.add_argument("-rs","--reference_session")
parser.add_argument("-ird", "--ieeg_recon_dir", help="Source iEEG Recon Directory")
parser.add_argument("-a", "--atlas_path", help="Atlas Path")
parser.add_argument("-an", "--atlas_name", help="Atlas Name")
parser.add_argument("-ri", "--roi_indices", help="ROI Indices")
parser.add_argument("-rl", "--roi_labels", help="ROI Labels")
parser.add_argument("-r","--radius",help="Radius for Electrode atlast Assignment")


args = parser.parse_args()

subject = args.subject
radius = int(args.radius)
atlas = nib.load(args.atlas_path)
roi_indices = np.loadtxt(args.roi_indices, dtype=int)
roi_labels = np.loadtxt(args.roi_labels, dtype=object)
atlas_name = args.atlas_name
clinical_module_dir = os.path.join(args.ieeg_recon_dir,'module2')
reference_session = args.reference_session

try:
    img = nib.load(os.path.join(clinical_module_dir,'MRI_RAS',subject+'_'+reference_session+'_acq-3D_space-T00mri_T1w.nii.gz'))
except FileNotFoundError:
    img = nib.load(os.path.join(clinical_module_dir,subject+'_'+reference_session+'_acq-3D_space-T00mri_T1w_ras.nii.gz'))

pixdims = atlas.header['pixdim'][1:4]

max_dim = np.max(pixdims)
min_radius = np.round(1/max_dim) # the minimum possible radius given the voxel size

coords = np.loadtxt(os.path.join(clinical_module_dir,subject+'_'+reference_session+'_space-T00mri_desc-vox_electrodes.txt'))
electrode_names = np.loadtxt(os.path.join(clinical_module_dir,subject+'_electrode_names.txt'), dtype=object)


def split_affine(affine):
    return affine[:3,:3], affine[:3,3]

def apply_affine(xyz, affine):
    M, abc = split_affine(affine)
    return (np.matmul(M,xyz) + abc).astype(int)

def generate_sphere(A, x0,y0,z0, radius, value):
    ''' 
        A: array where the sphere will be drawn
        radius : radius of circle inside A which will be filled with ones.
        x0,y0,z0: coordinates for the center of the sphere within A
        value: value to fill the sphere with
    '''

    ''' AA : copy of A (you don't want the original copy of A to be overwritten.) '''
    AA = A



    for x in range(x0-radius, x0+radius+1):
        for y in range(y0-radius, y0+radius+1):
            for z in range(z0-radius, z0+radius+1):
                ''' deb: measures how far a coordinate in A is far from the center. 
                        deb>=0: inside the sphere.
                        deb<0: outside the sphere.'''   
                deb = radius - ((x0-x)**2 + (y0-y)**2 + (z0-z)**2)**0.5 
                if (deb)>=0: AA[x,y,z] = value
    return AA
def most_common(lst):
    return max(set(lst), key=lst.count)

def match_label(index,index_list, label_list):
    return label_list[np.where(index_list==index)[0][0]]

atlas_data = atlas.get_fdata()

electrode_assignment_index = []
electrode_assignment_label = []

for i in range(len(coords)):
    coords_atlas = apply_affine(coords[i,:],np.matmul(np.linalg.pinv(atlas.affine),img.affine))
    
    mask = np.zeros(atlas.shape)

    mask = generate_sphere(mask, coords_atlas[0], coords_atlas[1], coords_atlas[2], int(max([radius/max_dim, min_radius])), 1)

    index = most_common(list(atlas_data[mask==1]))
    label = match_label(index, roi_indices, roi_labels)

    electrode_assignment_index.append(index)
    electrode_assignment_label.append(label)

atlas_module_dir = os.path.join(clinical_module_dir,'..','module3')

if os.path.exists(atlas_module_dir) == False:
    os.mkdir(atlas_module_dir)

atlas_coords = np.zeros((len(coords), 6), dtype=object)

atlas_coords[:,0] = electrode_names
atlas_coords[:,1:4] = coords
atlas_coords[:,4] = electrode_assignment_index
atlas_coords[:,5] = electrode_assignment_label

np.savetxt(os.path.join(atlas_module_dir, subject+'_space-T00mri_atlas-'+atlas_name+'_radius-'+str(radius)+'_desc-vox_coordinates.txt') ,atlas_coords, fmt='%s')

import pandas as pd
df_coords = pd.DataFrame()
df_coords['name'] = electrode_names
df_coords['x'] = coords[:,0]
df_coords['y'] = coords[:,1]
df_coords['z'] = coords[:,2]
df_coords['index'] = electrode_assignment_index
df_coords['label'] = electrode_assignment_label
df_coords.to_csv(os.path.join(atlas_module_dir, subject+'_space-T00mri_atlas-'+atlas_name+'_radius-'+str(radius)+'_desc-vox_coordinates.csv'))

