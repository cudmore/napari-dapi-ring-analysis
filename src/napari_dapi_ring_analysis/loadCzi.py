"""
Load czi files using aicsimageio
"""

import os
from pprint import pprint
from datetime import datetime

import pandas as pd

import tifffile

from aicsimageio import AICSImage
from aicspylibczi import CziFile

from napari_dapi_ring_analysis._logger import logger

loadFileTypes = ['.czi', '.tif', '.oir']

def loadFolder(folderPath) -> pd.DataFrame:
    """Load headers for a folder of czi files.
    
    Returns:
        pd.DataFrame of file headers, one per row
    """
    _folder, parentFolder = os.path.split(folderPath)

    fileList = os.listdir(folderPath)
    fileList = sorted(fileList)
    headerList = []
    #sumSlices = 0
    for file in fileList:
        _filestub, _ext = os.path.splitext(file)
        if not _ext in loadFileTypes:
            continue
        filePath = os.path.join(folderPath, file)

        #header = loadCziHeader(filePath)
        header = _loadHeader(filePath)
        
        #zPixels = header['zPixels']

        # header['firstSlice_mask'] = sumSlices
        # header['lastSlice_mask'] = sumSlices + zPixels - 1
        
        # header['parentFolder'] = parentFolder
        
        #sumSlices += zPixels
        
        headerList.append(header)

    df = pd.DataFrame(headerList)
    return df

def _loadHeader(path : str) -> dict:
    """Load an image stack header using AICSImageIO.
    """
    #logger.info(f'{path}')
    
    img = AICSImage(path)  # selects the first scene found
    
    xVoxel = img.physical_pixel_sizes.X
    yVoxel = img.physical_pixel_sizes.Y
    zVoxel = img.physical_pixel_sizes.Z

    #print(os.path.split(path)[1], xVoxel, type(xVoxel))

    xPixels = img.dims.X
    yPixels = img.dims.Y
    zPixels = img.dims.Z

    _parentFolder, _ = os.path.split(path)
    _, _parentFolder = os.path.split(_parentFolder)
    
    _date = ''
    _time = ''

    _header = {
        'file': os.path.split(path)[1],
        'parentFolder': _parentFolder,
        'date': _date,
        'time': _time,
        'xPixels': xPixels,
        'yPixels': yPixels,
        'zPixels': zPixels,
        'xVoxel': xVoxel,
        'yVoxel': yVoxel,
        'zVoxel': zVoxel,
    }

    return _header

def _loadTif(path):
    """Load from a tif
    
    This is the 100th time I have tried this :(
    """
    # img = AICSImage(path)  # selects the first scene found
    # xVoxel = img.physical_pixel_sizes.X
    # yVoxel = img.physical_pixel_sizes.Y
    # zVoxel = img.physical_pixel_sizes.Z
    # print('ome tif zVoxel:', zVoxel)

    with tifffile.TiffFile(path) as tif:
        volume = tif.asarray()  # (10, 2, 784, 784)
        axes = tif.series[0].axes  # ZCYX
        
        # print('tif.series[0]:', tif.series[0])
        # print('    axes:', tif.series[0].axes)
        # print('    dims:', tif.series[0].dims)
        # print('    attr:', tif.series[0].attr)

        page0 = tif.pages[0]
        
        # print('page0.tags:')
        # print(page0.tags)
        
        try:
            _XResolution = page0.tags['XResolution']
            xVoxel = _XResolution.value[1] / _XResolution.value[0]
            print('xVoxel:', xVoxel)
        except (KeyError) as e:
            xVoxel = 1
            logger.warning("Did not find 'XResolution' key in tif.pages[0].tags")

        try:
            _YResolution = page0.tags['YResolution']
            yVoxel = _YResolution.value[1] / _YResolution.value[0]
            print('yVoxel:', yVoxel)
        except (KeyError) as e:
            yVoxel = 1
            logger.warning("Did not find 'YResolution' key in tif.pages[0].tags")

        imagej_metadata = tif.imagej_metadata

        if imagej_metadata is not None:
            try:
                zVoxel = imagej_metadata['spacing']
            except (KeyError) as e:
                zVoxel = 1
                logger.warning("Did not find 'spacing' key imagej_metadata['spacing']")

    # HUGE
    # pprint(imagej_metadata)
    print('volume:', volume.shape, volume.dtype)
    print('axes:', axes, type(axes))

    slices = imagej_metadata['slices']
    
    try:
        channels = imagej_metadata['channels']
    except (KeyError) as e:
        logger.warning('imagej_metadata["channels"] does not exist')
    
    unit = imagej_metadata['unit']

def loadCziHeader(cziPath : str) -> dict:
    """Load header from a czi file.

    Notes:
        For Whistler datetime, I am just dropping "-07:00"
        Otherwise I get exception
        "Invalid isoformat string: '2022-09-06T11:28:35.0731032-07:00'"

        Whister czi files also have one too many decimals in fractional seconds
    """
    
    with open(cziPath) as f:
        czi = CziFile(f)

    #print('czi:', [x for x in dir(czi)])
    # print('  czi.meta:')
    # print(czi.meta)

    xpath_str = "./Metadata/Information/Document/CreationDate"
    _creationdate = czi.meta.findall(xpath_str)  #  [<Element 'CreationDate' at 0x7fa670647f40>]
    #print('_creationdate:', _creationdate)
    for creationdate in _creationdate:
        # xml.etree.ElementTree.Element
        #print('  creationdate:', creationdate)
        #print(dir(creationdate))
        _datetimeText = creationdate.text
        
        # _datetime: 2022-09-06T11:28:35.0731032-07:00
        if _datetimeText.endswith('-07:00'):
            _datetimeText = _datetimeText.replace('-07:00', '')
            _datetimeText = _datetimeText[0:-1]  # remove last fractional second

        # take apart datetime
        _date = ''
        _time = ''
        try:
            #_datetime = datetime.strptime(datetime_text, "%Y-%m-%dT%H:%M:%S%f")
            #_datetime = datetime.strptime(_datetimeText, "%Y-%m-%dT%H:%M:%S.%f%z")
            _datetime = datetime.fromisoformat(_datetimeText)
            #print(_datetime)
            _date = _datetime.strftime('%Y-%m-%d')
            _time = _datetime.strftime('%H-%M-%S')
        except (ValueError) as e:
            print(f'EXCEPTION IN PARSING TIME STR "{_datetimeText}"')
            print(e)

        img = AICSImage(cziPath)  # selects the first scene found
    
        xVoxel = img.physical_pixel_sizes.X
        yVoxel = img.physical_pixel_sizes.Y
        zVoxel = img.physical_pixel_sizes.Z

        xPixels = img.dims.X
        yPixels = img.dims.Y
        zPixels = img.dims.Z

        _parentFolder, _ = os.path.split(cziPath)
        _, _parentFolder = os.path.split(_parentFolder)
        
        _header = {
            'file': os.path.split(cziPath)[1],
            'parentFolder': _parentFolder,
            'date': _date,
            'time': _time,
            'xPixels': xPixels,
            'yPixels': yPixels,
            'zPixels': zPixels,
            'xVoxel': xVoxel,
            'yVoxel': yVoxel,
            'zVoxel': zVoxel,
        }

        return _header

if __name__ == '__main__':

    # cziPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/B35_Slice2_RS_DS1.czi'
    # header = loadCzi(cziPath)
    # pprint(header)

    # folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    # dfFolder = loadFolder(folderPath)
    # print(dfFolder)

    # a czi saved as tif in Fiji/ImageJ
    tifPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/G22_Slice2_RS_DS5.tif'
    tifPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/Untitled-1-channel.tif'
    tifPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/rgb.tif'
    tifPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/Composite.tif'
    _loadTif(tifPath)
