import math

from affine import Affine

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


def capture_to_files(c, path, count, scaling, warp_matrices, warp_mode,
                     cropped_dimensions, match_index, img_type=None):
    """Wrapper to align images of capture and write them to separate GeoTiffs on disk
    """
    pass
