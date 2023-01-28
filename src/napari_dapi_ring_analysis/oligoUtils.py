"""
20221101
"""
import os

import numpy as np

from skimage.filters import threshold_otsu, gaussian

from aicssegmentation.core.vessel import filament_2d_wrapper
from aicssegmentation.core.pre_processing_utils import intensity_normalization, image_smoothing_gaussian_3d, edge_preserving_smoothing_3d
from aicssegmentation.core.pre_processing_utils import suggest_normalization_param
from skimage.morphology import remove_small_objects     # function for post-processing (size filter)

from napari_dapi_ring_analysis._logger import logger

def aicsSuggestedNorm(imgData):
    """Ask aics how to normalize an image to define
        parameter xxx.
    """
    return suggest_normalization_param(imgData)

def aicsSegment(imgData : np.ndarray,
        # intensity_scaling_param = [3.5, 15],
        intensity_scaling_param = [1, 17],
        gaussian_smoothing_sigma = 1,
        f2_param = [[1.25, 0.16], [2.5, 0.16/2]],
        minArea = 5,
        ):
    """Segment Oligo stack with aics tomm20 workflow
    
    Args:
        intensity_scaling_param:
        gaussian_smoothing_sigma:
        f2_param:

    Try this on imgData:
        from aicssegmentation.core.pre_processing_utils import suggest_normalization_param
        suggest_normalization_param(struct_img0)

    Returns:
        dict: keys are np.ndarray with intermediate steps
    """

    # intensity normalization
    imgNorm = intensity_normalization(imgData, scaling_param=intensity_scaling_param)

    # smoothing with 2d gaussian filter slice by slice 
    imgSmooth = image_smoothing_gaussian_3d(imgNorm, sigma=gaussian_smoothing_sigma)

    # filament filter
    imgFilament = filament_2d_wrapper(imgSmooth, f2_param)

    imgRemoveSmall = remove_small_objects(imgFilament>0, min_size=minArea,
                                                connectivity=1, in_place=False)

    # Or, edge-preserving smoothing
    # imgSmooth = edge_preserving_smoothing_3d(imgNorm)

    retDict = {
        'imgData': imgData,
        'imgNorm': imgNorm,
        'imgSmooth': imgSmooth, 
        'imgFilament': imgFilament,
        'imgRemoveSmall': imgRemoveSmall,
    }

    return retDict

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

def parseFileName(filePath : str):
    """Parse Christine/Whislter file names.

    Args:
        filePath: full path to raw czi file.

    Given a file like: 'B35_Slice2_RS_DS1.czi'
        animalID: B35
        sliceNumber: slice2 (slices coming off vibratome/cryostat)
        hemisphere: RS
        region: DS for dorsal striatum and NA for nucleus acumbens
        imageNumber: whatever is trailing

        B35_Slice2_RS_DS1.czi
        B36_Slice2_LS_DS_1.0.czi
        G19_Slice1_LS_NAc.czi
        G20_Slice3_LS_NAc.czi
        G22_Slice2_RS_DS5.czi
        P10_Slice2_RS_DS1.czi
        P11_Slice1_LS_NAcmedial.czi
        B36_Slice2_LS_DS_1.1.czi

    """
    retDict = {
        'animalID': None,
        'sliceNumber': None,
        'hemisphere': None,
        'region': None,
        'imageNumber': None,
    }
    filename = os.path.split(filePath)[1]

    firstUnderscore = filename.find('_')
    if firstUnderscore == -1:
        logger.error(f'no _ in filename: {filename}')
        return
    retDict['animalID'] = filename[0:firstUnderscore]
    
    secondUnderscore = filename.find('_', firstUnderscore+1)
    retDict['sliceNumber'] = filename[firstUnderscore+1:secondUnderscore]

    leftSide = filename.find('LS_') != -1
    rightSide = filename.find('RS_') != -1
    if leftSide and rightSide or (not leftSide and not rightSide):
        logger.error(f'ambiguous left/right hemisphere: {filename}')
        logger.error(f'  filePath:{filePath}')
    else:
        if leftSide:
            retDict['hemisphere'] = 'LS'
        elif rightSide:
            retDict['hemisphere'] = 'RS'

    # _region: DS for dorsal striatum and NA for nucleus acumbens
    dorsalStriatum = filename.find('_DS') != -1
    nucleusAcumbens = (filename.find('_NA') != -1) or (filename.find('_Na') != -1)
    if dorsalStriatum and nucleusAcumbens or (not dorsalStriatum and not nucleusAcumbens):
        logger.error(f'ambiguous region for DS/NA: {filename}')
        logger.error(f'  filePath:{filePath}')
    else:
        if dorsalStriatum:
            retDict['region'] = 'DoS'
        elif nucleusAcumbens:
            retDict['region'] = 'NuA'

        # trailing after (_DS, _NA, _Na)
        if dorsalStriatum:
            dsIdx = filename.find('_DS') + 3
            retDict['imageNumber'] = filename[dsIdx:]  # will have .czi on end
            retDict['imageNumber'] = os.path.splitext(retDict['imageNumber'])[0]
        elif nucleusAcumbens:
            _tmpFileName = filename.upper()
            naIdx = _tmpFileName.find('_NA') + 3
            retDict['imageNumber'] = filename[naIdx:]  # will have .czi on end
            retDict['imageNumber'] = os.path.splitext(retDict['imageNumber'])[0]
        # naIdx = filename.find('_NA')
        # if naIdx == -1:
        #     naIdx = filename.find('_Na')
    
    #
    return retDict

def testParseFileName():
    """test parseFileName() on a pre-saved csv
    
    """
    from pprint import pprint
    
    csvPath = '/Users/cudmore/Desktop/oligo-summary-20221209-v2.csv'
    df = pd.read_csv(csvPath)

    dictList = []
    
    files = df['file']
    for file in files:
        colDict = parseFileName(file)
        dictList.append(colDict)
        #pprint(colDict)

    dfOut = pd.DataFrame(dictList)
    print(dfOut)
