def dd2cardinals(lon, lat):
    """Determine cardinal direction from coordinates in decimal degrees

    Return:
        dict: Dict with cardinal directions under GPSLatitudeRef and GPSLongitudeRef keys
    """
    out = dict()
    if lon >= 0:
        out['GPSLongitudeRef'] = 'E'
    else:
        out['GPSLongitudeRef'] = 'W'
    if lat >= 0:
        out['GPSLatitudeRef'] = 'N'
    else:
        out['GPSLatitudeRef'] = 'S'
    return out


def exif_params_from_capture(c):
    """Build a valid exif paramaters set from a ``micasense.capture.Capture``
    """
    lat,lon,alt = c.location()
    gps_dt = c.utc_time()
    gps_date = gps_dt.date().isoformat()
    gps_time = gps_dt.time().isoformat()
    xres,yres = c.images[0].focal_plane_resolution_px_per_mm
    focal_length = c.images[0].focal_length
    focal_length_35 = c.images[0].focal_length_35
    GPS_dict = dd2cardinals(lon, lat)
    params = ['-GPSVersionID=2.2.0.0',
              '-GPSAltitudeRef="Above Sea Level"',
              '-GPSAltitude=%f' % alt,
              '-GPSLatitudeRef=%s' % GPS_dict['GPSLatitudeRef'],
              '-GPSLatitude=%f' % lat,
              '-GPSLongitudeRef=%s' % GPS_dict['GPSLongitudeRef'],
              '-GPSLongitude=%f' % lon,
              '-GPSDateStamp=%s' % gps_date,
              '-GPSTimeStamp=%s' % gps_time,
              '-FocalLength=%f' % focal_length,
              '-FocalPlaneXResolution=%f' % xres,
              '-FocalPlaneYResolution=%f' % yres,
              '-focallengthin35mmformat=%f' % focal_length_35,
              '-FocalPlaneResolutionUnit=mm']
    return [str.encode(x) for x in params]

