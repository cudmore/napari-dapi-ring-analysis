"""
20221031
"""
import os
from pprint import pprint
import json
import enum
from typing import List, Union  # , Callable, Iterator, Optional

import numpy as np
import pandas as pd

import tifffile

#from skimage.transform import resize  # rescale, downscale_local_mean
#from skimage.filters import gaussian
#from skimage.filters import threshold_otsu

from scipy.ndimage import zoom  # to redice x/y size of image
import scipy.ndimage

from aicsimageio import AICSImage

#from oligoanalysis.loadCzi import loadCziHeader  # , loadFolder
from napari_dapi_ring_analysis.loadCzi import _loadHeader
from napari_dapi_ring_analysis._logger import logger
from napari_dapi_ring_analysis import oligoUtils

class imageChannels(enum.Enum):
    dapi = 'dapi'
    cyto = 'cyto'

class oligoAnalysis():
    def __init__(self, path : str, xyScaleFactor : float = 0.25):
        """
        Args:
            path: Full path to raw image (czi file)
            xyScaleFactor: fraction to zoom x/y
                cellpose wants nuclei to be ~10 pixels but our are ~30 pixels
        """
        #logger.info(f'path: {path} xyScaleFactor:{xyScaleFactor}')
        
        if not os.path.isfile(path):
            raise ValueError(f'Did not find raw image file: {path}')
        
        self._path : str = path
        # full path to raw image file (czi file)

        # default header
        # load header from raw image stack (czi)
        self._header : dict = _loadHeader(path)

        christineDict = oligoUtils.parseFileName(path)
        if christineDict is None:
            logger.error(f'DID NOT GET CHRISTINE FILE NAME DICTIONARY')
        else:
            for k,v in christineDict.items():
                self._header[k] = v

        self._header['dapiChannel'] = 1
        self._header['cytoChannel'] = 0

        self._header['dapiMinInt'] = np.nan # assigned in analyzeIntensity
        self._header['dapiMaxInt'] = np.nan
        self._header['cytoMinInt'] = np.nan
        self._header['cytoMaxInt'] = np.nan

        self._header['cellpose'] = ''  # if we have a cell pose _seg.pny file
        self._header['num labels'] = ''  # number of labels if we have a cell pose _seg.pny file
        self._header['xyScaleFactor'] = xyScaleFactor
        #
        self._header['gaussianSigma'] = 1  # can be scalar like 1 or tuple like (z,y,x)
        self._header['cytoOtsuThreshold'] = None
        self._header['cytoStackPixels'] = None
        self._header['cytoMaskPixels'] = None
        self._header['cytoMaskPercent'] = None
        #
        self._header['dapiOtsuThreshold'] = None
        self._header['dapiStackPixels'] = None
        self._header['dapiMaskPixels'] = None
        self._header['dapiMaskPercent'] = None
        #
        self._header['erodeIterations'] = 2
        self._header['dilateIterations'] = 2
        
        self.loadHeader()  # load previously saved, assigns self._header

        # update header if we have a cellpose _seg.npy file
        hasCellPose = os.path.isfile(self._getCellPoseDapiMaskPath())
        if hasCellPose:
            self._header['cellpose'] = 'Yes'
            
        self._dfLabels : pd.DataFrame = self.loadLabelDf()
        # Created in analizeOligoDapi()

        self._rgbStack = None
        # created from raw image on first load
        # used throughout the remaining analysis (and in cellpose)

        self._cellPoseMask = None
        # DAPI mask from cellpose after running a model on _rgbStack

        self._dapiFinalMask = None
        # derived from cellpose DAPI mask after erode/dilate

        self._redImageFiltered = None
        # after gaussina filter
        
        self._redImageMask = None
        # after threshold the gaussian filtered image (_redImageFiltered)

        self._greenImageFiltered = None
        self._greenImageMask = None

        self._isLoaded = False
        # True if raw images have been loaded, see load()

    def setLabelRowAccept(self, rowList : List[int], df : pd.DataFrame):
        """
        
        Notes:
            we get a dataframe with only rows in rowList
                do not use index like iloc, use loc or at
        """
        logger.info(f'rowList:{rowList}')
        logger.info(f'{df}')
        
        acceptValues = df.loc[rowList]['accept'].values
        print(f'  acceptValues: {type(acceptValues)} {acceptValues.shape} "{acceptValues}"')

        for idx, row in enumerate(rowList):
            self._dfLabels.at[row, 'accept'] = acceptValues[idx]

    @property
    def dapiChannel(self):
        return self._header['dapiChannel']
       
    # a setter function
    @dapiChannel.setter
    def dapiChannel(self, channel):
        self._header['dapiChannel'] = channel

    @property
    def cytoChannel(self):
        return self._header['cytoChannel']
       
    # a setter function
    @cytoChannel.setter
    def cytoChannel(self, channel):
        self._header['cytoChannel'] = channel

    def getBaseSaveFile(self) -> str:
        """Get the base save file stub.
        
        This is the original czi without extension + '-rgb-small'.
        We use '-rgb-small' because we are scaling/zooming the raw scope file for cellpose
        
        All saved files should append to this stub.
        """
        saveFile = os.path.split(self._path)[1]
        saveFile, _ext = os.path.splitext(saveFile)
        saveFile += f'-rgb-small'
        baseSavePath = os.path.join(self._getSaveFolder(), saveFile)
        return baseSavePath

    # def getImageFilePath(self, typeStr : str):
    #     filePathStub = self.getBaseSaveFile() # -rgb-small
    #     finalFilePath = ''
    #     if typeStr == 'header':
    #         finalFilePath += f'-header.json'
    #     elif typeStr == 'labelAnalysis':
    #         finalFilePath += f'-labels.csv'
    #     elif typeStr == 'rgb':
    #         finalFilePath += '.tif'
    #     elif typeStr == 'cellpose dapi mask':
    #         finalFilePath += '_seg.npy'
    #     else:
    #         logger.error(f'Did not understand file type: {typeStr}')
    #     return finalFilePath

    def _getRgbPath(self) -> str:
        """Get full path to saved rgb tif.
        """
        rgbSavePath = self.getBaseSaveFile()
        rgbSavePath += '.tif'
        return rgbSavePath

    def _getCellPoseDapiMaskPath(self) -> str:
        cellPoseDapiMaskPath = self.getBaseSaveFile()
        cellPoseDapiMaskPath += '_seg.npy'
        return cellPoseDapiMaskPath

    def isLoaded(self):
        """True if images are loaded. By default the constructor only loads headers.

        Use load() to load images.
        """
        return self._isLoaded
    
    def load(self):
        """Load images.

        If we fail to find saved files, we will perform analysis.

        """

        self._rgbStack = self._getRgbStack()
        """rgb stack we use to run a trained cellpose model on
        """

        self._cellPoseMask = self.getCellPoseMask()
        # Output of cellpose in _seg.npy

        if self._cellPoseMask is not None:
            # need to update the table
            self._header['num labels'] = len(np.unique(self._cellPoseMask))

        # _dict, self._redImageMask = self.makeImageMask()
        self._redImageMask = self.loadImageMask(imageChannels.cyto)
        if self._redImageMask is None:
            self.analyzeImageMask(imageChannels.cyto)

        self._redImageFiltered = self.loadImageFiltered(imageChannels.cyto)
        if self._redImageFiltered is None:
            self.analyzeImageMask(imageChannels.cyto)

        # dec 08, adding simple dapi mask
        self._greenImageMask = self.loadImageMask(imageChannels.dapi)
        if self._greenImageMask is None:
            self.analyzeImageMask(imageChannels.dapi)

        self._greenImageFiltered = self.loadImageFiltered(imageChannels.dapi)
        if self._greenImageFiltered is None:
            self.analyzeImageMask(imageChannels.dapi)

        # analyze with ring
        self._dapiFinalMask = self.loadDapiFinalMask()
        if self._dapiFinalMask is None:
            self._dapiFinalMask = self.analyzeOligoDapi()

        self._isLoaded = True

    def save(self):
        """Save
            - headers
            - red image mask
            - red image filtered
            - dapi ring mask
        """
        logger.info(f'Saving analysis: {self.filename}')
        
        self.saveHeader()
        self.saveLabelDf()

        if self._redImageMask is not None:
            maskPath = self._getImageMaskPath(imageChannels.cyto)
            tifffile.imsave(maskPath, self._redImageMask)

        if self._redImageFiltered is not None:
            filteredPath = self._getImageFilteredPath(imageChannels.cyto)
            tifffile.imsave(filteredPath, self._redImageFiltered)

        self.saveDapiFinalMask()

    @property
    def filename(self) -> str:
        """Get the original filename.
        """
        return os.path.split(self._path)[1]
    
    def getHeader(self):
        """Get the image header.
        
        This includes analysis parameters and results.
        """
        return self._header

    def saveHeader(self):
        """Save image header as json.
        
        This includes analysis parameters and results.
        """
        headerPath = self._getHeaderFilePath()
        logger.info(f'saving header json: {headerPath}')
        with open(headerPath, 'w') as f:
            try:
                json.dump(self._header, f, indent=4)
            except (TypeError) as e:
                logger.error(f'Did not save header')
                logger.error(f'{e}')
                logger.error(f'{headerPath}')
                logger.error(self._header)

    def loadHeader(self):
        """Load image header as json.
        """
        headerPath = self._getHeaderFilePath()
        if not os.path.isfile(headerPath):
            # no header to load
            return

        #logger.info(f'{headerPath}')
        
        # only load keys we already have in self._header
        _loadedHeader = None
        with open(headerPath, 'r') as f:
            try:
                _loadedHeader = json.load(f)
            except (json.decoder.JSONDecodeError) as e:
                logger.error(e)

        if _loadedHeader is None:
            logger.error(f'Loading header failed')
            logger.error(f'headerPath: {headerPath}')
        else:
            for k in self._header.keys():
                try:
                    self._header[k] = _loadedHeader[k]
                except (KeyError) as e:
                    logger.warning(f'Did not find key "{k}" in loaded header')

    def _getHeaderFilePath(self) -> str:
        """Get path to save/load header.
        
        We want to save header when we change analysis params
            - gaussianSigma
            - dilation/erosion iteration
            - ???
        """
        headerFilePath = self.getBaseSaveFile()
        headerFilePath += f'-header.json'
        return headerFilePath

    def _getDapiFinalMaskPath(self) -> str:
        dapiFinalMaskPath = self.getBaseSaveFile()
        dapiFinalMaskPath += '-dapi-final-mask.tif'
        return dapiFinalMaskPath
 
    def loadDapiFinalMask(self) -> np.ndarray:
        """Load _dapiFinalMask, the DAPI ring mask after erode/dilate.

        See: AnalyzeOligoDapi()
        """
        dapiFinalMaskPath = self._getDapiFinalMaskPath()
        
        if not os.path.isfile(dapiFinalMaskPath):
            #logger.info(f'did not find dapi_final_mask: {dapiFinalMaskPath}')
            return
        #logger.info(f'loading dapi_final_mask: {dapiFinalMaskPath}')
        dapiFinalMask = tifffile.imread(dapiFinalMaskPath)
        return dapiFinalMask

    #def saveDapiFinalMask(self, dapi_final_mask : np.ndarray = None):
    def saveDapiFinalMask(self):
        """Save _dapiFinalMask, the DAPI ring mask after erode/dilate.

        See: AnalyzeOligoDapi()
        """
        if self._dapiFinalMask is None:
            return
        dapiFinalMaskPath = self._getDapiFinalMaskPath()
        logger.info(f'saving dapi_final_mask: {dapiFinalMaskPath}')
        tifffile.imsave(dapiFinalMaskPath, self._dapiFinalMask)

    def saveLabelDf(self):
        """Save a csv file where each row is stats for one mask label.
        """
        dfPath = self._getLabelFilePath()
        if self._dfLabels is not None:
            logger.info(f'saving label df: {dfPath}')
            self._dfLabels.to_csv(dfPath, index=False)

    def loadLabelDf(self) -> pd.DataFrame:
        dfPath = self._getLabelFilePath()
        if not os.path.isfile(dfPath):
            return
        #logger.info(f'loading label df: {dfPath}')
        df = pd.read_csv(dfPath)
        return df

    def _getLabelFilePath(self) -> str:
        """Get path to save/load label df (self._dfMaster).
        
        Each row has stats for one label.

        See: analizeOligoDapi()
        """
        dfPath = self.getBaseSaveFile()
        dfPath += f'-labels.csv'
        return dfPath

    def _getSaveFolder(self) -> str:
        """Get the save folder and make if neccessary.
        
        The save folder is <parent folder>/<parent folder>-analysis
        """
        _folder, _file = os.path.split(self._path)
        _, _parentFolder = os.path.split(_folder)
        
        # _saveFolder is shared by all files in parentFolder
        _saveFolder = os.path.join(_folder, _parentFolder + '-analysis')
        if not os.path.isdir(_saveFolder):
            logger.info(f'making analysis save folder:')
            logger.info(f'  {_saveFolder}')
            os.mkdir(_saveFolder)
        
        # each raw tif/czi go into a different folder
        #_cellFolder = os.path.splitext(_file)[0]
        # use full file name with extension for folder, this way folders are uunique files
        _cellFolder = os.path.join(_saveFolder, _file)
        if not os.path.isdir(_cellFolder):
            logger.info(f'making analysis folder for file "{_file}":')
            logger.info(f'  {_cellFolder}')
            os.mkdir(_cellFolder)

        return _cellFolder

    def _getImageMaskPath(self, imageChannel : imageChannels) -> str:
        """Get the full path to an image mask.
        
        This file ends in -mask-{channelStr}.tif

        Args:
            channelStr: in ['red', 'green']
        """
        maskPath = self.getBaseSaveFile()
        maskPath += f'-mask-{imageChannel.value}.tif'
        return maskPath

    def _getImageFilteredPath(self, imageChannel : imageChannels) -> str:
        """Get the full path to a (gaussian) filtered image.
        
        This file ends in -filtered-{channelStr}.tif

        Args:
            channelStr: In ['red', 'green']
        """
        filteredPath = self.getBaseSaveFile()
        filteredPath += f'-filtered-{imageChannel.value}.tif'
        return filteredPath

    def getImageChannel(self, imageChannel : imageChannels) -> np.ndarray:
        """Get an image (color) channel from rgb stack.
        
        Args:
            channelStr: In ['red', 'green']

        Assuming rgb stack has channel order (slice, y, x, channel)
        """
        if imageChannel == imageChannels.cyto:
            return self._rgbStack[:, :, :, self.cytoChannel]  # 0
        if imageChannel == imageChannels.dapi:
            return self._rgbStack[:, :, :, self.dapiChannel]  # 1

    def _getRgbStack(self, forceMake=False) -> np.ndarray:
        """Load or make an rgb stack from raw file.
        
        If rgb tif exists then load, otherwise make and save.
        """
        rgbSavePath = self._getRgbPath()

        # if True then always remake from czi file
        # if False then load what we saved
        #forceMake = False # on flight to sfn2022
        logger.info(f'  forceMake:{forceMake} SFN NOT LOADING, if True then REGENERATING _rgbStack EACH TIME')

        if not forceMake and os.path.isfile(rgbSavePath):
            logger.info(f'  Loading rgb stack: {rgbSavePath}')
            _rgbStack =  tifffile.imread(rgbSavePath)
        else:
            img = AICSImage(self._path)
            imgData = img.get_image_data("ZYXC", T=0)
            # imgData is like: (21, 784, 784, 2)
            logger.info(f'  AICSImage loaded raw imgData: {imgData.shape} {imgData.dtype}')

            # convert to 8 bit, we need to do each channel to maximize histogram
            imgData_ch1 = imgData[:,:,:,0]
            imgData_ch2 = imgData[:,:,:,1]

            # oligoUtils.printStack(imgData_ch1, ' . raw imgData_ch1')
            # oligoUtils.printStack(imgData_ch2, ' . raw imgData_ch2')

            imgData_ch1 = oligoUtils.getEightBit(imgData_ch1, maximizeHistogram=False)
            imgData_ch2 = oligoUtils.getEightBit(imgData_ch2, maximizeHistogram=False)
            
            # oligoUtils.printStack(imgData_ch1, ' . 8-bit imgData_ch1')
            # oligoUtils.printStack(imgData_ch2, ' . 8-bit imgData_ch2')
            
            # make rgb stack, assuming we loaded 'ZYXC'
            _shape = imgData.shape
            _rgbDim = (_shape[0], _shape[1], _shape[2], imgData.shape[3]+1)
            _rgbStack = np.ndarray(_rgbDim, dtype=np.uint8)
            _rgbStack[:,:,:,0] = imgData_ch1
            _rgbStack[:,:,:,1] = imgData_ch2
            _rgbStack[:,:,:,2] = 0

            # for Whistler, we need to make image 1/4 size
            # cellpose want nuclei to be about 10 pixels
            # Whistler data is zoomed in and nuclei are like 30 pixels
            xyScaleFactor = self._header['xyScaleFactor']
            _zoom = (1, xyScaleFactor, xyScaleFactor, 1)
            _rgbStack = zoom(_rgbStack, _zoom)
            oligoUtils.printStack(_rgbStack, f'after zoom by {xyScaleFactor}, _rgbStack')

            # get the min/max of each channel
            # need to cast to int() because np return uint8 which is not json serliazable
            dapiImg = _rgbStack[:, :, :, self.dapiChannel]
            self._header['dapiMinInt'] = int(np.min(dapiImg))
            self._header['dapiMaxInt'] = int(np.max(dapiImg))
            cytoImg = _rgbStack[:, :, :, self.cytoChannel]
            self._header['cytoMinInt'] = int(np.min(cytoImg))
            self._header['cytoMaxInt'] = int(np.max(cytoImg))

            logger.info(f'  saving rgb stack:')
            logger.info(f'    {rgbSavePath}')
            tifffile.imwrite(rgbSavePath, _rgbStack)

        return _rgbStack

    def getCellPoseMask(self) -> np.ndarray:
        """Get the cellpose mask from _seg.npy file.

        This is saved by cellpose outside oligoAnalysis
        """
        cellPoseSegPath = self._getCellPoseDapiMaskPath()
        if os.path.isfile(cellPoseSegPath):
            #self._header['cellpose'] = 'Yes'
            pass
        else:
            logger.warning(f'Did not find cellpose _seg.npy file {os.path.split(cellPoseSegPath)[1]}:')
            logger.warning(f'  You need to run a model in cellpose on the 3d rgb stack.')
            #logger.warning(f'    {cellPoseSegPath}')
            return
        dat = np.load(cellPoseSegPath, allow_pickle=True).item()
        masks = dat['masks']

        return masks

    def getImageMask(self, imageChannel : imageChannels)  -> np.ndarray:
        if imageChannel == imageChannels.cyto:
            return self._redImageMask
        elif imageChannel == imageChannels.dapi:
            return self._greenImageMask

    def getImageFiltered(self, imageChannel)  -> np.ndarray:
        if imageChannel == imageChannels.cyto:
            return self._redImageFiltered
        elif imageChannel == imageChannels.dapi:
            return self._greenImageFiltered

    def loadImageMask(self, imageChannel : imageChannels) -> np.ndarray:
        """Load the filtered thresholded binary mask.

        Args:
            channelStr: In ['red', 'green']

        Created in analyzeImageMask()
        """
        maskPath = self._getImageMaskPath(imageChannel)
        if os.path.isfile(maskPath):
            # load
            #logger.info(f'Loading image mask "{self.filename}" {imageChannel.value} {maskPath}')
            imgData_binary = tifffile.imread(maskPath)
            return imgData_binary

    def loadImageFiltered(self, imageChannel : imageChannels) -> np.ndarray:
        """Load the (gaussian) filtered image.
        
        Args:
            channelStr: In ['red', 'green']

        Created in analyzeImageMask()
        """
        maskPath = self._getImageFilteredPath(imageChannel)
        if os.path.isfile(maskPath):
            # load
            #logger.info(f'Loading image filtered "{self.filename}" {imageChannel.value} {maskPath}')
            imgData_binary = tifffile.imread(maskPath)
            return imgData_binary
        
    def analyzeImageMask(self, imageChannel : imageChannels, gaussianSigma = None):
        """Create a binary image mask for either dapi or cyto
            - Gaussian blur
            - Otsu threshold

        Args:
            channelStr: in ['red', 'green']
        
        Assigns:
            self._redImageMask
        """
        imgData = self.getImageChannel(imageChannel)

        if gaussianSigma is None:
            gaussianSigma = self._header['gaussianSigma']
        
        logger.info(f'{self.filename} imageChannel:{imageChannel.value} _gaussianSigma:{gaussianSigma}')
        
        otsuThreshold, imgData_blurred, imgData_binary = \
            oligoUtils.getOtsuThreshold(imgData, sigma=gaussianSigma)
        
        # calculate pixel stats
        numStackPixels = imgData_binary.size
        numMaskPixels = np.count_nonzero(imgData_binary)
        maskPercent = numMaskPixels / numStackPixels * 100
        
        _chStr = imageChannel.value

        logger.info(f'  -- RESULTS: {_chStr} otsuThreshold:{otsuThreshold} maskPercent:{maskPercent}')

        #self._header['gaussianSigma'] = numStackPixels
        self._header[f'{_chStr}GausSigma'] = gaussianSigma
        self._header[f'{_chStr}OtsuThreshold'] = otsuThreshold
        self._header[f'{_chStr}StackPixels'] = numStackPixels
        self._header[f'{_chStr}MaskPixels'] = numMaskPixels
        self._header[f'{_chStr}MaskPercent'] = maskPercent

        if imageChannel == imageChannel.cyto:
            self._redImageMask = imgData_binary
            self._redImageFiltered = imgData_blurred
        elif imageChannel == imageChannels.dapi:
            # logger.warning(f'not implemented for imageChannel {imageChannel.value}')
            self._greenImageMask = imgData_binary
            self._greenImageFiltered = imgData_blurred

        return imgData_binary, imgData_blurred

    def analyzeOligoDapi(self, dilateIterations : int = None,
                        erodeIterations : int = None):
        """
        For each labeled mask in cell pose dapi mask
            - dilate
            - erode
            - make a ring mask
            - sum pixels in the 'other' channel contained in this ring

        Requires:
            Cellpose dapi mask
            
        Returns:
            dapi_final_mask
        """

        # this is the dapi mask output by cellpose
        # it will not exist if we did not run cllpose on this stack
        logger.info(f'{self.filename}')
        
        _cellPoseDapiMask = self.getCellPoseMask()
        if _cellPoseDapiMask is None:
            logger.warning('Did not perform ring analysis, no cellpose dapi mask')
            return

        if dilateIterations is None:
            dilateIterations = self._header['dilateIterations']
        else:
            self._header['dilateIterations'] = dilateIterations
        if erodeIterations is None:
            erodeIterations = self._header['erodeIterations']
        else:
            self._header['erodeIterations'] = erodeIterations
                
        # TODO: sloppy, we don't always need to save
        #self.saveHeader()

        maskLabelList = np.unique(_cellPoseDapiMask)

        dapi_final_mask = np.zeros_like(_cellPoseDapiMask)  # dapi mask after dilation
        logger.info(f'making dapi_dilated_mask: {dapi_final_mask.shape} {dapi_final_mask.dtype}')

        listOfDict = []  # convert to pandas dataframe at end

        for maskLabel in maskLabelList:
            if maskLabel == 0:
                # background
                continue
            
            _oneMask = _cellPoseDapiMask == maskLabel  # (46, 196, 196)
            #print('_oneMask:', type(_oneMask), _oneMask.shape, _oneMask.dtype)

            # dilate the mask
            if dilateIterations>0:
                _dilatedMask = scipy.ndimage.binary_dilation(_oneMask, iterations=dilateIterations)
            else:
                _dilatedMask = _oneMask

            if erodeIterations>0:
                _erodedMask = scipy.ndimage.binary_erosion(_oneMask, iterations=erodeIterations)
            else:
                _erodedMask = _oneMask

            #print('  dilatedMask:', type(dilatedMask), dilatedMask.shape, dilatedMask.dtype, np.sum(dilatedMask))

            # make a ring
            #dilatedMask = dilatedMask ^ _oneMask
            finalMask = _dilatedMask ^ _erodedMask  # carrot (^) is xor

            # the number of pixels in the dilated/eroded dapi mask
            finalMaskCount = np.count_nonzero(finalMask)

            # oligo red mask pixels in the (dilated/eroded) dapi mask
            redImageMask = np.where(finalMask==True, self._redImageMask, 0)  # 0 is fill value
            #print('  redImageMask:', type(redImageMask), redImageMask.shape, redImageMask.dtype, np.sum(redImageMask))

            # like cellpose_dapi_mask but after dilation
            finalMaskLabel = finalMask.copy().astype(np.int64)
            #print('1 ', dilatedMaskLabel.dtype, np.max(dilatedMaskLabel))
            # +1 so colors are different from cellpose_dapi_mask
            finalMaskLabel[finalMaskLabel>0] = maskLabel + 1   
            #print('  2 ', dilatedMaskLabel.dtype, np.max(dilatedMaskLabel))
            dapi_final_mask = dapi_final_mask + finalMaskLabel
            #print('  dapi_dilated_mask:', dapi_dilated_mask.shape, np.sum(dapi_dilated_mask))
            
            redImageMaskPercent = np.sum(redImageMask) / finalMaskCount * 100
            
            oneDict = {
                'label': maskLabel,
                'finalMaskCount': finalMaskCount,  # num pixels in dilated mask
                'cytoImageMaskSum': np.sum(redImageMask),  # sum of red mask in dilated dapi mask
                'cytoImageMaskPercent': redImageMaskPercent,  # fraction of pixels in red mask in dilated mask
                'accept': '',  # '' indicates False
            }
            listOfDict.append(oneDict)
            
        self._dfLabels = pd.DataFrame(listOfDict)
        
        return dapi_final_mask

def check_OligoAnalysis():
    cziPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/B35_Slice2_RS_DS1.czi'
    oa = oligoAnalysis(cziPath)

    oa.analyzeOligoDapi()

    oa.analyzeOligoDapi()

if __name__ == '__main__':
    #check_OligoAnalysisFolder()

    check_OligoAnalysis()