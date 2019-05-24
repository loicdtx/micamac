*******
MicaMAC
*******

*multispectral ortho-mosaics for micasense redEdge cameras using MICMAC*

`Micasense RedEdge camera <https://www.micasense.com/rededge-mx>`_
`MICMAC <https://github.com/micmacIGN/micmac>`_ 

MicaMAC is a set of wrappers to facilitate the generation of ortho-mosaics out of micasense RedEdge data; it uses the `micasense python package <https://github.com/micasense/imageprocessing>`_, MICMAC and a bit of python. 

Processing micasense RedEdge data does not work out of the box with free/open-source photogrammetry software tools like MICMAC mainly for 3 reasons:
- The individual bands of the raw captures are not aligned with each others
- There are five bands while most software are optimized for 3 bands (RGB) images.
- Many software do not support tiff file format and/or data in int16. Again, optimized for "classic" photographs (3 bands jpg image in int8). MICMAC is the exception there as it's perfectly happy using tiff in int16.
  

Usage
=====

There are two command lines:
- ``align_images.py`` performs bands alignent, optional altitude and AOI filtering, and optional conversion to surface reflectance.
- ``run_micmac.py`` runs a more or less standard micmac workflow on the results of the ``align_images.py`` command, resulting in the generation of ortho-mosaic, DEM and dense point cloud.
  
Both command lines have a detailed manual that can be accessed by running the command with the ``--help`` flag.


Installation
============

1. Install MICMAC (see `installation guide <https://micmac.ensg.eu/index.php/Install>`_ )
2. Clone the repos:
   
.. code-block:: bash

    git clone https://github.com/loicdtx/micamac.git

3. Install python dependencies and package (preferably inside a python3 virtualenv)

.. code-block:: bash

    cd micamac
    pip install -r requirements.txt
    pip install -e .

4. Optionally if you have flights without proper panel captures and DLS but still want some sort of conversion to reflectance/normalization among flights (using 6S radiative transfer modeling), you can use the ``irraiance-modeling`` branch. For that you must install `Py6S <https://github.com/robintw/Py6S>`_ (and ``6S``).
