#!/usr/bin/env python3

import argparse
import os
import subprocess
import multiprocessing as mp


COLORS = ['blue', 'green', 'red', 'nir', 'edge']

def sf_runner(ortho_dir):
    os.chdir(ortho_dir)
    subprocess.call(['mm3d', 'TestLib', 'SeamlineFeathering',
                     'Ort_.*tif', 'ApplyRE=1', 'ComputeRE=1',
                     'SzBox=[5000,5000]'])

# MosaicFeathering.tif

def main(img_dir, utm):
    # Create output dir and run gdal_translate
    if not os.path.exists('OUTPUT'):
        os.makedirs('OUTPUT')

    # Build iterable (list of the ortho dirs)
    ortho_dirs = [os.path.join(img_dir, 'Ortho-%s' % color) for color in COLORS]

    # Run Tawny for every band
    pool = mp.Pool(2)
    pool.map(sf_runner, ortho_dirs)

    os.chdir(img_dir)

    for color in COLORS:
        subprocess.call(['gdal_translate', '-a_srs',
                         '+proj=utm +zone=%d +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % utm,
                         'Ortho-%s/MosaicFeathering.tif' % color,
                         'OUTPUT/mosaicFeathering_%s.tif' % color])


if __name__ == '__main__':
    epilog = """
Run micmac SeamlineFeathering mosaicking tool

Example usage:
--------------
# Display help
run_seamline_feathering.py --help

# With specific parameters
run_seamline_feathering.py -i /path/to/images --utm 33
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

    parsed_args = parser.parse_args()
    main(**vars(parsed_args))












