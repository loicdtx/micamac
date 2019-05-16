#!/usr/bin/env python3

"""
Loic Dutrieux, May 2019
Command line to pre-process micasense red-edge images; performs:
    - Interactive subsetting to remove e.g. plane turns, approach, etc
    - Optional conversion to reflectance
    - bands alignment
    - export each band independently to geotiff
    - Produce panchromatic band and export it to geotiff
    - Add geotags and other georeferencing metadata to exif
"""
import os
import glob
from fractions import Fraction
import random
import argparse
import multiprocessing as mp
import functools
import math

import numpy as np
import matplotlib.pyplot as plt
import imageio
import exiftool
import rasterio
from rasterio.crs import CRS
from affine import Affine
from shapely.geometry import mapping
from flask import Flask, render_template, jsonify, request, session

from micasense import imageutils
import micasense.imageset as imageset
from micasense.capture import Capture

from micamac.micasense_utils import capture_to_point


app = Flask(__name__, template_folder='../../templates')
POLYGONS = []


def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()




def float_or_str(value):
    """Helper function to for mixed type input argument in argparse
    """
    try:
        return float(value)
    except:
        return value


def main(img_dir, out_dir, alt_thresh, ncores, start_count):
    # Create output dir it doesn't exist yet
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    # Load all images as imageset
    imgset = imageset.ImageSet.from_directory(img_dir)
    meta_list = imgset.as_nested_lists()
    feature_list = [{'type': 'Feature',
                     'properties': {},
                     'geometry': mapping(capture_to_point(c))}
                    for c in imgset.captures]
    fc = {'type': 'FeatureCollection',
          'features': feature_list}

    @app.route('/')
    def index():
        return render_template('index.html', fc=fc)


    @app.route('/polygon', methods = ['POST'])
    def post_polygon():
        content = request.get_json(silent=True)
        POLYGONS.append(content)
        shutdown_server()
        return jsonify('Bye')

    # Select spatial subset
    app.run(debug=False)

    # mean_altitude = np.mean([x[3] for x in meta_list[0]])
    if alt_thresh == 'interactive':
        alt_arr = np.array([x[3] for x in meta_list[0]])
        n, bins, patches = plt.hist(alt_arr, 100)
        plt.xlabel('Altitude')
        plt.ylabel('Freq')
        plt.show()
        # Ask user for alt threshold
        alt_thresh = input('Enter altitude threshold:')
        alt_thresh = float(alt_thresh)
        is_valid = [x[3] > alt_thresh for x in meta_list[0]]
    elif isinstance(alt_thresh, float):
        is_valid = [x[3] > alt_thresh for x in meta_list[0]]
    else:
        raise ValueError('--alt_thresh argument must be a float or interactive')

    #########################
    ### Alignment parameters
    #########################
    # Select an arbitrary image, find warping and croping parameters, apply to image,
    # assemble a rgb composite to perform visual check
    alignment_confirmed = False
    while not alignment_confirmed:
        warp_cap_ind = random.randint(1, len(imgset.captures))
        warp_cap = imgset.captures[warp_cap_ind]
        warp_matrices, alignment_pairs = imageutils.align_capture(warp_cap,
                                                                  max_iterations=100,
                                                                  multithreaded=True)
        print("Finished Aligning")
        # Retrieve cropping dimensions
        cropped_dimensions, edges = imageutils.find_crop_bounds(warp_cap, warp_matrices)
        warp_mode = alignment_pairs[0]['warp_mode']
        match_index = alignment_pairs[0]['ref_index']
        # Apply warping and cropping to the Capture used for finding the parameters to
        # later perform a visual check
        im_aligned = imageutils.aligned_capture(warp_cap, warp_matrices, warp_mode,
                                                cropped_dimensions, match_index,
                                                img_type='radiance')
        rgb_list = [imageutils.normalize(im_aligned[:,:,i]) for i in [0,1,2]]
        plt.imshow(np.stack(rgb_list, axis=-1))
        plt.show()

        cir_list = [imageutils.normalize(im_aligned[:,:,i]) for i in [1,3,4]]
        plt.imshow(np.stack(cir_list, axis=-1))
        plt.show()

        alignment_check = input("Are all bands properly aligned? y: begin processing; n: try another image (y/n):")
        if alignment_check.lower() == 'y':
            alignment_confirmed = True
        else:
            print('Trying another image')

    ##################
    ### Processing
    #################
    # Build iterator of captures
    cap_tuple_iterator = zip(imgset.captures, is_valid,
                             range(start_count, len(is_valid) + start_count))
    process_kwargs = {'warp_matrices': warp_matrices,
                      'warp_mode': warp_mode,
                      'cropped_dimensions': cropped_dimensions,
                      'match_index': match_index,
                      'out_dir': out_dir}
    # Run process function with multiprocessing
    pool = mp.Pool(ncores)
    pool.map(functools.partial(process, **process_kwargs), cap_tuple_iterator)


if __name__ == '__main__':
    epilog = """
Process set of micasense rededge images from a flight.
- Optional computation of irradiance values from panel reflectance
- Conversion from radiance to reflectance
- Bands alignment

The cli requires plotting capabilities for user confirmation, so X-window must
be enabled when working over ssh

When --irr is set to panel (default), the first image is assume to be of the panel


Example usage:
--------------
# Display help
./micasense_raw_to_jpg.py --help

# Generate rgb files for an entire flight using irradiance values retrieved from panel image
./micasense_raw_to_jpg.py -i /path/to/images -o /path/to/output/dir
"""
    # Instantiate argparse parser
    parser = argparse.ArgumentParser(epilog=epilog,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    # parser arguments
    parser.add_argument('-i', '--img_dir',
                        required=True,
                        type=str,
                        help='directory containing images (nested directories are fine)')

    parser.add_argument('-o', '--out_dir',
                        required=True,
                        type=str,
                        help='output directory')

    parser.add_argument('-alt', '--alt_thresh',
                        type=float_or_str,
                        default='interactive',
                        help = 'Consider only data above that altitude')

    parser.add_argument('-n', '--ncores',
                        default=20,
                        type=int,
                        help='Number of cores to use for multiprocessing')

    parser.add_argument('-scount', '--start_count',
                        default=0,
                        type=int,
                        help='Number of first image processed (useful for merging several batches)')

    parsed_args = parser.parse_args()
    main(**vars(parsed_args))
