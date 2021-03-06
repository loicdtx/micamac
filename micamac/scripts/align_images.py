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
import random
import argparse
import multiprocessing as mp
import functools
import tempfile
import json

import numpy as np
import matplotlib.pyplot as plt
import exiftool
import fiona
from shapely.geometry import mapping, shape
from flask import Flask, render_template, jsonify, request, session

from micasense import imageutils
import micasense.imageset as imageset

from micamac.micasense_utils import capture_to_point, capture_to_files
from micamac.flask_utils import shutdown_server
from micamac.sixs import modeled_irradiance_from_capture


app = Flask(__name__, template_folder='../../templates')
POLYGONS = []


@app.route('/')
def index():
    fc_tmp_file = os.path.join(tempfile.gettempdir(), 'micamac_fc.geojson')
    with open(fc_tmp_file) as src:
        fc = json.load(src)
    return render_template('index.html', fc=fc)


@app.route('/polygon', methods = ['POST'])
def post_polygon():
    content = request.get_json(silent=True)
    POLYGONS.append(content)
    shutdown_server()
    return jsonify('Bye')



def float_or_str(value):
    """Helper function to for mixed type input argument in argparse
    """
    try:
        return float(value)
    except:
        return value


def main(img_dir, out_dir, alt_thresh, ncores, start_count, scaling,
         irradiance, subset, layer, resolution):
    # Create output dir it doesn't exist yet
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
    # Load all images as imageset
    imgset = imageset.ImageSet.from_directory(img_dir)
    meta_list = imgset.as_nested_lists()
    # Make feature collection of image centers and write it to tmp file
    point_list = [capture_to_point(c) for c in imgset.captures]
    feature_list = [{'type': 'Feature',
                     'properties': {},
                     'geometry': mapping(x)}
                    for x in point_list]
    fc = {'type': 'FeatureCollection',
          'features': feature_list}

    ###########################
    #### Optionally cut a spatial subset of the images
    ##########################
    if subset == 'interactive':
        # Write feature collection to tmp file, to make it accessible to the flask app
        # without messing up with the session context
        fc_tmp_file = os.path.join(tempfile.gettempdir(), 'micamac_fc.geojson')
        with open(fc_tmp_file, 'w') as dst:
            json.dump(fc, dst)
        # Select spatial subset interactively (available as feature in POLYGONS[0])
        app.run(debug=False, host= '0.0.0.0')
        # Check which images intersect with the user defined polygon (list of booleans)
        poly_shape = shape(POLYGONS[0]['geometry'])
        in_polygon = [x.intersects(poly_shape) for x in point_list]
        print('Centroid of drawn polygon: %s' % poly_shape.centroid.wkt)
    elif subset is None:
        in_polygon = [True for x in point_list]
    elif os.path.exists(subset):
        with fiona.open(subset, layer) as src:
            poly_shape = shape(src[0]['geometry'])
        in_polygon = [x.intersects(poly_shape) for x in point_list]
        print('Centroid of supplied polygon: %s' % poly_shape.centroid.wkt)
    else:
        raise ValueError('--subset must be interactive, the path to an OGR file or left empty')

    ##################################
    ### Threshold on altitude
    ##################################
    if alt_thresh == 'interactive':
        alt_arr = np.array([x[3] for x in meta_list[0]])
        n, bins, patches = plt.hist(alt_arr, 100)
        plt.xlabel('Altitude')
        plt.ylabel('Freq')
        plt.show()
        # Ask user for alt threshold
        alt_thresh = input('Enter altitude threshold:')
        alt_thresh = float(alt_thresh)
        above_alt = [x[3] > alt_thresh for x in meta_list[0]]
    elif isinstance(alt_thresh, float):
        above_alt = [x[3] > alt_thresh for x in meta_list[0]]
    else:
        raise ValueError('--alt_thresh argument must be a float or interactive')

    # Combine both boolean lists (altitude and in_polygon)
    is_valid = [x and y for x,y in zip(above_alt, in_polygon)]

    #########################
    ### Optionally retrieve irradiance values
    #########################
    if irradiance == 'panel':
        # Trying first capture, then last if doesn't work
        try:
            panel_cap = imgset.captures[0]
            # Auto-detect panel, perform visual check, retrieve corresponding irradiance values
            if panel_cap.detect_panels() != 5:
                raise AssertionError('Panels could not be detected')
            panel_cap.plot_panels()
            # Visual check and ask for user confirmation
            panel_check = input("Are panels properly detected ? (y/n):")
            if panel_check != 'y':
                raise AssertionError('User input, unsuitable detected panels !')
        except Exception as e:
            print("Failed to use pre flight panels; trying post flight panel capture")
            panel_cap = imgset.captures[-1]
            # Auto-detect panel, perform visual check, retrieve corresponding irradiance values
            if panel_cap.detect_panels() != 5:
                raise AssertionError('Panels could not be detected')
            panel_cap.plot_panels()
            # Visual check and ask for user confirmation
            panel_check = input("Are panels properly detected ? (y/n):")
            if panel_check != 'y':
                raise AssertionError('User input, unsuitable detected panels !')
        # Retrieve irradiance values from panels reflectance
        img_type = 'reflectance'
        irradiance_list = panel_cap.panel_irradiance()
    elif irradiance == 'dls':
        img_type = 'reflectance'
        irradiance_list = None
    elif irradiance == 'sixs':
        # Pick the middle cature, and use it to model clear sky irradiance using 6s
        middle_c = imgset.captures[round(len(imgset.captures)/2)]
        img_type = 'reflectance'
        irradiance_list = modeled_irradiance_from_capture(middle_c)
    elif irradiance is None:
        img_type = None
        irradiance_list = None
    else:
        raise ValueError('Incorrect value for --reflectance, must be panel, dls or left empty')


    #########################
    ### Alignment parameters
    #########################
    # Select an arbitrary image, find warping and croping parameters, apply to image,
    # assemble a rgb composite to perform visual check
    alignment_confirmed = False
    while not alignment_confirmed:
        warp_cap_ind = random.randint(1, len(imgset.captures) - 1)
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

        alignment_check = input("""
Are all bands properly aligned? (y/n)
    y: Bands are properly aligned, begin processing
    n: Bands are not properly aliged or image is not representative of the whole set, try another image
"""
                               )
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
                      'out_dir': out_dir,
                      'irradiance_list': irradiance_list,
                      'img_type': img_type,
                      'resolution': resolution,
                      'scaling': scaling}
    # Run process function with multiprocessing
    pool = mp.Pool(ncores)
    pool.map(functools.partial(capture_to_files, **process_kwargs), cap_tuple_iterator)


if __name__ == '__main__':
    epilog = """
Process set of micasense rededge images from a flight. Performs:
    - Spatial subseting to retain only captures within Area of Interest (user defined
      either by interactively drawing a polygon, or by supplying vector file)
    - Optional conversion to reflectance using irradiance values extracted from
      either panel capture or DLS.
    - Write 6 single band geotiff in UInt16 for each capture (panchromatique + 5 rededge bands)

The cli requires plotting capabilities for user confirmation, so X-window must
be enabled when working over ssh

When --irr is set to panel (default), the first image is assume to be of the panel


Example usage:
--------------
# Display help
align_images.py --help

# Process the whole directory, to reflectance, with interactive drawing of AOI
align_images.py -i /path/to/images -o /path/to/output/dir -irr panel -subset interactive -n 40
"""
    # Instantiate argparse parser
    parser = argparse.ArgumentParser(epilog=epilog,
                                     formatter_class=argparse.RawTextHelpFormatter)

    # parser arguments
    parser.add_argument('-i', '--img_dir',
                        required=True,
                        type=str,
                        help='directory containing images (nested directories are fine)')

    parser.add_argument('-o', '--out_dir',
                        required=True,
                        type=str,
                        help='output directory')
    # scaling, reflectance, subset, layer
    parser.add_argument('-scaling', '--scaling',
                        type=int,
                        default=60000,
                        help='Scaling factor when storing reflectances or radiances as UInt16')

    parser.add_argument('-irr', '--irradiance',
                        type=str,
                        default=None,
                        help="""
Way of retrieving irradiance values for computing reflectance:
    panel: Use reflectance panel. It is assumed that panel images are present in the
           first and/or the last image of the set
    dls: Use onboad Downwelling Light Sensor
    sixs: Model clear sky irradiance values using sixs radiative transfer modeling
    None (leave empty): Reflectance is not computed and radiance images are returned instead
                        """)

    parser.add_argument('-subset', '--subset',
                        type=str,
                        default=None,
                        help="""
Optional spatial subset to restrict images processed.
    interactive: Opens a interactive map in a browser window and select the area of interest interactively
    /path/to/file.gpkg: Path to an OGR file. The first feature of the vector layer will be used to spatially subset the images
    None (leave empty): No spatial subsetting
                        """)

    parser.add_argument('-layer', '--layer',
                        type=str,
                        default=None,
                        help='Layer name when --subset is a path to a multilayer file')

    parser.add_argument('-alt', '--alt_thresh',
                        type=float_or_str,
                        default='interactive',
                        help = 'Consider only data above that altitude')

    parser.add_argument('-res', '--resolution',
                        type=float,
                        default=0.1,
                        help = """
Expected ground resolution in meters. Not very important, only used for
    approximative display of images in GIS software""")

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
