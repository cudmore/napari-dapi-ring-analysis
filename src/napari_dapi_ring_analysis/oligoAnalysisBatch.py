import os
import sys
import pandas as pd
import numpy as np

import napari_dapi_ring_analysis as dra
from napari_dapi_ring_analysis._logger import logger

def batchMakeAnalysis(folderPathList, cytoSigma: float = 0.7):
    """Step through all data in a list of folders.
    """
    dfMaster = pd.DataFrame()

    for folderPath in folderPathList:
        
        print('== processing folderPath:', folderPath)
        
        oaf = dra.oligoAnalysisFolder(folderPath)

        dfFolder = oaf.getDataFrame()
        if len(dfFolder) == 0:
            logger.error(f'Did not find image files for folder: {folderPath}')
            continue

        #print(dfFolder)

        files = dfFolder['file'].values
        # dictList = []
        for _fileIdx, file in enumerate(files):
            
            # full path to file
            file = os.path.join(folderPath, file)
            
            print(f'    === file {_fileIdx+1} of {len(files)}')
            print(f'    === file {file}')

            # files = dfFolder['']
            oa = oaf.getOligoAnalysis(file)

            # run aics segmentation (fills in aics % in header)
            oa.aicsAnalysis()

            # grab cellpose mask and count number of labels
            _cellPoseMask = oa.getCellPoseMask()
            if _cellPoseMask is not None:
                # need to update the table
                oa._header['num labels'] = len(np.unique(_cellPoseMask))
            else:
                oa._header['num labels'] = float('nan')

            dapiImg = oa.getImageChannel(dra.imageChannels.dapi, rawCzi=True)
            # dapiMin = np.min(dapiImg)
            # dapiMax = np.max(dapiImg)
            # dapiRange = dapiMax - dapiMin

            # bring cyto gaussian down to 0.7
            cytoImg = oa.getImageChannel(dra.imageChannels.cyto, rawCzi=True)
            # cytoMin = np.min(cytoImg)
            # cytoMax = np.max(cytoImg)
            # cytoRange = cytoMax - cytoMin

            # these are assigned in oa when we create small-3d-rgb (need to add function)
            oa._header['dapiMinInt'] = int(np.min(dapiImg))
            oa._header['dapiMaxInt'] = int(np.max(dapiImg))

            oa._header['cytoMinInt'] = int(np.min(cytoImg))
            oa._header['cytoMaxInt'] = int(np.max(cytoImg))

            # when oligo analysis is loaded  (by oligo analysis folder)
            # it auto make masks with gaussianSigma=1
            oa.analyzeImageMask(dra.imageChannels.cyto, gaussianSigma=cytoSigma)
            oa.analyzeImageMask(dra.imageChannels.dapi, gaussianSigma=3)

            oa._header['cytoDapiRatio'] = oa._header['cytoMaskPercent'] / oa._header['dapiMaskPercent']

            # unload raw data
            oa.unloadRawData()

        _dfFolder = oaf.getAnalysisDataFrame()
        
        # Christine analysis
        # make a new column with ration of percent cyto/dapi
        # logger.info('MAKING cytoDapiRatio !!!! FROM 12/13/22 with Christine')
        # _dfFolder['cytoDapiRatio'] = _dfFolder['cytoMaskPercent'] / _dfFolder['dapiMaskPercent']

        dfMaster = pd.concat([dfMaster, _dfFolder])
        
        # save to one csv
        # savePath = '/Users/cudmore/Dropbox/data/whistler/cudmore/oligo-simmary-20221214-v2.csv'
        # savePath = '/Users/cudmore/Dropbox/data/whistler/cudmore/oligo-simmary-20230111-saline.csv'
        #savePath = f'/Users/cudmore/Dropbox/data/whistler/cudmore/oligo-simmary-20230112-cs-{cytoSigma}.csv'
        
        # adding new aics analysis
        # savePath = f'/media/cudmore/data/Dropbox/data/whistler/cudmore/oligo-summary-20230121-cs-{cytoSigma}-v3.csv'

        savePath = f'/media/cudmore/data/Dropbox/data/whistler/cudmore/oligo-summary-20230123-Saline-{cytoSigma}-v3.csv'

        
        logger.info(f'saving to: {savePath}')
        dfMaster.to_csv(savePath)


if __name__ == '__main__':
    # import sys
    # testParseFileName()
    # sys.exit(1)
    
    # NEED TO RUN _cellpose.batchRunFolder0() FIRST !!!!!

    _rootPath = '/media/cudmore/data/Dropbox/data/whistler/cudmore/'

    folderPathList = [
        _rootPath + '20221010/FST',
        _rootPath + '20221010/Morphine',

        _rootPath + '20221031/FST',
        _rootPath + '20221031/Morphine',

        _rootPath + '20221109/Adolescent',
        _rootPath + '20221109/Saline',

        _rootPath + '20221216/Saline',

        _rootPath + '20230123/Saline',

        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221010/FST',
        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221010/Morphine',

        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221031/FST',
        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221031/Morphine',

        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221109/Adolescent',
        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221109/Saline',

        # '/Users/cudmore/Dropbox/data/whistler/cudmore/20221216/Saline'

    ]

    folderPathList = [
        _rootPath + '20230123/Saline',
    ]

    # folderPathList = [
    #     '/Users/cudmore/Dropbox/data/whistler/cudmore/20221010/FST',
    # ]
    # folderPathList = [
    #     '/Users/cudmore/Dropbox/data/whistler/cudmore/20221216/Saline',
    # ]

    # batchMakeAnalysis(folderPathList, cytoSigma = 0.4)
    batchMakeAnalysis(folderPathList, cytoSigma = 0.7)
    # batchMakeAnalysis(folderPathList, cytoSigma = 1.0)
    