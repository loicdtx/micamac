from Py6S import *

try:
    SixS.test()
except Exception as e:
    _has_sixs = False
else:
    _has_sixs = True



WAVELENGTHS = [0.475, 0.560, 0.668, 0.840, 0.717]


def modeled_irradiance_from_capture(c):
    """Retrieve an approximative modeled irradiance value for each band assuming clear sky conditions

    Args:
        c (micasense.capture.Capture): The capture from time and location will
            be used to model the irradiance

    Returns:
        list: List of five elements corresponding to the modeled irradiance for each
        of the five spectral chanels
    """
    if not _has_sixs:
        raise ImportError('Py6S must be installed and properly configured (6s binary installed) to use that function')
    c_time = c.utc_time().strftime('%d/%m/%Y %H:%M:%S')
    c_lat,c_lon,_ = c.location()
    s = SixS()
    s.atmos_profile = AtmosProfile.FromLatitudeAndDate(c_lat, c_time)
    s.geometry.from_time_and_location(c_lat, c_lon, c_time, 0, 0)
    irradiance_list = SixSHelpers.Wavelengths.run_wavelengths(s, wavelengths=WAVELENGTHS,
                                                              output_name='direct_solar_irradiance',
                                                              verbose=False)
    return [x/1000 for x in irradiance_list[1]]

