#!/usr/bin/env python3

import argparse
import os
import glob
import shutil
import re
import subprocess
import multiprocessing as mp

from micamac.micmac_utils import run_tawny


COLORS = ['blue', 'green', 'red', 'nir', 'edge']

# Every orthomosaic may require radiometric equalization parameters tuning
# The command re-runs tawny for all 5 bands without overwriting previous results
def tawny_runner(color, args):
    subprocess.call(['mm3d', 'Tawny',
                     'Ortho-%s' % color,
                     *args])

def main(img_dir, filename_prefix, utm, **kwargs):
    ## kwargs should contain:
        # RadiomEgal, DEq, DEqXY, AddCste, DegRap, DegRapXY, SzV
    # Filter unset
    tawny_kwargs = {k:v for k,v in kwargs.items() if v is not None}

    Out = '%s.tif' % filename_prefix
    arg_list['Out'] = Out

    arg_list = ['{k}={v}'.format(k=k,v=v) for k,v in tawny_kwargs.items()]

    # Set workdir
    os.chdir(img_dir)

    # Create output dir and run gdal_translate
    if not os.path.exists('OUTPUT'):
        os.makedirs('OUTPUT')

    # Run Tawny for every band
    pool = mp.Pool(5)
    pool.map(tawny_runner, COLORS)

    for color in COLORS:
        subprocess.call(['gdal_translate', '-a_srs',
                         '+proj=utm +zone=%d +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % utm,
                         'Ortho-%s/%s.tif' % (color, filename_prefix),
                         'OUTPUT/%s_%s.tif' % (filename_prefix, color)])


if __name__ == '__main__':
    epilog = """
Re-run tawny with specific parameters on an existing project
See Tawny doc for more details on each paramaters

Example usage:
--------------
# Display help
./rerun_tawny.py --help

# With specific parameters
./rerun_tawny.py -i /path/to/images --utm 33 --filename-prefix ortho_zero_deq --DEq 0
"""
    # Instantiate argparse parser
    parser = argparse.ArgumentParser(epilog=epilog,
                                     formatter_class=argparse.RawTextHelpFormatter)

    # parser arguments
    parser.add_argument('-i', '--img_dir',
                        required=True,
                        type=str,
                        help='directory containing images')

    parser.add_argument('-utm', '--utm',
                        default=33,
                        type=int,
                        help='UTM zone of the output orthomosaic')

    parser.add_argument('--filename-prefix', '--filename-prefix',
                        default='Ortho2',
                        type=str,
                        help='Prefix used for the orthomosaic name (suffix is {color}.tif)')

    parser.add_argument('--RadiomEgal', dest='RadiomEgal', action='store_true')
    parser.add_argument('--no-RadiomEgal', dest='RadiomEgal', action='store_false')
    parser.set_defaults(RadiomEgal=True)

    parser.add_argument('--DEq', '-DEq',
                        default=1,
                        type=int,
                        help='Degree of equalization')

    parser.add_argument('--DEqXY', '-DEqXY',
                        default=None,
                        type=int,
                        nargs=2,
                        help='Degrees of equalization in X and Y directions, (supply two values)')

    parser.add_argument('--AddCste',
                        help='Add unknown constant for equalization',
                        action='store_true')

    parser.add_argument('--DegRap', '-DegRap',
                        help='Degree of rappel to initial values',
                        type=int,
                        default=0)

    parser.add_argument('--DegRapXY', '-DegRapXY',
                        help='Degree of rappel to initial values in X and Y directions (supply two values)',
                        type=int,
                        nargs=2,
                        default=None)

    parser.add_argument('--SzV', '-SzV',
                        help='Size of Window for equalization',
                        type=int,
                        default=1)

# RadiomEgal, DEq, DEqXY, AddCste, DegRap, DegRapXY, SzV

    parsed_args = parser.parse_args()
    main(**vars(parsed_args))












