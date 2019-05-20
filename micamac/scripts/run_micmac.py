#!/usr/bin/env python3

import argparse
import os
import glob
import shutil
import re
import subprocess
import multiprocessing as mp

from shapely.geometry import Point

from micamac.micmac_utils import run_tawny, dir_to_points, update_poubelle, update_ori
from micamac.micmac_utils import create_proj_file, clean_intermediary, clean_images


COLORS = ['blue', 'green', 'red', 'nir', 'edge']


def main(img_dir, lon, lat, radius, resolution, ortho, dem, ply,
         ncores, utm, clean-intermediary, clean-images):
    if not any([ortho, dem, ply]):
        raise ValueError('You must select at least one of --ortho, --dem and --ply')
    # Set workdir
    os.chdir(img_dir)
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
    """ % utm

    with open('SysUTM.xml', 'w') as dst:
        dst.write(proj_xml)


    # mm3d XifGps2Txt "rgb.*tif" 
    subprocess.call(['mm3d', 'XifGps2Txt', 'pan.*tif'])

    # mm3d XifGps2Xml "rgb.*tif" RAWGNSS
    subprocess.call(['mm3d', 'XifGps2Xml', 'pan.*tif', 'RAWGNSS'])

    # mm3d OriConvert "#F=N X Y Z" GpsCoordinatesFromExif.txt RAWGNSS_N ChSys=DegreeWGS84@RTLFromExif.xml MTD1=1 NameCple=FileImagesNeighbour.xml NbImC=25
    subprocess.call(['mm3d', 'OriConvert', '#F=N X Y Z',
                     'GpsCoordinatesFromExif.txt', 'RAWGNSS_N',
                     'ChSys=DegreeWGS84@RTLFromExif.xml', 'MTD1=1',
                     'NameCple=FileImagesNeighbour.xml', 'NbImC=20'])

    # mm3d Tapioca File FileImagesNeighbour.xml -1
    subprocess.call(['mm3d', 'Tapioca', 'File',
                     'FileImagesNeighbour.xml', '-1'])

    # mm3d Schnaps "pan.*tif" MoveBadImgs=1
    subprocess.call(['mm3d', 'Schnaps', 'pan.*tif', 'MoveBadImgs=1'])

    # Build a list of file around the provided coordinate to compute a pre orientation model
    radius_dd = radius / 111320.0
    search_polygon = Point(lon, lat).buffer(radius_dd)
    point_list = dir_to_points()
    img_list = []
    for point_tuple in point_list:
        if point_tuple[0].intersects(search_polygon):
            img_list.append(point_tuple[1])
    # mm3d Tapas FraserBasic $file_list Out=Arbitrary_pre SH=_mini
    subprocess.call(['mm3d', 'Tapas', 'FraserBasic',
                     '|'.join(img_list),
                     'Out=Arbitrary_pre', 'SH=_mini'])

    # Compute orientation model for the full block
    # mm3d Tapas FraserBasic "pan.*tif" Out=Arbitrary SH=_mini InCal=Arbitrary_pre
    p = subprocess.Popen(['mm3d', 'Tapas', 'FraserBasic',
                          'pan.*tif', 'Out=Arbitrary', 'SH=_mini',
                          'InCal=Arbitrary_pre'])
    p.communicate(input='\n')

    # mm3d CenterBascule "rgb.*tif" Arbitrary RAWGNSS_N Ground_Init_RTL
    subprocess.call(['mm3d', 'CenterBascule', 'pan.*tif',
                     'Arbitrary', 'RAWGNSS_N', 'Ground_Init_RTL'])

    # mm3d Campari "rgb.*tif" Ground_Init_RTL Ground_RTL EmGPS=\[RAWGNSS_N,5\] AllFree=1 SH=_mini
    subprocess.call(['mm3d', 'Campari', 'pan.*tif', 'Ground_Init_RTL', 'Ground_RTL',
                     'EmGPS=[RAWGNSS_N,5]', 'AllFree=1', 'SH=_mini'])

    # mm3d ChgSysCo  "rgb.*tif" Ground_RTL RTLFromExif.xml@SysUTM.xml Ground_UTM
    subprocess.call(['mm3d', 'ChgSysCo', 'pan.*tif',
                     'Ground_RTL', 'RTLFromExif.xml@SysUTM.xml', 'Ground_UTM'])

    # Run malt for panchromatic
    subprocess.call(['mm3d', 'Malt', 'Ortho',
                     'pan.*tif', 'Ground_UTM', 'ResolTerrain=%f' % resolution])

    # MIrror content of POubelle for all colors
    update_poubelle()

    # Create orientation files for every color
    update_ori()

    # Run malt for every band
    for color in COLORS:
        subprocess.call(['mm3d', 'Malt', 'Ortho',
                         '(pan|%s).*tif' % color,
                         'Ground_UTM', 'DoMEC=0', 'DoOrtho=1',
                         'ImOrtho="%s.*.tif"' % color,
                         'DirOF=Ortho-%s' % color,
                         'DirMEC=MEC-Malt',
                         'ImMNT="pan.*tif"',
                         'ResolTerrain=%f' % resolution])

    # Create output dir and run gdal_translate
    if not os.path.exists('OUTPUT'):
        os.makedirs('OUTPUT')

    if ortho:
        # Run Tawny for every band
        pool = mp.Pool(ncores)
        pool.map(run_tawny, COLORS)

        for color in COLORS:
            subprocess.call(['gdal_translate', '-a_srs',
                             '+proj=utm +zone=%d +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % utm,
                             'Ortho-%s/Orthophotomosaic.tif' % color,
                             'OUTPUT/ortho_%s.tif' % color])
    if dem:
        pass

    if ply:
        pass

    if clean-intermediary:
        clean_intermediary()

    if clean-images:
        clean_images()



if __name__ == '__main__':
    epilog = """
Run micmac Ortho generation workflow on previously aligned micasense bands


Example usage:
--------------
# Display help
./run_micmac.py --help

# Run workflow and clean intermediary outputs
./run_micmac.py -i /path/to/images --lon 12.43 --lat 1.234 --utm 33 --clean
"""
    # Instantiate argparse parser
    parser = argparse.ArgumentParser(epilog=epilog,
                                     formatter_class=argparse.RawTextHelpFormatter)

    # parser arguments
    parser.add_argument('-i', '--img_dir',
                        required=True,
                        type=str,
                        help='directory containing images')

    parser.add_argument('-lon', '--lon',
                        required=True,
                        type=float,
                        help='Pre-orientation image cluster center longitude')

    parser.add_argument('-lat', '--lat',
                        required=True,
                        type=float,
                        help='Pre-orientation image cluster center latitude')

    parser.add_argument('-rad', '--radius',
                        required=True,
                        type=float,
                        help='Search radius in meters around provided coordinates, to select pre-orientation image subset')

    parser.add_argument('-res', '--resolution',
                        default=0.1,
                        type=float,
                        help='Resolution of the produced orthomosaic in meters')

    parser.add_argument('-ortho', '--ortho',
                        action='store_true',
                        help='Export orthomosaic')

    parser.add_argument('-dem', '--dem',
                        action='store_true',
                        help='Export DEM')

    parser.add_argument('-ply', '--ply',
                        action='store_true',
                        help='Exporte dense point cloud')

    parser.add_argument('-n', '--ncores',
                        default=5,
                        type=int,
                        help="""
Number of cores to use for multiprocessing. There\'s no use in setting it >5,
for it\'s only used for running Tawny in parallel on the 5 bands. This argument has no impact
on the other micmac steps that use all threads available""")

    parser.add_argument('-utm', '--utm',
                        default=33,
                        type=int,
                        help='UTM zone of the output orthomosaic')

    parser.add_argument('-c-int', '--clean-intermediary',
                        action='store_true',
                        help='Clean all intermediary output after terminating (folder auto-generated by micmac)')

    parser.add_argument('-c-img', '--clean-images',
                        action='store_true',
                        help='Delete all input images after successful completion')


    parsed_args = parser.parse_args()
    main(**vars(parsed_args))











