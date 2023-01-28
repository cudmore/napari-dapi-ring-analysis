"""
Run cellpose on 3d rgb stacks and save _seg.npy file
"""
import os
import sys
import json
import pathlib
import tifffile

import numpy as np

from cellpose import models
from cellpose import utils, io

from cellpose.io import logger_setup

from aicssegmentation.core.pre_processing_utils import intensity_normalization, image_smoothing_gaussian_3d, edge_preserving_smoothing_3d

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

    Output (saved)
        -cp,json with model parameters
        -seg.npy with cellpose output (mask is in there, it is hdf5 file)
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
    logger.info(f'  imgData: {imgData.shape} max:{np.max(imgData)}')  # (7, 196, 196, 3)

    # try to pre-scale, bacause I trained on rgb, this does not work
    # _imgDataGray = imgData[:,:,:,2]  # assuming 2 is dapi channel

    # intensity_scaling_param = [1, 17]
    # _imgDataGray = intensity_normalization(_imgDataGray, scaling_param=intensity_scaling_param)
    # logger.info(f'_imgDataGray:')
    # logger.info(f'  intensity_scaling_param: {intensity_scaling_param}')
    # logger.info(f'  {_imgDataGray.shape} max:{np.max(_imgDataGray)}')

    gpu = True
    model_type = None  # 'cyto' or 'nuclei' or 'cyto2'
    
    pretrained_models = getModels()
    if pretrained_models is None:
        logger.warning('Did not find any models, cellpose is not running')
        return

    # logger.info('pretrained_models:')
    # print('  ', pretrained_models)

    #pretrained_model = pretrained_models[1]  # '/Users/cudmore/Sites/oligo-analysis/models/CP_20221008_110626'

    # made new model at sfn CP_20221115_123812
    #pretrained_model = pretrained_models[2]  # '/Users/cudmore/Sites/oligo-analysis/models/CP_20221008_110626'

    pretrained_model = pretrained_models[3]  # '/Users/cudmore/Sites/oligo-analysis/models/CP_20221008_110626'

    #channels = [[2,1]]  # # grayscale=0, R=1, G=2, B=3
    channels = [[2,2]]  # # grayscale=0, R=1, G=2, B=3
    #channels = [[0,0]]  # # grayscale=0, R=1, G=2, B=3  # when using _imgDataGray
    
    diameter = 30 #28 # cellpose default is 30
    
    flow_threshold = 1.0  # default is 0.4 (ignored when using anisotropy)
    cellprob_threshold = -5  #-2  #-2  # [-6,6], lower number includes more

    anisotropy = 10  # ignores flow_threshold, z / xy um/pixel
    min_size = 380 # if not specified default to 15
    #min_size = -1  # to turn off

    do_3D = True
    #net_avg = False

    cellPoseDict = {
        'pretrained_model': os.path.split(pretrained_model)[1],
        'channels': channels,
        'diameter': diameter,
        'flow_threshold': flow_threshold,
        'cellprob_threshold': cellprob_threshold,
        'anisotropy': anisotropy,
        'min_size': min_size,
        'do_3D': do_3D,
        #'net_avg': net_avg,
    }

    logger.info(f'  instantiating model with models.CellposeModel()')
    logger.info(f'    gpu: {gpu}')
    logger.info(f'    model_type: {model_type}')
    logger.info(f'    pretrained_model: {pretrained_model}')
    #logger.info(f'    net_avg: {net_avg}')

    model = models.CellposeModel(gpu=gpu, model_type=model_type,
                                    pretrained_model=pretrained_model)

    logger.info('  running model.eval')
    logger.info(f'    diameter: {diameter}')
    logger.info(f'    flow_threshold: {flow_threshold}')
    logger.info(f'    cellprob_threshold: {cellprob_threshold}')
    logger.info(f'    channels: {channels}')
    logger.info(f'    do_3D: {do_3D}')


    # jan2023, flow_threshold = 0.4
    # try 0.8
    masks, flows, styles = model.eval(imgData,
                                        diameter=diameter,
                                        flow_threshold=flow_threshold,  # added jan2023
                                        cellprob_threshold=cellprob_threshold,
                                        channels=channels,
                                        do_3D=do_3D,
                                        anisotropy=anisotropy,
                                        min_size=min_size)

    # save
    logger.info(f'  saving cellpose _seg.npy into folder {os.path.split(imgPath)[0]}')
    # models.CellposeModel.eval does not return 'diams', using diameter
    io.masks_flows_to_seg(imgData, masks, flows, diameter, imgPath, channels)
    
    # save parameters
    paramPath = os.path.splitext(imgPath)[0]
    paramPath = paramPath + '-cp.json'
    logger.info(f'  saving cellpose params to {paramPath}')
    with open(paramPath, "w") as jsonOutfile:
        json.dump(cellPoseDict, jsonOutfile, indent=4)

    logger.info(f'  >>> DONE running cellpose on pre-trained model "{os.path.split(pretrained_model)[1]}" for file "{os.path.split(imgPath)[1]}"')

    # can't save 3d output as png
    # io.save_to_png(imgData, masks, flows, imgPath)

def batchRunFolder0():
    """run a cellpose model on entire folders of czi rgb stack
    """
    _rootPath = '/media/cudmore/data/Dropbox/data/whistler/'
    
    folderPathList = [
        _rootPath + 'cudmore/20221010/FST',
        _rootPath + 'cudmore/20221010/Morphine',

        _rootPath + 'cudmore/20221031/FST',
        _rootPath + 'cudmore/20221031/Morphine',

        _rootPath + 'cudmore/20221109/Adolescent',
        _rootPath + 'cudmore/20221109/Saline',

        _rootPath + 'cudmore/20230123/Saline',

    ]
    
    # do one folder for debugging
    folderPathList = [
        _rootPath + 'cudmore/20230123/Saline',
    ]

    logger.info(f'Running on folderPathList')

    # check all folders exists
    for folderPath in folderPathList:
        if os.path.isdir(folderPath):
            print(f'  ok: folder exists: {folderPath}')
        else:
            print(f'  error: folder does not exist: {folderPath}')
            return

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
        
        filePath = os.path.join(folderPath, file)
        
        oa = oaf.getOligoAnalysis(filePath, loadImages=False)
        
        rgbStackPath = oa._getRgbPath()
        
        # this is our small-rgb stack, it is made from raw czi file
        # forceMake will remake from czi and save -small-rgb
        rgbStack = oa._getRgbStack(forceMake=True)  # np.ndarrray
        
        #logger.info(f'  oligoanalysis rgbStack for cellpose shape is: {rgbStack.shape}')

        # the raw czi file
        # imgPath = os.path.join(folderPath, file)
        
        # here, imgPath is only used to determine where to save
        runModelOnImage(imgPath=rgbStackPath, imgData=rgbStack, setupLogger=False)

        # TODO: unload oligoAnalysis
        oa = None  # does this free memory ?

def saveSlicesForCellPose():
    """Open a 3d rgb and save the 2-channel slices
        Each slice will be rgb 8-bit without histogram normalization
    
        These rgb slices can be opened in cellpose
         - draw rois
         - train
    """
    
    # up until jan 21 2023, this is the training set I was using
    #folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    
    # new jan 2023
    folderPath = '/media/cudmore/data/Dropbox/data/whistler/cudmore/20221010/Morphine'

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
        file = os.path.join(folderPath, file)

        if not os.path.isfile(file):
            logger.error('did not find file: {file}')
            sys.exit(1)

        logger.info('\n')
        logger.info(f'=== {idx+1}/{len(files)} Fetching oligo analysis for file {file}')
        
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
            
            #tifffile.imsave(slicePath, oneSlice)

            masterSliceNumber += 1

if __name__ == '__main__':
    
    # save a folder of czi rgb to slices (to be opened in cellpose gui)
    # saveSlicesForCellPose()
    # sys.exit(1)

    # path = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/FST-analysis/B35_Slice2_RS_DS1.czi/B35_Slice2_RS_DS1-rgb-small.tif'
    # runModelOnImage(imgPath=path)

    # modelList = getModels()
    # for model in modelList:
    #     print(model)

    # logFile = getCellposeLog()
    # print(logFile)

    batchRunFolder0()