import os
import math

from affine import Affine
from shapely.geometry import Point
import rasterio
from rasterio.crs import CRS
import numpy as np
import exiftool

from micasense import imageutils

from micamac.exif_utils import exif_params_from_capture


def affine_from_capture(c, res):
    """Build an affine transform from a ``micasense.capture.Capture``

    Args:
        c (``micasense.captue.Capture``): The capture
        res (float): Expected ground resolution in meters

    TODO: I'm not at all sure that it's how affine rotation are handled

    Return:
        affine.Affine: Affine transform to be passed to rasterio open when writing
        the array to file
    """
    lat,lon,_ = c.location()
    res_deg = res / 111320
    yaw_rad = c.dls_pose()[0]
    yaw_deg = 360 - math.degrees(yaw_rad)
    aff = Affine(res_deg, 0, lon,
                 0, -res_deg, lat)
    return aff * Affine.rotation(yaw_deg)


def capture_to_files(cap_tuple, scaling, out_dir, warp_matrices, warp_mode,
                     cropped_dimensions, match_index, img_type=None,
                     irradiance_list=None, resolution=0.1):
    """Wrapper to align images of capture and write them to separate GeoTiffs on disk

    Args:
        cap_tuple (tuple): Tuple of (capture, is_valid, count)
    """
    cap, valid, count = cap_tuple
    if valid:
        if img_type == 'reflectance':
            cap.compute_reflectance(irradiance_list=irradiance_list)
        aligned_stack = imageutils.aligned_capture(capture=cap,
                                                   warp_matrices=warp_matrices,
                                                   warp_mode=warp_mode,
                                                   cropped_dimensions=cropped_dimensions,
                                                   match_index=match_index,
                                                   img_type=img_type)
        aligned_stack = aligned_stack * scaling
        aligned_stack[aligned_stack > 65535] = 65535
        aligned_stack = aligned_stack.astype('uint16')
        panchro_array = (0.299 * aligned_stack[:,:,2] + 0.587 * aligned_stack[:,:,1] + 0.114 * aligned_stack[:,:,0]) * 2
        panchro_array = panchro_array.astype('uint16')
        # Retrieve exif dict
        exif_params = exif_params_from_capture(cap)
        # Write to file
        blue_path = os.path.join(out_dir, 'blue_%05d.tif' % count)
        red_path = os.path.join(out_dir, 'red_%05d.tif' % count)
        green_path = os.path.join(out_dir, 'green_%05d.tif' % count)
        nir_path = os.path.join(out_dir, 'nir_%05d.tif' % count)
        edge_path = os.path.join(out_dir, 'edge_%05d.tif' % count)
        pan_path = os.path.join(out_dir, 'pan_%05d.tif' % count)
        # Write 5 bands stack to file on disk
        aff = affine_from_capture(cap, resolution)
        profile = {'driver': 'GTiff',
                   'count': 1,
                   'transform': aff,
                   'crs': CRS.from_epsg(4326),
                   'height': aligned_stack.shape[0],
                   'width': aligned_stack.shape[1],
                   'dtype': np.uint16}
        # Write blue
        with rasterio.open(blue_path, 'w', **profile) as dst:
            dst.write(aligned_stack[:,:,0], 1)
        # Write green 
        with rasterio.open(green_path, 'w', **profile) as dst:
            dst.write(aligned_stack[:,:,1], 1)
        # Write red
        with rasterio.open(red_path, 'w', **profile) as dst:
            dst.write(aligned_stack[:,:,2], 1)
        # Write nir
        with rasterio.open(nir_path, 'w', **profile) as dst:
            dst.write(aligned_stack[:,:,3], 1)
        # Write rededge
        with rasterio.open(edge_path, 'w', **profile) as dst:
            dst.write(aligned_stack[:,:,4], 1)
        # Write panchromatic
        with rasterio.open(pan_path, 'w', **profile) as dst:
            dst.write(panchro_array, 1)
        with exiftool.ExifTool() as et:
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(blue_path))
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(green_path))
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(red_path))
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(nir_path))
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(edge_path))
            et.execute(*exif_params,
                       str.encode('-overwrite_original'),
                       str.encode(pan_path))

    cap.clear_image_data()


def capture_to_point(c, ndigits=6):
    """Build a shapely Point from a capture
    """
    lat,lon,_ = [round(x, ndigits) for x in c.location()]
    return Point(lon, lat)
