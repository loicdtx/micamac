import subprocess
import glob
import multiprocessing as mp
import re
import os
import shutil
import xml.etree.ElementTree as ET

from shapely.geometry import Point
import exiftool
import rasterio
from rasterio.crs import CRS
from rasterio.warp import transform_geom
from rasterio.features import rasterize
from affine import Affine
from shapely.geometry import mapping, shape, MultiPoint


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


def make_tarama_mask(point_list, utm_zone, buff=0, TA_dir='TA'):
    """Generate a mask using the gps coordinates of the captures

    This command follows the execution of tarama, after which a mask is normally
    created interactively by the user

    Args:
        point_list (list): List of (shapely.Point, str) tuples. See ``dir_to_points``
        utm_zone (int): Utm zone of the project
        buffer (float): optional buffer to extend or reduce masked area around
           the convex hull of the point list
        TA_dir (str): tarama dir relative to current directory. Defaults to ``'TA'``
    """
    # Build study area polygon
    src_crs = CRS.from_epsg(4326)
    dst_crs = CRS(proj='utm', zone=utm_zone, ellps='WGS84', units='m')
    feature_list = [mapping(x[0]) for x in point_list]
    feature_list_proj = [transform_geom(src_crs, dst_crs, x) for x in feature_list]
    point_list_proj = [shape(x) for x in feature_list_proj]
    study_area = MultiPoint(point_list_proj).convex_hull.buffer(buff)

    # Retrieve Affine transform and shape from TA dir
    root = ET.parse(os.path.join(TA_dir, 'TA_LeChantier.xml')).getroot()
    x_ori, y_ori = [float(x) for x in root.find('OriginePlani').text.split(' ')]
    x_res, y_res = [float(x) for x in root.find('ResolutionPlani').text.split(' ')]
    arr_shape = tuple(reversed([int(x) for x in root.find('NombrePixels').text.split(' ')]))
    aff = Affine(x_res, 0, x_ori, 0, y_res, y_ori)

    # Rasterize study area to template raster
    arr = rasterize(shapes=[(study_area, 1)], out_shape=arr_shape, fill=0,
                    transform=aff, default_value=1, dtype=rasterio.uint8)

    # Write mask to raster
    meta = {'driver': 'GTiff',
            'dtype': 'uint8',
            'width': arr_shape[1],
            'height': arr_shape[0],
            'count': 1,
            'crs': dst_crs,
            'transform': aff}
    filename = os.path.join(TA_dir, 'TA_LeChantier_Masq.tif')
    with rasterio.open(filename, 'w', **meta) as dst:
        dst.write(arr, 1)

    # Create associated xml file
    xml_content = """
<?xml version="1.0" ?>
<FileOriMnt>
     <NameFileMnt>%s</NameFileMnt>
     <NombrePixels>%d %d</NombrePixels>
     <OriginePlani>0 0</OriginePlani>
     <ResolutionPlani>1 1</ResolutionPlani>
     <OrigineAlti>0</OrigineAlti>
     <ResolutionAlti>1</ResolutionAlti>
     <Geometrie>eGeomMNTFaisceauIm1PrCh_Px1D</Geometrie>
</FileOriMnt>""" % (filename, arr_shape[1], arr_shape[2])

    xml_filename = os.path.join(TA_dir, 'TA_LeChantier_Mask.xml')
    with open(xml_filename, 'w') as dst:
        dst.write(xml_content)





