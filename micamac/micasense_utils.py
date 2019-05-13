def affine_from_capture(c):
    lat,lon,_ = c.location()
    # xres,yres = c.images[0].focal_plane_resolution_px_per_mm
    xres, yres = (100, 100)
    xres_deg = xres / 111320000
    yres_deg = yres / 111320000
    yaw_rad = c.dls_pose()[0]
    yaw_deg = 360 - math.degrees(yaw_rad)
    aff = Affine(xres_deg, 0, lon,
                 0, -yres_deg, lat)
    return aff * Affine.rotation(yaw_deg)


def capture_to_files(c, path, count, scaling, affine, exif_params):
    pass
