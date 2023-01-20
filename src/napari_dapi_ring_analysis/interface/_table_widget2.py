import sys

from qtpy import QtCore, QtGui, QtWidgets

from napari_dapi_ring_analysis._logger import logger

data = {'index':['1','2','3','4'],
        'col2':['1','2','1','3'],
        'col3':['1','1','2','1']}
 
class TableView(QtWidgets.QTableWidget):

    signalSelectionChanged = QtCore.Signal(object, object)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        
        self.setRowCount(4)
        self.setColumnCount(3)
        
        self.data = data
        self.setData()
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
 
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                            QtWidgets.QSizePolicy.Expanding)
        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers
                            | QtWidgets.QAbstractItemView.DoubleClicked)

        self.setSelectionBehavior(QtWidgets.QTableView.SelectRows)

        # allow discontinuous selections (with command key)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.setSortingEnabled(True)

        # to allow click on already selected row
        self.itemClicked.connect(self.on_user_click_item)

        _item = QtWidgets.QTableWidgetItem("xxx")
        self.setVerticalHeaderItem(1, _item)

    def setData(self): 
        horHeaders = []
        for n, key in enumerate(sorted(self.data.keys())):
            horHeaders.append(key)
            for m, item in enumerate(self.data[key]):
                newitem = QtWidgets.QTableWidgetItem(item)
                self.setItem(m, n, newitem)
        self.setHorizontalHeaderLabels(horHeaders)
 
    def on_user_click_item(self, item):
        """User clicked a row.
        
        Only respond if alt+click. Used to zoom into point

        Args:
            item (QTableWidgetItem): 
        
        TODO:
            This is used so alt+click (option on macos) will work
                even in row is already selected. This is causing 'double'
                selection callbacks with on_selectionChanged()
        """                
        # pure PyQt
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        isAlt = modifiers == QtCore.Qt.AltModifier
        
        # if not isAlt:
        #     return
        
        row = item.row()

        #row = self.proxy.mapToSource(item).row()
        logger.info(f'row:{row}')

        selectedRowList = [row]
        logger.info(f'selectedRowList:{selectedRowList} isAlt:{isAlt}')
        self.signalSelectionChanged.emit(selectedRowList, isAlt)

def magicTable():
    from magicgui.widgets import Table
    dict_of_lists = {"col_1": [1, 4], "col_2": [2, 5], "col_3": [3, 6]}
    table = Table(value=dict_of_lists)
    table.show()

def main(args):
    app = QtWidgets.QApplication(args)
    table = TableView(data)
    table.show()

    magicTable()
    
    sys.exit(app.exec_())
 
if __name__=="__main__":
    main(sys.argv)