"""
20221101
"""
import os
import time
from typing import List, Union  # , Callable, Iterator, Optional
from functools import partial

import numpy as np
import pandas as pd

#from skimage.measure import regionprops, regionprops_table
import skimage.measure

from qtpy import QtWidgets, QtCore, QtGui

import qdarkstyle

import napari
import napari_layer_table  # our custom plugin (installed from source)

#import magicgui.widgets

import napari_dapi_ring_analysis

import napari_dapi_ring_analysis.oligoUtils
from napari_dapi_ring_analysis import oligoAnalysis
from napari_dapi_ring_analysis import oligoAnalysisFolder
from napari_dapi_ring_analysis import imageChannels

from napari_dapi_ring_analysis.interface import myTableView
from napari_dapi_ring_analysis.interface._data_model import pandasModel

from napari_dapi_ring_analysis.interface import bHistogramWidget

from napari_dapi_ring_analysis._logger import logger

class oligoInterface(QtWidgets.QWidget):

    signalSelectImageLayer = QtCore.Signal(object, object, object, object)
    """Emit when user changes to image layer in napari viewer.
    
    Args:
        data (np.ndarray) image data
        name (str) name of the layer
        colorMapName (Str) name of color map, like 'red' or 'green'
    """

    signalSetSlice = QtCore.Signal(object)
    """Emit when user changes slice slider in napari viewer.
    
    Args:
        sliceNumber (int)
    """

    def __init__(self, viewer : napari.Viewer, folderPath : str = None, parent = None):
        """
        Args:
            viewer:
            folderPath:
        """
        super().__init__(parent)
        self._viewer = viewer
        
        # self._folderPath = folderPath
        self._folderPath : str = None

        self._oligoAnalysisFolder : oligoAnalysisFolder = None
        # if os.path.isdir(folderPath):
        #     self._oligoAnalysisFolder = oligoAnalysisFolder(folderPath)

        self._layerTableDocWidget = None
        
        self._selectedFile : str = None
        self._selectedRow : int = None
        # name of the selected file

        self._buildGui()
        #self.refreshAnalysisTable()

        self._buildingNapari = False
        # to pause updates, set True when adding/removing viewer layers

        # respond to viewer switching layer
        self._viewer.layers.selection.events.changed.connect(self.slot_selectLayer)

        # respond to changes in viewer image slice
        self._viewer.dims.events.current_step.connect(self.slot_setSlice)
        
        #self.openOligoAnalysisPlugin()

        self._ltp = None

        self.switchFolder(folderPath)

        self.updateStatus('Ready')

    def slot_selectFromPlot(self, d : dict):
        """Whebn user selects point in scatter plot, select in file list and show in napari.
        """
        logger.info(f'find row matching {d["path"]}')
        logger.info(f'  only for d["dataType"]=="All Spikes" ')
        if d['dataType'] != 'All Spikes':
            return
        df = self._oligoAnalysisFolder.getDataFrame()
        # print(df['path'])

        _path = d['path']
        _row = df.index[df['path'] == _path]

        if len(_row) == 0:
            return
        
        rowIdx = _row[0]

        logger.info(f'selecting row: {rowIdx}')
        
        self._analysisTable.selectRow(rowIdx)

    def switchFolder(self, folderPath : str):
        
        if folderPath is None or not os.path.isdir(folderPath):
            #raise ValueError(f'Did not find folder: {folderPath}')
            logger.error(f'bad folderPath: {folderPath}')
            return

        logger.info(f'{folderPath}')
        
        self._folderPath : str = folderPath
        
        self._oligoAnalysisFolder = oligoAnalysisFolder(folderPath)

        self._selectedFile : str = None
        self._selectedRow : int = None

        # this is a full refresh of table
        if self._oligoAnalysisFolder is not None:
            dfAnalysis = self._oligoAnalysisFolder.getAnalysisDataFrame()
            myModel = pandasModel(dfAnalysis)
            self._analysisTable.mySetModel(myModel)

            # hide a number of columns in tableview
            # don't hide dapiMaxInt as it tells us when cellpose goes wrong!
            hideColumns = ['date', 'time',
                    'xPixels', 'yPixels', 'xVoxel', 'yVoxel', 'zVoxel',
                    'dapiChannel', 'cytoChannel',
                    'xyScaleFactor',
                    'cytoStackPixels', 'cytoMaskPixels',
                    'dapiMinInt',
                    'cytoMinInt',
                    'dapiOtsuThreshold', 'dapiStackPixels', 'dapiMaskPixels', 'dapiMaskPercent',
                    #'badcolumntest'
                    'sliceNumber', 'imageNumber']
            for hideColumn in hideColumns:
                self._analysisTable.mySetColumnHidden(hideColumn)

            #self.refreshAnalysisTable()
            self.setWindowTitle(self._folderPath)

    def slot_setSlice(self, event):
        """Respond to change in image slice slider in viewer.
        """
        if self._buildingNapari:
            return
        logger.info(f'event.type: {event.type}')
        #logger.info(f'event: {type(event)}')  # napari.utils.events.event.Event
        logger.info(f'  self._viewer.dims.current_step:{self._viewer.dims.current_step}')

        # query the global viewer (I don't like this)
        current_step_tuple = self._viewer.dims.current_step  # return tuple (slice, ?, ?)
        currentSlice = current_step_tuple[0]
        self.signalSetSlice.emit(currentSlice)

    def slot_selectLayer(self, event):
        """Respond to change in layer selection in viewer.
        
        Args:
            event (napari.utils.events.event.Event): event.type == 'changed'

        Notes:
            We receive this event multiple times, we want all info in `event`
                but not sure how to query it?
            For now, we are using the global self._viewer
        """
        if self._buildingNapari:
            return

        # _activeLayer will sometimes be None
        _activeLayer = self._viewer.layers.selection.active
        if _activeLayer is None:
            return
        # napari.layers.image.image.Image
        if isinstance(_activeLayer, napari.layers.image.image.Image):
            # logger.info(f'event.type: {event.type}')
            # print('  ', type(event))
            # print('  _activeLayer:', _activeLayer)
            # print('  _activeLayer:', type(_activeLayer))
            
            _name = _activeLayer.name
            _data = _activeLayer.data
            _colorMapName = _activeLayer.colormap.name
            _contrast_limits = _activeLayer.contrast_limits

            _ndim = _activeLayer.ndim
            _rgb = _activeLayer.rgb

            # napari.utils.Colormap: colormap
            #print(_activeLayer.colormap)  # 2d array of [r,g,b,a]
            logger.info(f'  _activeLayer.name:{_name}')
            logger.info(f'  _activeLayer.ndim:{_ndim}')
            logger.info(f'  _activeLayer.data.shape:{_data.shape}')
            logger.info(f'  _activeLayer.rgb:{_rgb}')  # last dimension of the data has length 3 or 4
            logger.info(f'  _activeLayer.colormap.name:{_activeLayer.colormap.name}')

            # TODO: when our hist signals contrast slider change,
            #   change layer.events.contrast_limits
            
            # want something like this
            #_activeLayer.events.contrast_limits.connect(self._bHistogramWidget.slot_setContrast)
            # this for now
            # _activeLayer.events.contrast_limits.connect(self.slot_setContrast)
            
            # does not work
            # self._bHistogramWidget.signal_contrast_limits.connect(_activeLayer.events.contrast_limits)

            logger.info(f'  -->> emit signalSelectImageLayer _data.shape {_data.shape} _name:{_name}')
            self.signalSelectImageLayer.emit(_data,
                                            _name,
                                            _colorMapName,
                                            #_activeLayer,
                                            _contrast_limits)

            # todo: set the hist signal signalContrastChange
            # to set the contrast of napari layer _activeLayer

    def slot_setContrast(self, event : napari.utils.events.event.Event):
        """Received when napari contrast slider is adjusted.
        """
        logger.info(f'{type(event)} {event.type}')
        
        # _dir = dir(event)
        # for one in _dir:
        #     print(one)
        _activeLayer = self._viewer.layers.selection.active
        contrast_limits = _activeLayer.contrast_limits
        print('  contrast_limits:', contrast_limits)

    def _buildTableView(self):
        #  table/list view
        _myTableView = myTableView()
        
        # TODO (Cudmore) Figure out how to set font of (cell, row/vert header, col/horz header)
        #   and reduce row size to match font
        _fontSize = 11
        _myTableView.setFontSize(_fontSize)
        _myTableView.signalSelectionChanged.connect(self.on_table_selection)

        # this is a full refresh of table
        if self._oligoAnalysisFolder is not None:
            dfAnalysis = self._oligoAnalysisFolder.getAnalysisDataFrame()
            myModel = pandasModel(dfAnalysis)
            _myTableView.mySetModel(myModel)

        return _myTableView

    def _buildGui(self):
        _alignLeft = QtCore.Qt.AlignLeft

        vLayout = QtWidgets.QVBoxLayout()

        # top row of controls
        hLayout = QtWidgets.QHBoxLayout()

        aButton = QtWidgets.QPushButton('Load Folder')
        aButton.clicked.connect(self.on_load_folder_button)
        hLayout.addWidget(aButton, alignment=_alignLeft)

        # checkboxes to toggle interface
        aCheckbox = QtWidgets.QCheckBox('Histogram')
        aCheckbox.setChecked(False)
        aCheckbox.stateChanged.connect(self.on_histogram_checkbox)
        hLayout.addWidget(aCheckbox, alignment=_alignLeft)

        aCheckbox = QtWidgets.QCheckBox('Points')
        aCheckbox.setChecked(True)
        aCheckbox.stateChanged.connect(self.on_points_checkbox)
        hLayout.addWidget(aCheckbox, alignment=_alignLeft)

        # 3x different napari plots
        aLabel = QtWidgets.QLabel('Napari')
        hLayout.addWidget(aLabel, alignment=_alignLeft)

        aButton = QtWidgets.QPushButton('Full')
        aButton.clicked.connect(partial(self.on_napari_full_button, 'Full'))
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aButton = QtWidgets.QPushButton('Dapi')
        aButton.clicked.connect(partial(self.on_napari_full_button, 'Dapi'))
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aButton = QtWidgets.QPushButton('Cyto')
        aButton.clicked.connect(partial(self.on_napari_full_button, 'Cyto'))
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aButton = QtWidgets.QPushButton('AICS')
        aButton.clicked.connect(partial(self.on_napari_full_button, 'AICS'))
        hLayout.addWidget(aButton, alignment=_alignLeft)

        hLayout.addStretch()  # required for alignment=_alignLeft 
        vLayout.addLayout(hLayout)

        # table of results, update this as we analyze
        #dfAnalysis = self._oligoAnalysisFolder.getAnalysisDataFrame(removeColumns=True)
        # self._analysisTable = magicgui.widgets.Table(dfAnalysis)
        # self._analysisTable.read_only = True
        # self._analysisTable.native.itemClicked.connect(self.on_table_selection)
        # self._aTable.native: magicgui.backends._qtpy.widgets._QTableExtended
        # vLayout.addWidget(self._analysisTable.native)
        self._analysisTable = self._buildTableView()
        vLayout.addWidget(self._analysisTable)

        # table of files
        # self._aTable = magicgui.widgets.Table(self._oligoAnalysisFolder.getDataFrame())
        # self._aTable.read_only = True
        # self._aTable.native.itemClicked.connect(self.on_table_selection)
        # # self._aTable.native: magicgui.backends._qtpy.widgets._QTableExtended
        # vLayout.addWidget(self._aTable.native)

        # one row with save and filename
        hLayout = QtWidgets.QHBoxLayout()

        aButton = QtWidgets.QPushButton('Save Analysis')
        aButton.clicked.connect(self.on_save_button)
        hLayout.addWidget(aButton, alignment=_alignLeft)

        self._selectedFilleLabel = QtWidgets.QLabel('file:')
        hLayout.addWidget(self._selectedFilleLabel, alignment=_alignLeft)

        hLayout.addStretch()  # required for alignment=_alignLeft 
        vLayout.addLayout(hLayout)

        # red mask
        hLayout = QtWidgets.QHBoxLayout()

        aButton = QtWidgets.QPushButton('Make Cyto Mask')
        aButton.setToolTip('Make a binary mask from the "cyto" channel')
        aButton.clicked.connect(self.on_make_red_mask)
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aButton = QtWidgets.QPushButton('Make DAPI Mask')
        aButton.setToolTip('Make a binary mask from the "DAPI" channel')
        aButton.clicked.connect(self.on_make_green_mask)
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aLabel = QtWidgets.QLabel('Gaussian Sigma')
        hLayout.addWidget(aLabel)
        self._sigmaLineEditWidget = QtWidgets.QLineEdit('1')
        self._sigmaLineEditWidget.setToolTip('Either a single number of a list of z,y,x')
        self._sigmaLineEditWidget.editingFinished.connect(self.on_edit_sigma)
        hLayout.addWidget(self._sigmaLineEditWidget, alignment=_alignLeft)

        hLayout.addStretch()  # required for alignment=_alignLeft 
        vLayout.addLayout(hLayout)

        # ring mask
        hLayout = QtWidgets.QHBoxLayout()
        aButton = QtWidgets.QPushButton('Make DAPI Ring Mask')
        aButton.setToolTip('Make and analyze a DAPI ring mask')
        aButton.clicked.connect(self.on_make_ring_mask)
        hLayout.addWidget(aButton, alignment=_alignLeft)

        aLabel = QtWidgets.QLabel('Erode')
        hLayout.addWidget(aLabel, alignment=_alignLeft)
        self._erodeSpinBox = QtWidgets.QSpinBox()
        self._erodeSpinBox.setMinimum(0)
        self._erodeSpinBox.setValue(2)
        # self._erodeSpinBox.valueChanged.connect(self.on_edit_erode_dilate)
        hLayout.addWidget(self._erodeSpinBox, alignment=_alignLeft)

        aLabel = QtWidgets.QLabel('Dilate')
        hLayout.addWidget(aLabel, alignment=_alignLeft)
        self._dilateSpinBox = QtWidgets.QSpinBox()
        self._dilateSpinBox.setMinimum(0)
        self._dilateSpinBox.setValue(2)
        # self._dilateSpinBox.valueChanged.connect(self.on_edit_erode_dilate)
        hLayout.addWidget(self._dilateSpinBox, alignment=_alignLeft)

        # aButton = QtWidgets.QPushButton('Run Model')
        # aButton.setToolTip('Run pre-made model on 3D RGB stack')
        # aButton.clicked.connect(self.on_run_model)
        # hLayout.addWidget(aButton, alignment=_alignLeft)

        hLayout.addStretch()  # required for alignment=_alignLeft 
        vLayout.addLayout(hLayout)

        #
        self._statusWidget = QtWidgets.QLabel('Status')
        vLayout.addWidget(self._statusWidget)

        # need pointer to set _imgData on switching to an image layer
        logger.warning('turn histogram back on after debugging a bit !!!!')
        self._bHistogramWidget = None
        '''
        _empty = np.zeros((1,1,1))
        self._bHistogramWidget = bHistogramWidget(_empty)
        self._bHistogramWidget.setVisible(False)
        self.signalSelectImageLayer.connect(self._bHistogramWidget.slot_setData)
        self.signalSetSlice.connect(self._bHistogramWidget.slot_setSlice)
        vLayout.addWidget(self._bHistogramWidget)
        '''

        #
        self.setLayout(vLayout)

    def updateStatus(self, text : str):
        text = f'Status: {text}'
        self._statusWidget.setText(text)

    def refreshAnalysisTable(self):
        
        logger.info('')
        
        dfAnalysis = self._oligoAnalysisFolder.getAnalysisDataFrame()

        rowList = [self._selectedRow]
        
        # reduce to just one row
        df = dfAnalysis[dfAnalysis['path']==self._selectedFile]

        if len(df) == 0:
            logger.error(f'did not find path in path column of oligoAnalysisFolder:')
            logger.error(f'  {self._selectedFile}')
            print(dfAnalysis['path'].head())
            return

        # print('df gaussianSigma:')
        # print(df['gaussianSigma'])
        # print(df)

        # update the table view
        self._analysisTable.myModel.mySetRow(rowList, df)

        # this is a full refresh of table
        # myModel = pandasModel(dfAnalysis)
        # self._analysisTable.mySetModel(myModel)

    def on_run_model(self):
        """Run cellpose model on image.
        """
        oa = self.getSelectedAnalysis()
        if oa is None:
            return
        rgbPath = oa._getRgbPath()
        oligoanalysis.runModelOnImage(rgbPath)

    def on_histogram_checkbox(self, state):
        logger.info(f'state:{state}')
        checked = state > 0
        if self._bHistogramWidget is not None:
            self._bHistogramWidget.setVisible(checked)

    def on_points_checkbox(self, state):
        """Toggle napari viewer layer-table-plugin.
        """
        logger.info(f'state:{state}')
        checked = state > 0
        if self._layerTableDocWidget is not None:
            self._layerTableDocWidget.setVisible(checked)

    def on_napari_full_button(self, name):
        # take current file selection and switch to full napari view
        if self._selectedFile is None:
            return

        # get selected oa
        oa = self._oligoAnalysisFolder.getOligoAnalysis(self._selectedFile)

        if name == 'Full':
            self.clearViewer()  # remove all layers
            self.displayOligoAnalysis_napari(oa)
        elif name == 'Dapi':
            self.clearViewer()  # remove all layers
            self.displayChannel_napari(oa, imageChannels.dapi)
        elif name == 'Cyto':
            self.clearViewer()  # remove all layers
            self.displayChannel_napari(oa, imageChannels.cyto)
        elif name == 'AICS':
            self.clearViewer()  # remove all layers
            self.displayAicsSegmentation_napari(oa)

        else:
            logger.info(f'Button "{name}" not understood')

    def on_load_folder_button(self):

        folderpath = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Folder')

        logger.info(f'User selected folder: {folderpath}')    
        if folderpath:
            self.switchFolder(folderpath)

    def on_save_button(self):
        logger.info('')
        oa = self.getSelectedAnalysis()
        if oa is None:
            return
        oa.save()

        self.updateStatus(f'Saved analysis for file {oa.filename}')

    def on_edit_sigma(self):
        """Edit the gaussian sigma.
        
        This has two cases
            1) scalar like 1 to apply to all image dimension dimensions
            2) tuple like (1, .5, .5) to specify sigma per image dimension

        Returns:
            Either a float or a tuple. Will return NOne if text is invalid.
        """
        # get the current string
        text = self._sigmaLineEditWidget.text()
        logger.info(f'sigma text: {text}')
        
        if ',' in text:
            # tuple
            #value = tuple(text)
            try:
                text = text.replace('(', '')
                text = text.replace(')', '')
                text = text.replace('[', '')
                text = text.replace(']', '')
                value = [float(x) for x in text.split(',')]
                #value = tuple(value)
                value = list(value)
            except (ValueError) as e:
                errStr = 'Please enter a number or a list of numbers like (z, y, x)'
                self.updateStatus(errStr)
                logger.error(errStr)
                self._sigmaLineEditWidget.setText('1,1,1')
                return
        else:
            # int
            value = float(text)
        logger.info(f'  gaussian sigma is now: {type(value)} {value}')
        
        if isinstance(value,list):
            if len(value) != 3:
                errStr = 'Please enter a list of 3 numbers (z, y, x)'
                self.updateStatus(errStr)
                logger.error(errStr)
                self._sigmaLineEditWidget.setText('1,1,1')
                return

        return value

    def on_make_red_mask(self):
        """Remake red mask using xxx as parameter.
        """  
        logger.info('')

        # filename = self._selectedFile
        # if filename is None:
        #     return
        # oa = self._oligoAnalysisFolder.getOligoAnalysis(filename)

        oa = self.getSelectedAnalysis()
        if oa is None:
            return

        # need to set sigma in oa._header['gaussianSigma']
        _gaussianSigma = self.on_edit_sigma()
        if _gaussianSigma is None:
            # we got a bad value, expecting a scalar or a list/tuple of (z, y, x)
            return
        oa._header['gaussianSigma'] = _gaussianSigma

        # refresh interface
        logger.info(f'fetching new red mask with sigma: {_gaussianSigma}')

        _redImageMask, _redImageFiltered = oa.analyzeImageMask(imageChannels.cyto)
        self._redbinaryLayer.data = _redImageMask  # oa.getImageMask('red')
        self._redFilteredLayer.data = _redImageFiltered  # oa.getImageMask('red')

        self.refreshAnalysisTable()

        self.updateStatus('Made Cyto mask after gaussian filter and otsu threshold')

    def on_make_green_mask(self):
        """Remake green mask using xxx as parameter.
        """  
        logger.info('')

        # filename = self._selectedFile
        # if filename is None:
        #     return
        # oa = self._oligoAnalysisFolder.getOligoAnalysis(filename)

        oa = self.getSelectedAnalysis()
        if oa is None:
            return

        # need to set sigma in oa._header['gaussianSigma']
        _gaussianSigma = self.on_edit_sigma()
        if _gaussianSigma is None:
            # we got a bad value, expecting a scalar or a list/tuple of (z, y, x)
            return
        oa._header['gaussianSigma'] = _gaussianSigma

        # refresh interface
        logger.info(f'fetching new green mask with sigma: {_gaussianSigma}')

        _greenImageMask, _greenImageFiltered = oa.analyzeImageMask(imageChannels.dapi)
        self._greenbinaryLayer.data = _greenImageMask  # oa.getImageMask('red')
        self._greenFilteredLayer.data = _greenImageFiltered  # oa.getImageMask('red')

        self.refreshAnalysisTable()

        self.updateStatus('Made DAPI mask after gaussian filter and otsu threshold')

    def on_make_ring_mask(self, value):
        erodeIterations = self._erodeSpinBox.value()
        dilateIterations = self._dilateSpinBox.value()

        logger.info('')

        # filename = self._selectedFile
        # if filename is None:
        #     return
        # oa = self._oligoAnalysisFolder.getOligoAnalysis(filename)

        oa = self.getSelectedAnalysis()
        if oa is None:
            return

        # need to set sigma in oa._header['gaussianSigma']
        # oa._header['erodeIterations'] = erodeIterations
        # oa._header['dilateIterations'] = dilateIterations

        _dapiFinalMask = oa.analyzeOligoDapi(dilateIterations=dilateIterations,
                                        erodeIterations=erodeIterations)
        if _dapiFinalMask is None:
            # happend when there is no cellpose mask from _seg.npy file
            statusStr = f'Did not perform ring analysis, no cellpose dapi mask for file {oa.filename}'
            self.updateStatus(statusStr)
            return
        
        oa._dapiFinalMask = _dapiFinalMask

        # refresh interface
        self.refreshAnalysisTable()
        self.dapiFinalMask_layer.data = _dapiFinalMask

        # TODO: refresh napari-layer-table
        self._ltp.getTableView().mySetModel_from_df(oa._dfLabels)

        self.updateStatus('Made ring mask from cellpose DAPI mask')

    def on_table_selection(self, rowList : List[int], isAlt : bool = False):
        """Respond to user selection in table (myTableView).
        
        This is called when user selects a row(s) in underlying myTableView.

        Args:
            rowList: List of rows that were selected
            isAlt: True if keyboard Alt is down
        """

        logger.info(f'rowList:{rowList} isAlt:{isAlt}')

        oneRow = rowList[0]
        rowDict = self._oligoAnalysisFolder.getRow(oneRow)
        
        # print('  selected row dict is:')
        # print(rowDict)

        filename = rowDict['path']
        self.switchFile(filename, oneRow)

        # sfn
        self.refreshAnalysisTable()

    def getSelectedAnalysis(self):
        """Get the selected oligoAnalysis.
        """
        if self._selectedFile is None:
            return
        oa = self._oligoAnalysisFolder.getOligoAnalysis(self._selectedFile)
        return oa

    def switchFile(self, filepath : str, row : int):
        """load oa and display in napari

        Args:
            filename:
            row:
        """
        filepath = os.path.join(self._folderPath, filepath)

        _folder, _filename = os.path.split(filepath)

        logger.info(f'filename:{_filename}')

        if filepath == self._selectedFile:
            logger.info(f'  file is already selected: {self._selectedFile}')
            return
        
        self._selectedRow = row
        self._selectedFile = filepath

        self._viewer.title = filepath
                
        # get selected oa
        oa = self._oligoAnalysisFolder.getOligoAnalysis(filepath)

        # complete refresh of napari viewer
        self.clearViewer()  # remove all layers

        # jan 2023
        #self.displayCyto_napari(oa, imageChannels.cyto)
        #self.displayCyto_napari(oa, imageChannels.dapi)
        
        # jan 2023, was this
        self.displayOligoAnalysis_napari(oa)
        # logger.info('REMEMBER, defaulting to cyto view')
        # self.displayChannel_napari(oa, imageChannels.cyto)

        # set gaussian sigma
        _gaussianSigma = oa._header['gaussianSigma']
        _gaussianSigma = str(_gaussianSigma)
        self._sigmaLineEditWidget.setText(_gaussianSigma)
        
        # set dilate/erode
        self._dilateSpinBox.setValue(oa._header['dilateIterations'])
        self._erodeSpinBox.setValue(oa._header['erodeIterations'])

        # set analysis table
        # xxx

        self._selectedFilleLabel.setText(_filename)

    def clearViewer(self):
        """Remove all layers from the napari viewer.
        """
        self._viewer.layers.clear()
        if self._layerTableDocWidget is not None:
            self.closeLayerTablePlugin()

    def openLayerTablePugin(self, layer):
        """Open a layer table plugin with specified layer.
        
        Args:
            layer: napari points layer

        Returns:
            napari._qt.widgets.qt_viewer_dock_widget.QtViewerDockWidget
        """
        onAddCallback = None
        self._ltp = napari_layer_table.LayerTablePlugin(self._viewer, oneLayer=layer, onAddCallback=onAddCallback)
        
        logger.warning('TURN THIS BACK ON')
        logger.warning('  self._ltp.myTable2.signalEditingRows.connect(self.slot_editingRows)')
        #self._ltp.myTable2.signalEditingRows.connect(self.slot_editingRows)
        #ltp.signalDataChanged.connect(on_user_edit_points2)
        
        # show
        area = 'right'
        name = layer.name
        
        # napari._qt.widgets.qt_viewer_dock_widget.QtViewerDockWidget
        _layerTableDocWidget = self._viewer.window.add_dock_widget(self._ltp, area=area, name=name)
        
        # see: https://forum.image.sc/t/can-i-remove-the-close-icon-when-i-create-a-dock-widget-in-the-viewer-with-add-dock-widget/67369/3
        _layerTableDocWidget._close_btn = False

        return _layerTableDocWidget

    def slot_editingRows(self, rowList : List[int], df : pd.DataFrame):
        logger.info(f'rowList:{rowList}')
        #logger.info(f'{df}')

        oa = self.getSelectedAnalysis()
        if oa is None:
            return
        oa.setLabelRowAccept(rowList, df)

    def openOligoAnalysisPlugin(self):
        """Embed oligo analysis into napari viewer.
        
        I do not like this, takes up too much room.
        """
        area = 'bottom'
        name = 'Oligo Analysis'
        _docWidget = viewer.window.add_dock_widget(self, area=area, name=name)
        return _docWidget

    def closeLayerTablePlugin(self):
        self._viewer.window.remove_dock_widget(self._layerTableDocWidget) 
        self._layerTableDocWidget = None

    def displayAicsSegmentation_napari(self, oa : oligoAnalysis):
        
        # run aics segmenter algorithm on oligo (cyto) channel
        oa.aicsAnalysis()
        aicsDict = oa._aicsDict

        imgCyto = aicsDict['imgData']
        imgNorm = aicsDict['imgNorm']
        imgSmooth = aicsDict['imgSmooth']
        imgFilament = aicsDict['imgFilament']
        imgRemoveSmall = aicsDict['imgRemoveSmall']

        viewer = self._viewer
        scale = None
        _color = 'red'

        layerName = 'cyto'

        # required so we do not trigger napari events
        self._buildingNapari = True

        # raw image data
        imgCytoLayer = viewer.add_image(imgCyto, name=f'{layerName} Image',
                                scale=scale, blending='additive')
        imgCytoLayer.visible = True
        imgCytoLayer.colormap = _color
        _maxCyto = np.max(imgCyto) * 0.3
        imgCytoLayer.contrast_limits = (np.min(imgCyto), _maxCyto)

        # normalized image
        _imgCytoLayer = viewer.add_image(imgNorm, name=f'{layerName} Norm',
                                scale=scale, blending='additive')
        _imgCytoLayer.visible = True
        _imgCytoLayer.colormap = _color
        _max = np.max(imgNorm) * 0.3
        _imgCytoLayer.contrast_limits = (np.min(imgNorm), _max)

        # normalized image
        _imgCytoLayer = viewer.add_image(imgSmooth, name=f'{layerName} Gaussian',
                                scale=scale, blending='additive')
        _imgCytoLayer.visible = True
        _imgCytoLayer.colormap = _color
        _max = np.max(imgSmooth) * 0.3
        _imgCytoLayer.contrast_limits = (np.min(imgSmooth), _max)

        # filament mask
        _binaryLayer = viewer.add_labels(imgFilament, name=f'{layerName} Filament Mask',
                                color={1:'#FF00FFFF'},
                                scale=scale)
        _binaryLayer.visible = True

        # filament mask - small removed
        _binaryLayer = viewer.add_labels(imgRemoveSmall, name=f'{layerName} Pruned Filament Mask',
                                color={1:'#FF00FFFF'},
                                scale=scale)
        _binaryLayer.visible = True

        # required so we do not trigger napari events
        self._buildingNapari = False

    def displayChannel_napari(self, oa : oligoAnalysis, imageChannel : imageChannels.cyto):
        """Display cyto or dapi (image, filtered, binary).
        
        Jan 2023
        """

        logger.info('')
        
        #_imageChannel = imageChannels.cyto

        if imageChannel == imageChannels.cyto:
            _color = 'red'
        elif imageChannel == imageChannels.dapi:
            _color = 'green'

        layerName = imageChannel.value

        # required so we do not trigger napari events
        self._buildingNapari = True

        # physical units, x/y/z scalue of the image in um/pixel        
        xVoxel = oa._header['xVoxel']
        yVoxel = oa._header['yVoxel']
        zVoxel = oa._header['zVoxel'] / 2  # real scale looks like crap!
        scale = (zVoxel, yVoxel, xVoxel)
        scale = None

        viewer = self._viewer

        # raw
        imgCyto = oa.getImageChannel(imageChannel)
        # filtered
        imgCyto_filtered = oa.getImageFiltered(imageChannel)        
        # binary after otsu
        imgCyto_binary = oa.getImageMask(imageChannel)

        imgCytoLayer = viewer.add_image(imgCyto, name=f'{layerName} Image',
                                scale=scale, blending='additive')
        imgCytoLayer.visible = True
        imgCytoLayer.colormap = _color
        _maxCyto = np.max(imgCyto) * 0.3
        imgCytoLayer.contrast_limits = (np.min(imgCyto), _maxCyto)

        _binaryLayer = viewer.add_labels(imgCyto_binary, name=f'{layerName} Binary',
                                color={1:'#FF00FFFF'},
                                scale=scale)
        _binaryLayer.visible = True

        _filteredLayer = viewer.add_image(imgCyto_filtered, name=f'{layerName} Filtered',
                                scale=scale, blending='additive')
        _filteredLayer.visible = True
        _filteredLayer.colormap = 'yellow'  # _color
        _maxCytoFiltered = np.max(imgCyto_filtered) * 0.3
        _filteredLayer.contrast_limits = (np.min(imgCyto_filtered), _maxCytoFiltered)

        if imageChannel == imageChannels.cyto:
            self._redbinaryLayer = _binaryLayer
            self._redFilteredLayer = _filteredLayer
        elif imageChannel == imageChannels.dapi:
            self._greenbinaryLayer = _binaryLayer
            self._greenFilteredLayer = _filteredLayer

        self._buildingNapari = True

    def displayOligoAnalysis_napari(self, oa : oligoAnalysis):
        """Display all oligo analysis images in napari viewer.
        """
        self._buildingNapari = True

        viewer = self._viewer
        
        #imgRgb = oa._getRgbStack()
        imgCyto = oa.getImageChannel(imageChannels.cyto)
        imgDapi = oa.getImageChannel(imageChannels.dapi)
        imgCellposeMask = oa.getCellPoseMask()  # can be None

        imgCyto_binary = oa.getImageMask(imageChannels.cyto)
        imgCyto_filtered = oa.getImageFiltered(imageChannels.cyto)
        
        imgDapi_binary = oa.getImageMask(imageChannels.dapi)
        imgDapi_filtered = oa.getImageFiltered(imageChannels.dapi)

        dapiFinalMask = oa._dapiFinalMask  # can be None
        
        logger.error('lots of napari plugins do not work on scaled images ... hold off on this !!!')
        doScale = False
        if doScale:
            xVoxel = oa._header['xVoxel']
            yVoxel = oa._header['yVoxel']
            zVoxel = oa._header['zVoxel'] / 2  # real scale looks like crap!
            scale = (zVoxel, yVoxel, xVoxel)
        else:
            xVoxel = 1 
            yVoxel = 1
            zVoxel = 1
            scale = None
        
        imgCytoLayer = viewer.add_image(imgCyto, name='Cyto Image',
                                scale=scale, blending='additive')
        imgCytoLayer.visible = True
        imgCytoLayer.colormap = 'red'
        _maxCyto = np.max(imgCyto) * 0.3
        imgCytoLayer.contrast_limits = (np.min(imgCyto), _maxCyto)

        imgDapiLayer = viewer.add_image(imgDapi, name='DAPI Image',
                                scale=scale, blending='additive')
        imgDapiLayer.visible = True
        imgDapiLayer.colormap = 'green'
        _maxDapi = np.max(imgDapi) * 0.3
        imgDapiLayer.contrast_limits = (np.min(imgDapi), _maxDapi)

        # we want to be able to update this image
        self._redbinaryLayer = viewer.add_labels(imgCyto_binary, name='Cyto Binary',
                                scale=scale)
        self._redbinaryLayer.visible = False

        self._redFilteredLayer = viewer.add_image(imgCyto_filtered, name='Cyto Filtered',
                                scale=scale, blending='additive')
        self._redFilteredLayer.visible = False
        self._redFilteredLayer.colormap = 'red'
        #self._redFilteredLayer.contrast_limits = (0, 150)

        # adding dapping filtered and mask
        # we want to be able to update this image
        self._greenbinaryLayer = viewer.add_labels(imgDapi_binary, name='DAPI Binary',
                                scale=scale)
        self._greenbinaryLayer.visible = False

        self._greenFilteredLayer = viewer.add_image(imgDapi_filtered, name='DAPI Filtered',
                                scale=scale, blending='additive')
        self._greenFilteredLayer.visible = False
        self._greenFilteredLayer.colormap = 'green'

        # we will not update this, until we add runnign a model (slow)
        if imgCellposeMask is not None:
            imgDapiMask_layer = viewer.add_labels(imgCellposeMask, name='DAPI Cellpose Label',
                                scale=scale)
            imgDapiMask_layer.visible = True

        # we want to be able to update this image
        if dapiFinalMask is None:
            dapiFinalMask = np.zeros((1,1,1), dtype=np.uint64)
        self.dapiFinalMask_layer = viewer.add_labels(dapiFinalMask, name='DAPI Ring Mask', scale=scale)
        self.dapiFinalMask_layer.visible = False

        #
        # make a pnts layer from labels
        #_cellPoseMask = oa._getCellPoseMask()  # can be none
        if imgCellposeMask is not None:

            # problem if we save analysis and then remake the mask
            # len/# of masks is + 1 because 0 is background
            if len(np.unique(imgCellposeMask))-1 != len(oa._dfLabels):
                logger.error(f'number of maks not each to number in df')
                logger.error(f'  did you remake th mask? IF so, delete the analysis')

            _regionprops = skimage.measure.regionprops(imgCellposeMask)
            _regionpropsTable = skimage.measure.regionprops_table(imgCellposeMask)

            # add centroid to napari
            _points = [
                (s.centroid[0]*zVoxel, s.centroid[1]*yVoxel, s.centroid[2]*xVoxel) 
                for s in _regionprops]  # point[i] is a tuple of (z, y, x)
            _area = [s.area for s in _regionprops]  # point[i] is a tuple of (z, y, x)
            _label = [s.label for s in _regionprops]  # point[i] is a tuple of (z, y, x)

            # dec22
            # _regionprops and oa._dfLabels need same length
            logger.info(f'imgCellposeMask:{len(np.unique(imgCellposeMask))}')
            logger.info(f'  _points:{len(_points)}')
            logger.info(f'  _area:{len(_area)}')
            logger.info(f'  _label:{len(_label)}')
            logger.info(f'  oa._dfLabels:{len(oa._dfLabels)}')
            # len/# of masks is + 1 because 0 is background
            if len(np.unique(imgCellposeMask))-1 != len(oa._dfLabels):
                logger.error(f'number of masks not each to number in df')
                logger.error(f'  did you remake the mask? IF so, delete the analysis')

            properties = {
                'label': _label,
                'accept': oa._dfLabels['accept'],
                'cytoImageMaskPercent': oa._dfLabels['cytoImageMaskPercent'],
                'area': _area,
            }

            # add points to viewer
            if doScale:
                _pointSize = 0.6 # when using scale
            else:
                _pointSize = 5 # when not using scale, turning scale off as most napari plugins do not respect it !!!!
            
            label_layer_points = viewer.add_points(_points,
                                                name='DAPI label points',
                                                #face_color=face_color,
                                                symbol='cross',
                                                size=_pointSize,
                                                properties=properties)

            #
            self._layerTableDocWidget = self.openLayerTablePugin(label_layer_points)
        
        # set histogram to red image layer (data and name)
                # respond to changes in image contrast
        if self._bHistogramWidget is not None:
            self._bHistogramWidget.slot_setData(imgCytoLayer.data, imgCytoLayer.name)
        
            # TODO: fix this
            self._bHistogramWidget.signalContrastChange.connect(self.slot_contrastChange)
            #print('imgCytoLayer.events.contrast_limits:', imgCytoLayer.events.contrast_limits) 

        self._buildingNapari = False

    def slot_contrastChange(self, contrastDict):
        """Received when user changes contrast in our widget.
        
        Args:
            contrastDict: {'channel': 1, 'colorLUT': None, 'minContrast': 0, 'maxContrast': 46, 'bitDepth': 8}
        """
        # TODO: fix this
        logger.info('')
        print(contrastDict)

        # if napari viewer selected layer is image and mateches name
        # directly set contrast_limits = [min, max]
        _title = contrastDict['title']  # corresponds to napari image layer name/title
        try:
            _layer = self._viewer.layers[_title]
            print(_layer)
            minContrast = contrastDict['minContrast']
            maxContrast = contrastDict['maxContrast']
            _layer.contrast_limits = [minContrast, maxContrast]
        except (KeyError) as e:
            logger.warning('Did not find napari layer named "{_title}"')

def showScatterPlots(oi :oligoInterface):
    
    path = '/Users/cudmore/Dropbox/data/whistler/cudmore/oligo-simmary-20230112-cs-0.7.csv'
    if not os.path.isdir(path):
        logger.error(f'did not find path: {path}')
        return
    
    df = pd.read_csv(path)
    df = df[df.parentFolder != 'Adolescent']
    df = df.reset_index()

    from bScatterPlotWidget2 import bScatterPlotMainWindow
    interfaceDefaults = {'Y Statistic': 'cytoMaskPercent',
                        'X Statistic': 'parentFolder',
                        'Hue': 'parentFolder',
                        'Group By': 'parentFolder'}

    # parentFolder is condition (saline, fst, morphine)
    # grandParentFolder is date of imaging
    categoricalList = ['parentFolder', 'grandParentFolder', 'region']
    hueTypes = ['parentFolder', 'grandParentFolder', 'region']
    analysisName = 'parentFolder'
    sortOrder = ['parentFolder', 'grandParentFolder', 'region']
    spw = bScatterPlotMainWindow(None, categoricalList, hueTypes, analysisName,
                sortOrder=sortOrder,
                masterDf=df,
                interfaceDefaults=interfaceDefaults)
    # connect user click of point in scatter to oligoInterface (select a row in table)
    spw.signalSelectFromPlot.connect(oi.slot_selectFromPlot)
    spw.show()

def run():
    # cziPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/B35_Slice2_RS_DS1.czi'
    # oa = oligoAnalysis(cziPath)

    # for oligoInterface
    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/cudmore/20221010/Morphine'

    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Adolescent'
    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Saline'

    _folderPath = '/Users/cudmore/Dropbox/data/whistler/cudmore'
    _folderPath = '/media/cudmore/data/Dropbox/data/whistler/cudmore'

    if not os.path.isdir(_folderPath):
        logger.error(f'did not find path: {_folderPath}')
        return

    viewer = napari.Viewer()

    # get underlying qt QApplication
    _app = napari.qt.get_app()  # PyQt5.QtWidgets.QApplication
    # _app.processEvents()
    #print('_app:', type(_app))

    # set app to dark
    _app.setStyleSheet(qdarkstyle.load_stylesheet())

    # set app font size
    logger.info(f'app font: {_app.font().family()} {_app.font().pointSize()}')
    _fontSize = 12
    aFont = QtGui.QFont('Arial', _fontSize)
    _app.setFont(aFont, "QLabel")
    #_app.setFont(aFont, "QComboBox")
    _app.setFont(aFont, "QPushButton")
    _app.setFont(aFont, "QCheckBox")
    _app.setFont(aFont, "QSpinBox")
    _app.setFont(aFont, "QDoubleSpinBox")
    _app.setFont(aFont, "QTableView")
    _app.setFont(aFont, "QToolBar")

    # open interface with folder
    oi = oligoInterface(viewer, _folderPath)
    oi.show()

    #oi.displayOligoAnalysis(oa)
    showScatterPlots(oi)

    napari.run()

if __name__ == '__main__':
    run()