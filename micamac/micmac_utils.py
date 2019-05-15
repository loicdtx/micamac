import subprocess
import glob
import multiprocessing as mp
import re
import os
import shutil

from shapely.geometry import Point


def run_tawny(color):
    """tawny wrapper to be called in a multiprocessing map
    """
    subprocess.call(['mm3d', 'Tawny',
                     'Ortho-%s' % color,
                     'DEq=0', 'DegRap=1'])


def img_to_Point(img_path):
    """Given a file with exif geotag on disk, build a shapely Point

    Return:
        Tuple: A tuple (``shapely.geometry.Point``, path)
    """
    with exiftool.ExifTool() as et:
        meta = et.get_metadata(img_path)
    geom = Point(meta['EXIF:GPSLongitude'], meta['EXIF:GPSLatitude'])
    return (geom, img_path)


def dir_to_points():
    """Wrapper to run ``img_to_point`` on all panchromatic images of the current working directory

    Uses all threads available, return a list of tuples (see help of img_to_Point)
    """
    img_list = glob.glob('pan*tif')
    all_cpu = mp.cpu_count()
    pool = mp.Pool(all_cpu)
    point_list = pool.map(img_to_Point, img_list)
    return point_list


def update_poubelle():
    """Mirror content of Poubelle for all bands

    Move R,G,B,NIR,RE images corresponding to panchromatic images already
    present in Poubelle
    """
    bad_files = glob.glob('Poubelle/pan*tif')
    bad_files = [os.path.basename(x) for x in bad_files]
    file_pattern = re.compile(r'pan_(\d{5}\.tif)$')
    [shutil.move(file_pattern.sub(r'blue_\1', x), 'Poubelle/') for x in bad_files]
    [shutil.move(file_pattern.sub(r'green_\1', x) 'Poubelle/') for x in bad_files]
    [shutil.move(file_pattern.sub(r'red_\1', x), 'Poubelle/') for x in bad_files]
    [shutil.move(file_pattern.sub(r'nir_\1', x), 'Poubelle/') for x in bad_files]
    [shutil.move(file_pattern.sub(r'edge_\1', x), 'Poubelle/') for x in bad_files]


def update_ori(path='Ori-Ground_UTM'):
    """Create ori files for all bands by renaming existing panchromatic ori files

    Args:
        path (str): Orientation directory
    """
    glob_pattern = os.path.join(path, 'Orientation-pan*xml')
    ori_pan_list = glob.glob(glob_pattern)
    ori_file_pattern = re.compile(r'(Orientation-)pan(_\d{5}\.tif\.xml)')
    [shutil.copyfile(x, ori_file_pattern.sub(r'\1blue\2', x)) for x in ori_pan_list]
    [shutil.copyfile(x, ori_file_pattern.sub(r'\1green\2', x)) for x in ori_pan_list]
    [shutil.copyfile(x, ori_file_pattern.sub(r'\1red\2', x)) for x in ori_pan_list]
    [shutil.copyfile(x, ori_file_pattern.sub(r'\1nir\2', x)) for x in ori_pan_list]
    [shutil.copyfile(x, ori_file_pattern.sub(r'\1edge\2', x)) for x in ori_pan_list]


def clean_intermediary(exclude=['OUTPUT']):
    """Delete all intermediary output of the micmac execution
    """
    if isinstance(exclude, string):
        exclude = [exclude]
    dir_list = glob.glob('*/')
    [dir_list.remove(d) for d in exclude]
    [shutil.rmtree(x) for x in dir_list]


def clean_images():
    """Delete all images of the working directory
    """
    tif_list = glob.glob('*tif')
    [os.remove(x) for x in tif_list]


def create_proj_file(zone):
    proj_xml = """
    <SystemeCoord>
             <BSC>
                <TypeCoord>  eTC_Proj4 </TypeCoord>
                <AuxR>       1        </AuxR>
                <AuxR>       1        </AuxR>
                <AuxR>       1        </AuxR>
                <AuxStr>  +proj=utm +zone=%d +ellps=WGS84 +datum=WGS84 +units=m +no_defs   </AuxStr>

             </BSC>
    </SystemeCoord>
    """ % zone

    with open('SysUTM.xml', 'w') as dst:
        dst.write(proj_xml)
