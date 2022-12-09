"""
20221101
"""
import os

import numpy as np

from skimage.filters import threshold_otsu, gaussian

from napari_dapi_ring_analysis._logger import logger

def getOtsuThreshold(imgData : np.ndarray, sigma):
    """
    
    Args:
        imgData: (z,y,x)
        sigma:
    """
    #sigma = (0, 1, 1)
    #sigma = 1

    logger.info(f'imgData {imgData.shape} sigma:{sigma}')
    #printStack(imgData, 'getOtsuThreshold')

    # gaussian blur
    imgData_blurred = gaussian(imgData, sigma=sigma)

    # otsu threshold
    otsuThreshold = threshold_otsu(imgData_blurred)
    #print(f'{filename} otsu threshold: {otsuThreshold}')

    # make binary mask
    imgData_binary = imgData_blurred > otsuThreshold  # [True, False]

    return otsuThreshold, imgData_blurred, imgData_binary

def getEightBit(imgData : np.ndarray, maximizeHistogram = False) -> np.ndarray:
    """Convert an image to 8-bit np.uint8
    """
    
    
    if maximizeHistogram:
        # this will maximize range (might not be good)
        imgData = imgData / np.max(imgData) * 255
        imgData = imgData.astype(np.uint8)        
    else:
        # assuming czi files are 2**16, just divide by 2**8
        imgData = imgData / 2**8
        imgData = imgData.astype(np.uint8)
 
    return imgData

def printStack(imgData : np.ndarray, name : str = ''):
    logger.info(f'  {name}: {imgData.shape} {imgData.dtype} min:{np.min(imgData)} max:{np.max(imgData)}')
