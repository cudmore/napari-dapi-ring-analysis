from pprint import pprint
import numpy as np
import pandas as pd
from qtpy import QtCore, QtGui, QtWidgets
from typing import Set

from napari_dapi_ring_analysis._logger import logger

class myTableView(QtWidgets.QTableView):
    """Table view to display list of points in a point layer.
    """

    signalSelectionChanged = QtCore.Signal(object, object)
    """Emit when user changes row selection."""

    def __init__(self, parent=None):
        # super(myTableView, self).__init__(parent)
        super().__init__(parent)

        self.myModel = None
        
        self.blockUpdate = False
        
        self.hiddenColumnSet = set()
        self.hiddenColumnSet.add('Face Color')

        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                            QtWidgets.QSizePolicy.Expanding)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers
                            | QtWidgets.QAbstractItemView.DoubleClicked)

        self.setSelectionBehavior(QtWidgets.QTableView.SelectRows)

        # allow discontinuous selections (with command key)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.setSortingEnabled(True)

        # to allow click on already selected row
        self.clicked.connect(self.old_on_user_click_row)

    def setFontSize(self, fontSize : int = 11):
        """Set the table font size.
        
        This does not set the font size of cells, that is done in model data().
        """
        aFont = QtGui.QFont('Arial', fontSize)
        self.setFont(aFont)  # set the font of the cells
        self.horizontalHeader().setFont(aFont)
        self.verticalHeader().setFont(aFont)

        self.verticalHeader().setDefaultSectionSize(fontSize)  # rows
        self.verticalHeader().setMaximumSectionSize(fontSize)
        #self.horizontalHeader().setDefaultSectionSize(_fontSize)  # rows
        #self.horizontalHeader().setMaximumSectionSize(_fontSize)
        self.resizeRowsToContents()

    def keyPressEvent(self, event):
        """
        Args:
            vent: PyQt5.QtGui.QKeyEvent
        """
        #logger.info(f'event: {type(event)})')
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        #isShift = modifiers == QtCore.Qt.ShiftModifier
        isCtrl = modifiers == QtCore.Qt.ControlModifier
        keyText = event.text()
        keyEnum = event.key()
        keyTextIsC = keyEnum  == QtCore.Qt.Key_C
        #print(f'{isCtrl} "{keyText}" "{keyEnum}"')
        if isCtrl and keyTextIsC:
            dfCopy = self.myModel.myGetData().copy()
            dfCopy.to_clipboard(sep='\t', index=False)
            logger.info(f'Copied table to clipboard with shape: {dfCopy.shape}')
            print(dfCopy)

    def getNumRows(self):
        """Get number of rows from the model.
        """
        return self.myModel.rowCount()
    
    def getColumns(self):
        """Get columns from model.
        """
        return self.myModel.myGetData().columns

    def clearSelection(self):
        """Over-ride inherited.
        
        Just so we can see this in our editor.
        """
        super().clearSelection()
    
    def selectRow(self, rowIdx : int):
        """Select one row.
        
        Args:
            rowIdx (int): The row index into the model.
                it is not the visual row index if table is sorted
        """
        modelIndex = self.myModel.index(rowIdx, 0)  # rowIdx is in 'model' coordinates
        _visualRow = self.proxy.mapFromSource(modelIndex)
        visualRow = self.proxy.mapFromSource(modelIndex).row()
        logger.info(f'model rowIdx:{rowIdx} corresponds to visual row:{visualRow}')

        self.scrollTo(_visualRow, QtWidgets.QAbstractItemView.PositionAtTop)

        super().selectRow(visualRow)

    def mySelectRows(self, rows : Set[int]):
        """Make a new row selection from viewer.
        """
                        
        # to stop event recursion
        self.blockUpdate = True
        
        selectionModel = self.selectionModel()
        if selectionModel:
            selectionModel.clear()
        
            if rows:
                indexes = [self.myModel.index(r, 0) for r in rows]  # [QModelIndex]
                visualRows = [self.proxy.mapFromSource(modelIndex) for modelIndex in indexes]

                mode = QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows
                [self.selectionModel().select(i, mode) for i in visualRows]

                # scroll so first row in rows is visible
                # TODO (cudmore) does not work if list is filtered
                # column = 0
                # row = list(rows)[0]
                # index = self.model().index(row, column)
                # 20221031, was
                #self.scrollTo(index)


                logger.warning(f'20221101 FIX SNAP TO SELECTED ROW')
                # column = 0
                # row = visualRows[0]
                # index = self.model().index(row, column)
                # self.scrollTo(index)

            else:
                #print('  CLEARING SELECTION')
                self.clearSelection()
        
        #
        self.blockUpdate = False

    #def mySetModel(self, model : pd.DataFrame):
    def mySetModel(self, model):
        """ Set the model. Needed so we can show/hide columns

        Args:
            napari_dapi_ring_analysis.interface._data_model.pandasModel
            
            NOT a df: model (pd.DataFrame): DataFrame to set model to.
        """
        self.myModel = model
        
        selectionModel = self.selectionModel()
        if selectionModel is not None:
            selectionModel.selectionChanged.disconnect(self.on_selectionChanged)

        self.proxy = QtCore.QSortFilterProxyModel()
        self.proxy.setSourceModel(model)

        self.myModel.beginResetModel()
        self.setModel(self.proxy)
        self.myModel.endResetModel()
        
        self.selectionModel().selectionChanged.connect(self.on_selectionChanged)
        #self.selectionModel().currentChanged.connect(self.old_on_currentChanged)

        # refresh hidden columns, only usefull when we first build interface
        self._refreshHiddenColumns()

    def mySetColumnHidden(self, colStr : str, hidden : bool = True):
        _columns = self.myModel.myGetData().columns
        if not colStr in _columns:
            logger.error(f'did not find {colStr} in model columns')
            return

        if hidden:
            self.hiddenColumnSet.add(colStr)  # will not add twice
        else:
            if colStr in self.hiddenColumnSet:
                self.hiddenColumnSet.remove(colStr)
        self._refreshHiddenColumns()
        #colIdx = self.myModel._data.columns.get_loc(colStr)
        #self.setColumnHidden(colIdx, hidden)

    def _refreshHiddenColumns(self):
        columns = self.myModel.myGetData().columns
        for column in columns:
            colIdx = columns.get_loc(column)
            self.setColumnHidden(colIdx, column in self.hiddenColumnSet)

    def old_on_user_click_row(self, item):
        """User clicked a row.
        
        Only respond if alt+click. Used to zoom into point

        Args:
            item (QModelIndex): Model index of one row user selection.
        
        TODO:
            This is used so alt+click (option on macos) will work
                even in row is already selected. This is causing 'double'
                selection callbacks with on_selectionChanged()
        """                
        # pure PyQt
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        #isShift = modifiers == QtCore.Qt.ShiftModifier
        isAlt = modifiers == QtCore.Qt.AltModifier
        
        if not isAlt:
            return
        
        row = self.proxy.mapToSource(item).row()
        logger.info(f'row:{row}')

        selectedRowList = [row]
        self.signalSelectionChanged.emit(selectedRowList, isAlt)

    def on_selectionChanged(self, selected, deselected):
        """Respond to change in selection.

            Args:
                selected (QItemSelection):
                deselected (QItemSelection):

            Notes:
                - We are not using (selected, deselected) parameters,
                    instead are using self.selectedIndexes()
                - Connected to: self.selectionModel().selectionChanged
        """

        if self.blockUpdate:
            #self.blockUpdate = False
            return
            
        # pure PyQt
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        isShift = modifiers == QtCore.Qt.ShiftModifier
        isAlt = modifiers == QtCore.Qt.AltModifier
        
        # BINGO, don't use params, use self.selectedIndexes()
        selectedIndexes = [self.proxy.mapToSource(modelIndex).row()
                            for modelIndex in self.selectedIndexes()]
        
        # reduce to list of unique values
        selectedIndexes = list(set(selectedIndexes))  # to get unique values
        
        logger.info(f'selectedIndexes:{selectedIndexes}')
        
        self.signalSelectionChanged.emit(selectedIndexes, isAlt)

    '''
    def old_on_currentChanged(self, current, previous):
        """
        
        Args:
            current (QtCore.QModelIndex)
        """
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        isShift = modifiers == QtCore.Qt.ShiftModifier

        logger.info('')
        print(f'  current:{current.row()}')
        print(f'  previous:{previous.row()}')

        selectedRows = self.selectionModel().selectedRows()
        print(f'  selectedRows:{selectedRows}')

        #self.signalSelectionChanged.emit(selectedRowList, isShift)
    '''

