from email import header
from nipype.interfaces import (
    utility as niu,
    freesurfer as fs,
    fsl,
    image,
)

from nipype import Node, Workflow, SelectFiles, MapNode
from nipype.interfaces.utility import Function

import nipype.interfaces.io as nio
import os
from nipype.interfaces.ants.base import Info as ANTsInfo
from nipype.interfaces.ants import N4BiasFieldCorrection
from nipype.interfaces.image import Reorient

## Argument Parser
import argparse
parser = argparse.ArgumentParser()

#-db DATABSE -u USERNAME -p PASSWORD -size 20
parser.add_argument("-s", "--subject", help="Subject ID")
parser.add_argument("-d", "--source_directory", help="Source Directory")
parser.add_argument("-cs","--clinical_session")
parser.add_argument("-rs","--reference_session")

args = parser.parse_args()


print(args.subject)


#subjects = ['sub-RID0031','sub-RID0051','sub-RID0089','sub-RID0102','sub-RID0117','sub-RID0139','sub-RID0143','sub-RID0194','sub-RID0278','sub-RID0309','sub-RID0320','sub-RID0365','sub-RID0420','sub-RID0440','sub-RID0454','sub-RID0476','sub-RID0490','sub-RID0508','sub-RID0520','sub-RID0522','sub-RID0536','sub-RID0566','sub-RID0572','sub-RID0595','sub-RID0646','sub-RID0648','sub-RID0679']

subject = args.subject


#subjects = ['sub-RID0139']

source_dir = args.source_directory

out_file = os.path.join(source_dir,subject,'derivatives','ieeg_recon', 'clinical_module')

# Define the SelectFiles
templates= {'postimplant_ct': '{subject}/{session}/ct/{subject}_{session}_acq-3D_space-T01ct_ct.nii.gz',
'voxtool_coords': '{subject}/{session}/ieeg/{subject}_{session}_space-T01ct_desc-vox_electrodes.txt',
'preimplant_mri': '{subject}/{session_reference}/anat/{subject}_{session_reference}_acq-3D_space-T00mri_T1w.nii.gz'}

#templates = {'pet': '{subject}/{session}/pet/{subject}_{session}_pet.nii.gz'}
sf = Node(SelectFiles(templates),
            name='selectfiles')
sf.inputs.base_directory = source_dir
sf.inputs.subject = subject
sf.inputs.session = args.clinical_session
sf.inputs.session_reference = args.reference_session

session = args.reference_session # session of the reference MRI
#session = sf.inputs.session

session_clinical = args.clinical_session # session of the clinical scan

# Define data sink
datasink = Node(nio.DataSink(), name='sinker')
datasink.inputs.base_directory = out_file




# Define a custom nipype function that thresholds the CT image
def threshold_ct(in_ct):
    import nibabel as nib
    import os


    def append_fname(fname, suffix='thresholded',delim='.nii.gz'):
        fname = fname.split('/')[-1]
        return fname.split(delim)[0] + '_' + suffix + delim 


    message = "thresholding ct"
    print(message)
    ct = nib.load(in_ct)
    ct_affine = ct.affine
    ct_data = ct.get_fdata()

    ct_thresh = ct_data.copy()
    ct_thresh[ct_thresh<0] = 0


    ct_thresh_nifti = nib.Nifti1Image(ct_thresh, ct_affine)

    nib.save(ct_thresh_nifti,append_fname(in_ct))

    return os.path.abspath(append_fname(in_ct))



# Generate a segmentation of the VOX coordinates
def get_seg_vox_coords(in_ct ,coords_path):

    import nibabel as nib
    import numpy as np
    import os

    message = "Generating CT Coordinate Spheres"
    print(message)
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

    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords[:,1:4].astype(int)
        return coords


    coords = get_original_vox_coords(coords_path)

    ct = nib.load(in_ct)
    ct_affine = ct.affine
    ct_data = ct.get_fdata()
    ct_shape = ct.shape

    # Create empty array to store the coordinates
    spheres = np.zeros(ct_shape)

    for i in range(len(coords)):
        try:
            spheres = generate_sphere(spheres, coords[i,0], coords[i,1], coords[i,2], 2, i+1)
        except IndexError:
            print('Index Error at coordinate: ',i+1)

    spheres_nifti = nib.Nifti1Image(spheres, ct_affine)

    def append_fname(fname, suffix='thresholded',delim='.nii.gz'):
        fname = fname.split('/')[-1]
        return fname.split(delim)[0] + '_' + suffix + delim 

    fname = append_fname(in_ct, suffix='electrode_spheres')

    nib.save(spheres_nifti,fname)

    return os.path.abspath(fname)

def get_seg_vox_coords_mri(in_mri ,coords_path):

    import nibabel as nib
    import numpy as np
    import os

    message = "Generating MRI Coordinate Spheres"
    print(message)

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

    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords.astype(float).astype(int)
        return coords

    coords = get_original_vox_coords(coords_path)

    ct = nib.load(in_mri)
    ct_affine = ct.affine
    ct_shape = ct.shape

    # Create empty array to store the coordinates
    spheres = np.zeros(ct_shape)
    print(ct_shape)
    for i in range(len(coords)):
        print(i)
        try:
            spheres = generate_sphere(spheres, coords[i,0], coords[i,1], coords[i,2], 2, i+1)
        except IndexError:
            print('Index Error at coordinate: ',i+1)
    
    spheres_nifti = nib.Nifti1Image(spheres, ct_affine)

    def append_fname(fname, suffix='thresholded',delim='.nii.gz'):
        fname = fname.split('/')[-1]
        return fname.split(delim)[0] + '_' + suffix + delim 

    fname = append_fname(in_mri, suffix='electrode_spheres')

    nib.save(spheres_nifti,fname)

    return os.path.abspath(fname)


# Transform Coordinates in Input Array by Applying Transformation Matrix (or its inverse)
def transform_coordinates(in_mat ,coords_path, out_fname, inverse=True):

    import nibabel as nib
    import numpy as np
    import os

    message = "Transforming Coordinates"
    print(message)
    
    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords[:,1:4].astype(int)
        return coords
    
    def get_first_and_last_cols_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        return coords[:,0], coords[:,4], coords[:,5], coords[:,6]

    # Affine manipulation
    # define the functions to apply the affine transform
    def split_affine(affine):
        return affine[:3,:3], affine[:3,3]

    def apply_affine(xyz, affine):
        M, abc = split_affine(affine)
        return (np.matmul(M,xyz) + abc).astype(int)


    coords = get_original_vox_coords(coords_path)

    transform_matrix = np.loadtxt(in_mat)
    print('Matrix loaded')
    # Invert the transform matrix if inverse bool is true
    if inverse==True:

        transform_matrix = np.linalg.pinv(transform_matrix)
    

    # Create empty array to store the coordinates
    coords_transformed = np.zeros([coords.shape[0],coords.shape[1]+4], dtype=object)

    for i in range(len(coords)):
        coords_transformed[i,1:4] = apply_affine(coords[i,:], transform_matrix).astype(int)

    coords_transformed = coords_transformed

    a,b,c,d = get_first_and_last_cols_coords(coords_path)
    coords_transformed[:,0] = a
    coords_transformed[:,4] = b
    coords_transformed[:,5] = c
    coords_transformed[:,6] = d

    np.savetxt(out_fname,coords_transformed, fmt='%s')

    return os.path.abspath(out_fname)

def transform_coordinates_to_ras(in_mat ,coords_path):

        import nibabel as nib
        import numpy as np
        import os

        message = "Transforming Coordinates"
        print(message)

        # Affine manipulation
        # define the functions to apply the affine transform
        def split_affine(affine):
            return affine[:3,:3], affine[:3,3]

        def apply_affine(xyz, affine):
            M, abc = split_affine(affine)
            return (np.matmul(M,xyz) + abc).astype(int)


        coords = np.loadtxt(coords_path)

        transform_matrix = np.loadtxt(in_mat)
        print('Matrix loaded')
        # Invert the transform matrix if inverse bool is true

        

        # Create empty array to store the coordinates
        coords_transformed = np.zeros(coords.shape, dtype=object)

        for i in range(len(coords)):
            coords_transformed[i,:] = apply_affine(coords[i,:], transform_matrix).astype(int)

        coords_transformed = coords_transformed

        np.savetxt('coords_in_ras.txt',coords_transformed, fmt='%s')

        return os.path.abspath('coords_in_ras.txt')


def get_only_coords(coords_path):
    import nibabel as nib
    import numpy as np
    import os

    
    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords[:,1:4].astype(int)
        return coords
    


    coords = get_original_vox_coords(coords_path)

    np.savetxt('coordinates_only.txt', coords)

    return os.path.abspath('coordinates_only.txt')

def get_only_names(coords_path):
    import nibabel as nib
    import numpy as np
    import os

    
    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords[:,0]
        return coords
    


    coords = get_original_vox_coords(coords_path)

    np.savetxt('electrode_names_only.txt', coords, fmt='%s')

    return os.path.abspath('electrode_names_only.txt')

# Zero out the scaling row in the transform matrix
def zero_scaling(xfm_file):
    import numpy as np
    mat = np.loadtxt(xfm_file)
    mat[:,-1] = [0,0,0,1] 
    np.savetxt('zeroed_xfm.mat', mat)

    return os.path.abspath('zeroed_xfm.mat')

threshold_ct = MapNode(name='threshold_ct',
                interface=Function(input_names=['in_ct'],
                                    output_names=['out_file'],
                                    function=threshold_ct), iterfield='in_ct')



plot_ct_coords = MapNode(name='plot_ct_coords',
                interface=Function(input_names=['in_ct','coords_path'],
                                    output_names=['out_file'],
                                    function=get_seg_vox_coords), iterfield='in_ct')

transform_coords_to_ras = MapNode(name='transform_coords_to_ras',
                interface=Function(input_names=['in_mat','coords_path'],
                                    output_names=['out_file'],
                                    function=transform_coordinates_to_ras), iterfield=['in_mat','coords_path'])

get_only_coords = MapNode(name='get_only_coords', interface=Function(input_names=['coords_path'],
                                    output_names=['out_file'],
                                    function=get_only_coords), iterfield='coords_path')

get_only_names = MapNode(name='get_only_names', interface=Function(input_names=['coords_path'],
                                    output_names=['out_file'],
                                    function=get_only_names), iterfield='coords_path')

transform_coords_to_mri = MapNode(fsl.utils.WarpPoints(), name='transform_coords_to_mri', iterfield=['in_coords','xfm_file', 'src_file','dest_file'])

transform_coords_to_mri_mm = MapNode(fsl.utils.WarpPointsToStd(), name='transform_coords_to_mri_mm', iterfield=['in_coords','xfm_file', 'img_file', 'std_file'])

transform_ct_to_mri = MapNode(fsl.ApplyXFM(), name='transform_ct_to_mri', iterfield=['in_file','in_matrix_file','reference'])

transform_ct_to_ras = MapNode(fsl.utils.WarpPoints(), name='transform_ct_to_ras', iterfield=['in_coords','xfm_file', 'src_file','dest_file'])
#transform_mri_to_ras = MapNode(fsl.ApplyXFM(), name='transform_ct_to_ras', iterfield=['in_file','in_matrix_file','reference'])

plot_mri_coords = MapNode(name='plot_mri_coords',
                interface=Function(input_names=['in_mri','coords_path'],
                                    output_names=['out_file'],
                                    function=get_seg_vox_coords_mri), iterfield=['in_mri','coords_path'])


get_ct_to_mri_xfm = MapNode(fsl.ConvertXFM(),name='get_ct_to_mri_xfm', iterfield='in_file')
get_ct_to_mri_xfm.inputs.invert_xfm = True
#% Module 2

# Registration of post-implant CT to preimplant MRI
spatial_norm_rigid = MapNode(fsl.FLIRT(bins=640, cost_func='mutualinfo', dof=6), name='spatial_norm_rigid', iterfield=['in_file','reference'])
spatial_norm_rigid.base_dir = out_file
spatial_norm_rigid.inputs.searchr_x = [-60,60]
spatial_norm_rigid.inputs.searchr_y = [-60,60]
spatial_norm_rigid.inputs.searchr_z = [-60,60]

# Convert input images to RAS orientation
reorient_mri = MapNode(Reorient(orientation='RAS'), name='reorient_mri', iterfield='in_file')
reorient_ct = MapNode(Reorient(orientation='RAS'), name='reorient_ct', iterfield='in_file')



#%%
module1 = Workflow(name="module1", base_dir=out_file)

module1.connect([

        # Convert input images to RAS orientation
        (sf, reorient_ct, [('postimplant_ct','in_file')]),
        (sf, reorient_mri, [('preimplant_mri','in_file')]),
        (reorient_mri, datasink, [('out_file','MRI_RAS')]),
        (reorient_ct, datasink, [('out_file','CT_RAS')]),

        # Plot the coordinates in the CT space as spheres
        (reorient_ct, plot_ct_coords, [('out_file', 'in_ct')]),
        (sf, plot_ct_coords, [('voxtool_coords', 'coords_path')]),
        (plot_ct_coords, datasink, [('out_file', 'electrode_spheres_ct')]),

        # Threshold the CT for better registration and visualization
        (reorient_ct, threshold_ct, [('out_file', 'in_ct')]),
        (threshold_ct, datasink, [('out_file', 'ct_thresholded')]),

        # Perform MRI to CT rigid registration
        (reorient_mri, spatial_norm_rigid, [('out_file', 'in_file')]),
        (threshold_ct, spatial_norm_rigid, [('out_file', 'reference')]),
        (spatial_norm_rigid, datasink, [('out_file', 't00_registered_to_ct'),
                                    ('out_matrix_file', 't00_to_ct_transform')]),

        # Get the inverse of the MRI to CT registration matrix - This give CT to MRI registration
        (spatial_norm_rigid, get_ct_to_mri_xfm, [('out_matrix_file','in_file')]),
        (get_ct_to_mri_xfm, datasink, [('out_file','ct_to_t00_transform')]),
        
        # Apply the CT to MRI registration to the CT
        (get_ct_to_mri_xfm, transform_ct_to_mri, [('out_file','in_matrix_file')]),
        (threshold_ct, transform_ct_to_mri, [('out_file','in_file')]),
        (reorient_mri, transform_ct_to_mri, [('out_file','reference')]),
        (transform_ct_to_mri, datasink, [('out_file','ct_in_t00_space')]),


        ### Coordinate Transformation 
        # Get only the coordinates from the voxtool output (remove electrode names and such)
        (sf, get_only_coords, [('voxtool_coords', 'coords_path')]),

        # Save the names on a separate file
        (sf, get_only_names, [('voxtool_coords', 'coords_path')]),
        (get_only_names, datasink, [('out_file','electrode_names')]),

        # Transform CT coordinates to RAS
        (get_only_coords, transform_coords_to_ras, [('out_file','coords_path')]),
        (reorient_ct, transform_coords_to_ras, [('transform','in_mat')]),

        # Transform CT coords to MRI coords in Voxel Space
        (get_ct_to_mri_xfm, transform_coords_to_mri, [('out_file','xfm_file')]),
        (transform_coords_to_ras, transform_coords_to_mri, [('out_file','in_coords')]),

        (threshold_ct, transform_coords_to_mri, [('out_file','src_file')]),
        (reorient_mri, transform_coords_to_mri, [('out_file','dest_file')]),
        (transform_coords_to_mri, datasink, [('out_file', 'coordinates_in_mri')]),

        # Transform CT coords to MRI coords in mm Space
        (get_ct_to_mri_xfm, transform_coords_to_mri_mm, [('out_file','xfm_file')]),
        (transform_coords_to_ras, transform_coords_to_mri_mm, [('out_file','in_coords')]),

        (reorient_ct, transform_coords_to_mri_mm, [('out_file','img_file')]),
        (reorient_mri, transform_coords_to_mri_mm, [('out_file','std_file')]),
        (transform_coords_to_mri_mm, datasink, [('out_file', 'coordinates_in_mri_mm')]),

        # Plot final coordinates in MRI space as spheres
        (transform_coords_to_mri, plot_mri_coords, [('out_file', 'coords_path')]),
        (reorient_mri, plot_mri_coords, [('out_file', 'in_mri')]),
        (plot_mri_coords, datasink, [('out_file', 'electrode_spheres_mri')]),

        # Save the outputs
        
])
module1.run()

# Save the itksnap labels
def create_itk_snap_label_file():
    session = sf.inputs.session
    coords_path = source_dir + '/' +subject+'/'+session+'/ieeg/'+subject+'_'+session+'_space-T01ct_desc-vox_electrodes.txt'
    
    def append_fname(fname, suffix='thresholded',delim='.nii.gz'):
        fname = fname.split('/')[-1]
        return fname.split(delim)[0] + '_' + suffix + delim
    


    fname = out_file+'/'+append_fname(coords_path, suffix='itk_snap_labels', delim='.txt')
    
    import sys
    header = f'''
################################################
# ITK-SnAP Label Description File
# File format: 
# IDX   -R-  -G-  -B-  -A--  VIS MSH  LABEL
# Fields: 
#    IDX:   Zero-based index 
#    -R-:   Red color component (0..255)
#    -G-:   Green color component (0..255)
#    -B-:   Blue color component (0..255)
#    -A-:   Label transparency (0.00 .. 1.00)
#    VIS:   Label visibility (0 or 1)
#    IDX:   Label mesh visibility (0 or 1)
#  LABEL:   Label description 
################################################
0	0	0	0	0	0	0	"Clear Label"
    '''

    # 3. Write the html string as an HTML file
    with open(fname, 'w') as f:
        f.write(header)
    
    # Get the names of the coordinates
    import numpy as np

    
    # Return an array with the vox coordinates
    def get_original_vox_coords(coords_path):
        coords = np.loadtxt(coords_path, dtype=object)
        coords = coords[:,0]
        return coords

    coords_name = get_original_vox_coords(coords_path)
    
    original_stdout = sys.stdout

    for i in range(len(coords_name)):
        line = []
        line.append(i+1)
        line.append(np.random.randint(0,255)) # R
        line.append(np.random.randint(0,255)) # G
        line.append(np.random.randint(0,255)) # B
        line.append(1)
        line.append(1)
        line.append(1)
        line.append('"'+coords_name[i]+'"')
        with open(fname, 'a') as f:
            sys.stdout = f # Change the standard output to the file we created.
            print(*line, sep='\t')
            sys.stdout = original_stdout # Reset the standard output to its original value

create_itk_snap_label_file()

# Clean the output folder 

# # Remove the module cached folder
os.chdir(out_file)

# Rename some files
os.rename('coordinates_in_mri/_transform_coords_to_mri0/coords_in_ras_warped.txt','coordinates_in_mri/_transform_coords_to_mri0/' + subject+'_'+session+'_space-T00mri_desc-vox_electrodes.txt')
os.rename('coordinates_in_mri_mm/_transform_coords_to_mri_mm0/coords_in_ras_warped.txt','coordinates_in_mri_mm/_transform_coords_to_mri_mm0/' + subject+'_'+session+'_space-T00mri_desc-mm_electrodes.txt')

# Remove the cached folder
command = 'rm -r module1'
os.system(command)

    # # Move everything to derivatives folder
command = 'mv */*/* .'
os.system(command)

command = 'find . -type f -name "*.DS_Store" -delete'
os.system(command)

command = 'find . -empty -type d -delete'
os.system(command)

# Rename some of the final files


os.rename(subject+'_'+session_clinical+'_acq-3D_space-T01ct_ct_ras_thresholded_flirt.nii.gz', subject+'_'+session_clinical+'_acq-3D_space-T00mri_ct_thresholded.nii.gz')

try:
    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_flirt.nii.gz', subject+'_'+session+'_acq-3D_space-T01ct_T1w.nii.gz')

    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_flirt.mat', subject+'_'+session+'_T00mri_to_T01ct.mat')

    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_flirt_inv.mat', subject+'_'+session+'_T01ct_to_T00mri.mat')

except FileNotFoundError:
    
    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_ras_flirt.nii.gz', subject+'_'+session+'_acq-3D_space-T01ct_T1w.nii.gz')

    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_ras_flirt.mat', subject+'_'+session+'_T00mri_to_T01ct.mat')

    os.rename(subject+'_'+session+'_acq-3D_space-T00mri_T1w_ras_flirt_inv.mat', subject+'_'+session+'_T01ct_to_T00mri.mat')


os.rename('electrode_names_only.txt', subject+'_electrode_names.txt')


# Generate an svg to visualize
# #%% Visualization
from niworkflows.viz.notebook import display
display(subject+'_'+session+'_acq-3D_space-T01ct_T1w.nii.gz',subject+'_'+session_clinical+'_acq-3D_space-T01ct_ct_ras_thresholded.nii.gz')

command = 'mv report.svg '+subject+'_'+session+'_T00mri_T01ct_registration.svg'
os.system(command)

#%% Plot the locations of the electrodes using plotly
import plotly.graph_objects as go
import numpy as np
import nibabel as nib

coords_mm = np.loadtxt(subject+'_'+session+'_space-T00mri_desc-vox_electrodes.txt')

ct_thresh = nib.load(subject+'_'+session_clinical+'_acq-3D_space-T00mri_ct_thresholded.nii.gz')

# x, y, z = coords_mm[:,0], coords_mm[:,1], coords_mm[:,2]

# fig = go.Figure(data=[go.Scatter3d(x=x, y=y, z=z,
#                                 mode='markers', marker=dict(size=5))])


fig = go.Figure()



x,y,z = np.where(ct_thresh.get_fdata()>np.percentile(ct_thresh.get_fdata(),99.99))

fig.add_trace(go.Scatter3d(x=x, y=y, z=z,
                                mode='markers', marker=dict(size=2),name='Thresholded CT'))

x, y, z = coords_mm[:,0], coords_mm[:,1], coords_mm[:,2]

fig.add_trace(go.Scatter3d(x=x, y=y, z=z,
                                    mode='markers', marker=dict(size=3),name='Electrode Coordinates'))

fig.update_layout(title_text=subject+' - Electrode Scatterplot (vox)', title_x=0.5)
fig.show()
fig.write_html(subject+'_'+session+'_space-T00mri_desc-mm_electrodes_plot.html')