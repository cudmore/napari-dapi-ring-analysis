"""
"""
import os

import pandas as pd

from napari_dapi_ring_analysis import loadCzi
from napari_dapi_ring_analysis.oligoAnalysis import oligoAnalysis
from napari_dapi_ring_analysis._logger import logger

from napari_dapi_ring_analysis._cellpose import runModelOnImage
from cellpose.io import logger_setup

def old_batchRunFolder(folderPath : str):
    """Run cellpose on an entire folder.
    
    This takes some time but is neccessary to make analysis easier.
    """
    
    logger_setup()  # will clear .cellpose/run.log
    
    oaf = oligoAnalysisFolder(folderPath)
    df = oaf.getDataFrame()
    files = df['file'].tolist()
    for idx, file in enumerate(files):
        logger.info('\n')
        logger.info(f'=== {idx}/{len(files)-1} Fetching oligo analysis for file {file}')
        
        oa = oaf.getOligoAnalysis(file, loadImages=False)
        
        rgbStackPath = oa._getRgbPath()
        rgbStack = oa._getRgbStack()  # np.ndarrray
        
        #logger.info(f'  oligoanalysis rgbStack for cellpose shape is: {rgbStack.shape}')

        # the raw czi file
        # imgPath = os.path.join(folderPath, file)
        
        # here, imgPath is only used to determine where to save
        runModelOnImage(imgPath=rgbStackPath, imgData=rgbStack, setupLogger=False)

        # TODO: unload oligoAnalysis
        oa = None  # does this free memory ?

class oligoAnalysisFolder():

    def __init__(self, folderPath : str = None):
        """
        
        Args:
            folderPath: Full path to raw scope stacks.
        """
        logger.info(f'{folderPath}')
        
        self._folderPath : str = folderPath
        # Full path to raw scope stack

        #logger.info(f'Loading folder: {self._folderPath}')
        self._dfFolder = loadCzi.loadFolder(self._folderPath)
        #self._dfFolder = self._loadAllFileHeader()
        # DataFrame of headers for files in _folderPath

        self._analysisList = {}  #[None] * len(self._dfFolder)
        # dictionary of per file analysis
        # keys are filename, values are oligoAnalysis

        # load oligo analysis headers
        if len(self._dfFolder)==0:
            logger.warning(f'No valid image files in folder: {self._folderPath}')
        else:
            files = self._dfFolder['file'].tolist()
            for file in files:
                #logger.info(f'  loading file header for: {file}')
                filePath = os.path.join(self._folderPath, file)
                self._analysisList[file] = oligoAnalysis(filePath)
            logger.info(f'Loaded {len(files)} oligoAnalysis files.')

    def getDataFrame(self):
        """Get the dataframe of loaded file headers.
        """
        return self._dfFolder
    
    def getAnalysisDataFrame(self, removeColumns=False):
        """Get a DataFrame from all oligo analysis.
        
        Args:
            removeColumns: If True, remove some columns to make more concise
        """
        removeColumnList = ['xPixels', 'yPixels',
            'yVoxel', 'xyScaleFactor', 'oligoStackPixels', 'oligoMaskPixels']
        
        dictList = []
        for k,v in self._analysisList.items():
            oa = v
            oneDict = oa.getHeader()
            dictList.append(oneDict)
        df = pd.DataFrame(dictList)
        
        if removeColumns:
            for _col in removeColumnList:
                df = df.drop(_col, axis=1)

        # logger.info('')
        # print('  got df:')
        # print(df)
        
        return df


    def getRow(self, row : int) -> dict:
        """Get one row as dict.
        """
        df = self._dfFolder.loc[row]
        return df.to_dict()
    
    def getOligoAnalysis(self, file : str, loadImages = True):
        """Given a raw file name, return the oligoAnalysis.
        
        Make if necc.

        Args:
            file:
            loadImages:
        """
        #logger.info(f'file:{file}')
        if file in self._analysisList.keys():
            oa = self._analysisList[file]
            if loadImages and not oa.isLoaded():
                oa.load()
            #logger.info(f'  returning: {oa}')
            return oa
        # else:
        #     # NOT TAKEN
        #     filePath = os.path.join(self._folderPath, file)
        #     #try:
        #     if 1:
        #         print(f'  creating oligo analysis for filePath: {filePath}')
        #         oneAnalysis = oligoAnalysis(filePath)
        #         print('    oneAnalysis:', oneAnalysis)
        #         self._analysisList[file] = oneAnalysis
        #         return self._analysisList[file]
        #     # except (ValueError) as e:
        #     #     logger.error(e)

    def old_loadAllFileHeader(self):
        """Load all file headers in folder.
        """
        #logger.info(f'Loading folder: {self._folderPath}')
        df = loadCzi.loadFolder(self._folderPath)
        return df

def check_OligoAnalysisFolder():
    folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'

    oaf = oligoAnalysisFolder(folderPath)
    print('oaf._dfFolder')
    print(oaf._dfFolder)

    oa = oaf.getOligoAnalysis('')

if __name__ == '__main__':
    #check_OligoAnalysisFolder()
    
    pass