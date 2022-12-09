"""
Run cellpose on 3d rgb stacks and save _seg.npy file
"""
import os
import sys
import pathlib
import tifffile

import numpy as np

from cellpose import models
from cellpose import utils, io

from cellpose.io import logger_setup

#import oligoanalysis
from napari_dapi_ring_analysis import oligoAnalysisFolder
from napari_dapi_ring_analysis._logger import logger

def getCellposeLog():
    """Get the full path to the <user> cellpose log file.
    """
    userPath = pathlib.Path.home()
    userCellposeFolder = os.path.join(userPath, '.cellpose')
    if not os.path.isdir(userCellposeFolder):
        logger.error(f'Did not find <user>.cellpose "{userCellposeFolder}"')
        return None
    
    _runLogFile = os.path.join(userCellposeFolder, 'run.log')
    if not os.path.isfile(_runLogFile):
        logger.error(f'Did not find user cellpose log file: "{_runLogFile}"')
        return None

    return _runLogFile

def getModels():
    """Return str list of full path for all models in 'oligoanalysis/models' folder.
    """

    import napari_dapi_ring_analysis
    _filepath = os.path.abspath(napari_dapi_ring_analysis.__file__)
    _folder, _ = os.path.split(_filepath)
    _folder = os.path.join(_folder, 'models')
    
    #logger.info(_folder)
    
    if not os.path.isdir(_folder):
        logger.error(f'did not find model path: {_folder}')
        return

    files = os.listdir(_folder)
    fileList = [os.path.join(_folder, file)
                    for file in sorted(files)]
    return fileList

def runModelOnImage(imgPath : str, imgData : np.ndarray = None, setupLogger=True):
    """Run our pre-defined (trained) model on one 3D RGB stack.
    
    Args:
        imgPath: full path to 3D rgb stack
        imgData: image data for 3D rgb stack
        setupLogger: if True will re-init logger in <user>/.cellpose/run.log
    """
    
    # setup cellpose logging to file
    #  <user>/.cellpose/run.log (see getCellposeLog())
    if setupLogger:
        logger_setup()
    
    if imgData is None:
        # load small 3d rgb stack
        imgData = tifffile.imread(imgPath)

    logger.info('cellpose runModelOnImage()')
    logger.info(f'  {imgPath}')  # (7, 196, 196, 3)
    
    # shape is (slices, x, y, rgb)
    logger.info(f'  {imgData.shape}')  # (7, 196, 196, 3)

    # gaussian filter each rgb channel
    from skimage.filters import threshold_otsu, gaussian
    from scipy.signal import medfilt
    doGauss = True
    _sigma = [0.5, 0.8, 0.8]
    _kernel_size = [1,3,3]
    logger.info(f'XXX blurring with gaussian/median to see if we get fewer labels')
    logger.info(f'    _sigma:{_sigma}')
    logger.info(f'    _kernel_size:{_kernel_size}')


    rgbChannels = imgData.shape[3]  # 3
    for rgbChannelIdx in range(rgbChannels):
        _oneChannel = imgData[:,:,:,rgbChannelIdx]
        #logger.info(f'    _onceChannel:{_oneChannel.shape}')

        if doGauss:
            _gausFilter = gaussian(_oneChannel, sigma=_sigma)  # float64
        else:
            
            _gausFilter = medfilt(_oneChannel, kernel_size=_kernel_size)  # uint8

        logger.info(f'  idx:{rgbChannelIdx} _gausFilter:{_gausFilter.shape} {_gausFilter.dtype}')
        logger.info(f'      min:{np.min(_gausFilter)} max:{np.max(_gausFilter)}')

        # convert back to 8-bit
        # _gausFilter = _gausFilter / 2**32  # gaus returns float64
        # _gausFilter = _gausFilter.astype(np.uint8)

        # this will maximize range (might not be good)
        if doGauss:
            _gausFilter = _gausFilter / np.max(_gausFilter) * 255
            _gausFilter = _gausFilter.astype(np.uint8)        

        logger.info(f'    2 _gausFilter:{_gausFilter.shape} {_gausFilter.dtype}')
        logger.info(f'      min:{np.min(_gausFilter)} max:{np.max(_gausFilter)}')
        imgData[:,:,:,rgbChannelIdx] = _gausFilter

    #sys.exit(1)

    gpu = False
    model_type = None  # 'cyto' or 'nuclei' or 'cyto2'
    
    pretrained_models = getModels()
    if pretrained_models is None:
        logger.warning('Did not find any models, cellpose is not running')
        return

    print('pretrained_models:')
    print(pretrained_models)
    pretrained_model = pretrained_models[1]  # '/Users/cudmore/Sites/oligo-analysis/models/CP_20221008_110626'
    # made new model at sfn CP_20221115_123812

    channels = [[2,1]]  # # grayscale=0, R=1, G=2, B=3
    diameter = 30 # 20 # 16.0
    do_3D = True
    net_avg = False

    # run model
    # masks, flows, styles, diams = model.eval(imgData,
    #                                 diameter=diameter, channels=channels,
    #                                 do_3D=do_3D)

    logger.info(f'  instantiating model with models.CellposeModel()')
    logger.info(f'    gpu: {gpu}')
    logger.info(f'    model_type: {model_type}')
    logger.info(f'    pretrained_model: {pretrained_model}')
    logger.info(f'    net_avg: {net_avg}')

    model = models.CellposeModel(gpu=gpu, model_type=model_type,
                                    pretrained_model=pretrained_model,
                                    net_avg=net_avg)

    logger.info('  running model.eval')
    logger.info(f'    diameter: {diameter}')
    logger.info(f'    channels: {channels}')
    logger.info(f'    do_3D: {do_3D}')

    masks, flows, styles = model.eval(imgData,
                                        diameter=diameter, channels=channels,
                                        do_3D=do_3D
                                        )

    # save
    logger.info(f'  saving cellpose _seg.npy into folder {os.path.split(imgPath)[0]}')
    # models.CellposeModel.eval does not return 'diams', using diameter
    io.masks_flows_to_seg(imgData, masks, flows, diameter, imgPath, channels)
    
    logger.info(f'  >>> DONE running cellpose on pre-trained model "{os.path.split(pretrained_model)[1]}" for file "{os.path.split(imgPath)[1]}"')

    # can't save 3d output as png
    # io.save_to_png(imgData, masks, flows, imgPath)

def batchRunFolder0():
    """run a cellpose model on entire folders of czi rgb stack
    """
    folderPath1 = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/Morphine'
    folderPath0 = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    
    folderPath2 = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Adolescent'
    folderPath3 = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Saline'
    
    folderPathList = [folderPath0, folderPath1, folderPath2, folderPath3]

    # do one folder for debugging
    folderPathList = [folderPath1]

    logger.info(f'Running on folderPathList')

    for folderPath in folderPathList:
        print(' . === ', folderPath)
        batchRunFolder(folderPath)

    print('DONE with _cellpose.py __main__')
    for folderPath in folderPathList:
        print(' . === ', folderPath)

def batchRunFolder(folderPath : str):
    """Run a cellpose model on each 3d rgb tif stack in a folder.
    
    This takes some time but is neccessary to make analysis easier.
    """
    
    #logger_setup()  # will clear .cellpose/run.log
    
    oaf = oligoAnalysisFolder(folderPath)
    df = oaf.getDataFrame()
    files = df['file'].tolist()
    for idx, file in enumerate(files):
        logger.info('\n')
        logger.info(f'=== {idx}/{len(files)-1} Fetching oligo analysis for file {file}')
        
        oa = oaf.getOligoAnalysis(file, loadImages=False)
        
        rgbStackPath = oa._getRgbPath()
        
        # this is our small-rgb stack, it is made from raw czi file
        # this should save?
        rgbStack = oa._getRgbStack()  # np.ndarrray
        
        #logger.info(f'  oligoanalysis rgbStack for cellpose shape is: {rgbStack.shape}')

        # the raw czi file
        # imgPath = os.path.join(folderPath, file)
        
        # here, imgPath is only used to determine where to save
        runModelOnImage(imgPath=rgbStackPath, imgData=rgbStack, setupLogger=False)

        # TODO: unload oligoAnalysis
        oa = None  # does this free memory ?

def saveSlices():
    """Open a 3d rgb and save the 2-channel slices
        Each slice will be rgb 8-bit without histogram normalization
    
        These rgb slices can be opened in cellpose
         - draw rois
         - train
    """
    folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    
    # folder to save all the slices in
    _, _folderName = os.path.split(folderPath)
    savePath = os.path.join(folderPath, f'{_folderName}_rgbSlices')
    if not os.path.isdir(savePath):
        os.mkdir(savePath)

    oaf = oligoAnalysisFolder(folderPath)
    df = oaf.getDataFrame()
    files = df['file'].tolist()
    
    masterSliceNumber = 0
    
    for idx, file in enumerate(files):
        # file is czi file
        logger.info('\n')
        logger.info(f'=== {idx}/{len(files)-1} Fetching oligo analysis for file {file}')
        
        oa = oaf.getOligoAnalysis(file, loadImages=False)
        
        rgbStackPath = oa._getRgbPath()
        rgbStack = oa._getRgbStack()  # np.ndarrray
        # like (10, 196, 196, 3)
        logger.info(f'  rgbStack: {rgbStack.shape}')

        # save the rgb stack in a folder, one file per slice
        fileStub, _ = os.path.splitext(file)
        numSlices = rgbStack.shape[0]
        for _sliceNum in range(numSlices):
            fileName = fileStub + '_' + str(masterSliceNumber).zfill(4) + '.tif'
            slicePath = os.path.join(savePath, fileName)
            oneSlice = rgbStack[_sliceNum, :, :, :]
            print(' . slicePath:', slicePath)
            
            tifffile.imsave(slicePath, oneSlice)

            masterSliceNumber += 1

if __name__ == '__main__':
    
    # save a folder of czi rgb to slices (to be opened in cellpose gui)
    # saveSlices()
    # sys.exit(1)

    # path = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/FST-analysis/B35_Slice2_RS_DS1.czi/B35_Slice2_RS_DS1-rgb-small.tif'
    # runModelOnImage(imgPath=path)

    # modelList = getModels()
    # for model in modelList:
    #     print(model)

    # logFile = getCellposeLog()
    # print(logFile)

    batchRunFolder0()