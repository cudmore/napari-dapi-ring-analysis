"""
20221101
"""
import os
import time
from typing import List, Union  # , Callable, Iterator, Optional

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

    signalSelectImageLayer = QtCore.Signal(object, object, object)
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
            hideColumns = ['date', 'time',
                    'xPixels', 'yPixels', 'xVoxel', 'yVoxel', 'zVoxel',
                    'dapiChannel', 'cytoChannel',
                    'xyScaleFactor',
                    'cytoStackPixels', 'cytoMaskPixels']
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
            
            _data = _activeLayer.data
            _name = _activeLayer.name
            _colorMapName = _activeLayer.colormap.name

            # napari.utils.Colormap: colormap
            #print(_activeLayer.colormap)  # 2d array of [r,g,b,a]
            print(f'  _activeLayer.colormap.name:{_activeLayer.colormap.name}')

            # TODO: when our hist signals contrast slider change,
            #   change layer.events.contrast_limits
            
            # want something like this
            #_activeLayer.events.contrast_limits.connect(self._bHistogramWidget.slot_setContrast)
            # this for now
            # _activeLayer.events.contrast_limits.connect(self.slot_setContrast)
            
            # does not work
            # self._bHistogramWidget.signal_contrast_limits.connect(_activeLayer.events.contrast_limits)

            logger.info(f'  -->> emit signalSelectImageLayer _data.shape {_data.shape} _name:{_name}')
            self.signalSelectImageLayer.emit(_data, _name, _colorMapName)

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

        aButton = QtWidgets.QPushButton('Save')
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
        _empty = np.zeros((1,1,1))
        self._bHistogramWidget = bHistogramWidget(_empty)
        self._bHistogramWidget.setVisible(False)
        self.signalSelectImageLayer.connect(self._bHistogramWidget.slot_setData)
        self.signalSetSlice.connect(self._bHistogramWidget.slot_setSlice)
        vLayout.addWidget(self._bHistogramWidget)

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
        df = dfAnalysis[dfAnalysis['file']==self._selectedFile]

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
        self._bHistogramWidget.setVisible(checked)

    def on_points_checkbox(self, state):
        """Toggle napari viewer layer-table-plugin.
        """
        logger.info(f'state:{state}')
        checked = state > 0
        if self._layerTableDocWidget is not None:
            self._layerTableDocWidget.setVisible(checked)

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

        filename = rowDict['file']
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

    def switchFile(self, filename : str, row : int):
        """load oa

        Args:
            filename:
            row:
        """
        logger.info(f'filename:{filename}')

        if filename == self._selectedFile:
            logger.info(f'  file is already selected: {self._selectedFile}')
            return
        
        self._selectedRow = row
        self._selectedFile = filename

        self._viewer.title = filename
                
        # get selected oa
        oa = self._oligoAnalysisFolder.getOligoAnalysis(filename)

        # complete refresh of napari viewer
        self.clearViewer()  # remove all layers
        self.displayOligoAnalysis_napari(oa)

        # set gaussian sigma
        _gaussianSigma = oa._header['gaussianSigma']
        _gaussianSigma = str(_gaussianSigma)
        self._sigmaLineEditWidget.setText(_gaussianSigma)
        
        # set dilate/erode
        self._dilateSpinBox.setValue(oa._header['dilateIterations'])
        self._erodeSpinBox.setValue(oa._header['erodeIterations'])

        # set analysis table
        # xxx

        self._selectedFilleLabel.setText(filename)

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
        self._ltp.myTable2.signalEditingRows.connect(self.slot_editingRows)
        #ltp.signalDataChanged.connect(on_user_edit_points2)
        
        # show
        area = 'right'
        name = layer.name
        
        # napari._qt.widgets.qt_viewer_dock_widget.QtViewerDockWidget
        _layerTableDocWidget = viewer.window.add_dock_widget(self._ltp, area=area, name=name)
        
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
        viewer.window.remove_dock_widget(self._layerTableDocWidget) 
        self._layerTableDocWidget = None

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
        
        #viewer = napari.Viewer()
        xVoxel = oa._header['xVoxel']
        yVoxel = oa._header['yVoxel']
        zVoxel = oa._header['zVoxel'] / 2  # real scale looks like crap!

        scale = (zVoxel, yVoxel, xVoxel)

        imgCytoLayer = viewer.add_image(imgCyto, name='Cyto Image',
                                scale=scale, blending='additive')
        imgCytoLayer.visible = True
        imgCytoLayer.colormap = 'red'
        imgCytoLayer.contrast_limits = (np.min(imgCyto), np.max(imgCyto))

        imgDapiLayer = viewer.add_image(imgDapi, name='DAPI Image',
                                scale=scale, blending='additive')
        imgDapiLayer.visible = True
        imgDapiLayer.colormap = 'green'
        imgDapiLayer.contrast_limits = (np.min(imgDapi), np.max(imgDapi))

        # we want to be able to update this image
        self._redbinaryLayer = viewer.add_labels(imgCyto_binary, name='Cyto Binary',
                                scale=scale)
        self._redbinaryLayer.visible = True

        self._redFilteredLayer = viewer.add_image(imgCyto_filtered, name='Cyto Filtered',
                                scale=scale, blending='additive')
        self._redFilteredLayer.visible = False
        self._redFilteredLayer.colormap = 'red'
        #self._redFilteredLayer.contrast_limits = (0, 150)

        # adding dapping filtered and mask
        # we want to be able to update this image
        self._greenbinaryLayer = viewer.add_labels(imgDapi_binary, name='DAPI Binary',
                                scale=scale)
        self._greenbinaryLayer.visible = True

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
            logger.info(f'_points:{len(_points)}')
            logger.info(f'_area:{len(_area)}')
            logger.info(f'_label:{len(_label)}')
            logger.info(f'oa._dfLabels:{len(oa._dfLabels)}')
            # len/# of masks is + 1 because 0 is background
            if len(np.unique(imgCellposeMask))-1 != len(oa._dfLabels):
                logger.error(f'number of maks not each to number in df')
                logger.error(f'  did you remake th mask? IF so, delete the analysis')

            properties = {
                'label': _label,
                'accept': oa._dfLabels['accept'],
                'cytoImageMaskPercent': oa._dfLabels['cytoImageMaskPercent'],
                'area': _area,
            }

            # add points to viewer
            label_layer_points = viewer.add_points(_points,
                                                name='DAPI label points',
                                                #face_color=face_color,
                                                symbol='cross',
                                                size=5,
                                                properties=properties)

            #
            self._layerTableDocWidget = self.openLayerTablePugin(label_layer_points)
        
        # set histogram to red image layer (data and name)
                # respond to changes in image contrast
        self._bHistogramWidget.slot_setData(imgCytoLayer.data, imgCytoLayer.name)
        
        # TODO: fix this
        self._bHistogramWidget.signalContrastChange.connect(self.slot_contrastChange)
        #print('imgCytoLayer.events.contrast_limits:', imgCytoLayer.events.contrast_limits) 

        self._buildingNapari = False

    def slot_contrastChange(self, contrastDict):
        # TODO: fix this
        logger.info('')
        #print(contrastDict)

        # if napari viewer selected layer is image and mateches name
        # directly set contrast_limmits = [min, max]

if __name__ == '__main__':
    # cziPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST/B35_Slice2_RS_DS1.czi'
    # oa = oligoAnalysis(cziPath)

    # for oligoInterface
    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/FST'
    _folderPath = '/Users/cudmore/Dropbox/data/whistler/data-oct-10/Morphine'

    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Adolescent'
    #_folderPath = '/Users/cudmore/Dropbox/data/whistler/11-9-22 (Adolescent and Saline)/Saline'
    
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

    napari.run()