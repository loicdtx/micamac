def run_tawny(color):
    """tawny wrapper to be called in a multiprocessing map
    """
    subprocess.call(['mm3d', 'Tawny',
                     'Ortho-%s' % color,
                     'DEq=0', 'DegRap=1'])


def img_to_Point(img_path):
    with exiftool.ExifTool() as et:
        meta = et.get_metadata(img_path)
    geom = Point(meta['EXIF:GPSLongitude'], meta['EXIF:GPSLatitude'])
    return (geom, img_path)


def dir_to_points():
    """Get a list of Points corresponding to centers of pan images contained in the current directory
    """
    img_list = glob.glob('pan*tif')
    all_cpu = mp.cpu_count()
    pool = mp.Pool(all_cpu)
    point_list = pool.map(img_to_Point, img_list)
    return point_list


def update_poubelle():
    pass


def update_ori():
    pass


def clean_intermediary():
    pass


def clean_images():
    pass


def create_proj_file(zone):
    pass
