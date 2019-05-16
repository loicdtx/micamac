#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
from setuptools import setup, find_packages
import os

# Parse the version from the main __init__.py
with open('micamac/__init__.py') as f:
    for line in f:
        if line.find("__version__") >= 0:
            version = line.split("=")[1].strip()
            version = version.strip('"')
            version = version.strip("'")
            continue


setup(name='micamac',
      version=version,
      description=u"Multi-spectral orthomosaic generation with micmac",
      author=u"Loic Dutrieux",
      author_email='loic.dutrieux@cirad.fr',
      license='GPLv3',
      packages=find_packages(),
      install_requires=[
          'shapely',
          'fiona',
          'rasterio',
          'numpy',
          'matplotlib',
          'flask',
          'micasense',
          'pyexiftool'],
      scripts=[
          # 'micamac/scripts/get_centers.py',
          'micamac/scripts/align_images.py',
          # 'micamac/scripts/run_micmac.py'
      ])
