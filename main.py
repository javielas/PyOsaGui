import sys, traceback, csv
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import QTimer, QRunnable, Slot, Signal, QObject, QThreadPool, QModelIndex, Qt, QAbstractItemModel
from pyqtgraph import PlotWidget
from PySide6.QtGui import QStandardItem, QIcon, QFont, QColor
import pyqtgraph as pg
import numpy as np
import time, datetime
import xarray as xr
from pint import UnitRegistry
import zipfile
import tempfile
import os




from MainWindow import Ui_MainWindow

ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity

offline_mode = True
save_every_sweep = False

if not offline_mode: import osa_driver

#Matplotlib default set of colors
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2',
 '#7f7f7f', '#bcbd22', '#17becf']

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)

class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    see https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

class TreeItem:
    """Represents each item in the tree, which could be a root or child."""
    def __init__(self, name, data = None, parent=None, color=QColor(Qt.GlobalColor.transparent), metadata = None, plot =  None):
        self.data = data  # This holds the item data
        self.parent_item = parent  # The parent of this item
        self.child_items = []  # A list of child items
        self.checked = Qt.Checked  # Default to checked
        self.color = color
        self.name = name
        self.metadata = metadata
        self.plot = plot

    def get_checked(self):
        return self.checked

    def append_child(self, child):
        """Adds a child to the current item."""
        self.child_items.append(child)

    def child(self, row):
        """Returns the child at the specified row."""
        return self.child_items[row]
    
    def get_childs(self):
        return self.child_items

    def child_count(self):
        """Returns the number of children."""
        return len(self.child_items)

    def row(self):
        """Returns the row number of this item relative to its parent."""
        if self.parent_item:
            return self.parent_item.child_items.index(self)
        return 0

    def column_count(self):
        """Returns the number of columns (1 in this case)."""
        return 1

    def data_at_column(self, column):
        """Returns the data at the specified column."""
        if column == 0:
            return self.data
        return None

    def parent(self):
        """Returns the parent of this item."""
        return self.parent_item


class TreeModel(QAbstractItemModel):

    check_state_changed = Signal(QModelIndex, Qt.CheckState) #Custom signal to toggle visibility in the plot


    """Custom model for representing a list of dictionaries in a tree."""
    def __init__(self, data=[], parent=None):
        super().__init__(parent)
        self.root_item = TreeItem(name = "Root")

    # Required Abstract Methods
    def rowCount(self, parent=QModelIndex()):
        """Returns the number of rows under the given parent."""
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()
        return parent_item.child_count()

    def columnCount(self, parent=QModelIndex()):
        """Returns the number of columns for the children of the given parent."""
        if parent.isValid():
            return parent.internalPointer().column_count()
        return self.root_item.column_count()

    def index(self, row, column, parent=QModelIndex()):
        """Creates an index for the item at the given row, column, and parent."""
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)
        return QModelIndex()

    def parent(self, index):
        """Returns the parent of the item with the given index."""
        if not index.isValid():
            return QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)
    
    def add_parent(self, parent_name):
        """Method to add a new parent (root) item."""
        # Create a new root item with the given parent_name
        new_root_item = TreeItem(name = parent_name, parent=self.root_item)

        # Append the new root item to the model
        self.root_item.append_child(new_root_item)

        # Notify the view of the changes
        parent_index = QModelIndex()  # Root has an invalid QModelIndex
        self.beginInsertRows(parent_index, self.root_item.child_count() - 1, self.root_item.child_count() - 1)
        self.endInsertRows()

    def add_child(self, parent_item: TreeItem, child_item: TreeItem):
        """Method to add a new child to a specific parent."""
        # Get the parent index
        if parent_item == self.root_item:
            parent_index = QModelIndex()
        else:
            parent_index = self.createIndex(parent_item.row(), 0, parent_item)

        # Insert the child into the parent
        self.beginInsertRows(parent_index, parent_item.child_count(), parent_item.child_count())
        parent_item.append_child(child_item)
        self.endInsertRows()

        # Notify the view of the changes
        self.dataChanged.emit(parent_index, parent_index)

    def setData(self, index, value, role=Qt.EditRole):
        if role not in (Qt.EditRole, Qt.CheckStateRole):
            return False

        if not index.isValid():
            return False

        item = index.internalPointer()
        if role == Qt.EditRole:
            item.name = value
            item.data.name = value
        elif role == Qt.CheckStateRole:
            item.checked = value
            self.check_state_changed.emit(index, value)
            if item.parent() == self.root_item:
                # This is a group item, update all children
                for child in item.get_childs():
                    child.checked = value
                    child_index = self.index(child.row(), 0, index)
                    self.dataChanged.emit(child_index, child_index, [Qt.CheckStateRole])
        
        self.dataChanged.emit(index, index, [role])
        return True

    def flags(self, index):
        """Returns the item flags for the given index."""
        if not index.isValid():
            return Qt.NoItemFlags

        return Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def data(self, index, role):
        """Returns the data stored under the given role for the item referred to by the index."""
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == Qt.DisplayRole or role == Qt.EditRole:
            return item.name
        elif role == Qt.ItemDataRole.CheckStateRole:
            return Qt.CheckState.Checked if item.checked else Qt.CheckState.Unchecked
        elif role == Qt.DecorationRole:
            return QColor(item.color) if hasattr(item, 'color') else None

        return None

    def removeRow(self, row, parent=QModelIndex()):
        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        self.beginRemoveRows(parent, row, row)
        parent_item.child_items.pop(row)
        self.endRemoveRows()

        return True


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        #Create a threadpool for multithreading
        self.threadpool = QThreadPool()  

        self.model = TreeModel() # Set the model to be used and link it to the list of spectra
        self.treeView.setModel(self.model) # Assign to the treeView widget the model
        self.treeView.expandAll()

        self.sens_dict = {
            'Hold': 'SNHD',
            'Auto': 'SNAT',
            'High 1': 'SHI1',
            'High 2': 'SHI2',
            'High 3': 'SHI3'
        }

        #Plot Attributes
        self.plotWidget.setBackground('w')
        styles = {"color": "k", "font-size": "25px"}
        self.plotWidget.setLabel('left', 'Power (dBm)', **styles)
        self.plotWidget.setLabel('bottom', 'Wavelength (nm)', **styles)
        self.plotWidget.showGrid(x=True, y=True)

        #XY label coordinates for the plot
        self.x_label = pg.LabelItem("X:   ", color = 'k', size = '15pt')
        self.y_label = pg.LabelItem("Y:   ", color = 'k', size = '15pt')
        self.x_label.setParentItem(self.plotWidget.graphicsItem())
        self.y_label.setParentItem(self.plotWidget.graphicsItem())
        self.x_label.anchor(itemPos=(0.15, 0.9), parentPos=(0.03, 0.97))
        self.y_label.anchor(itemPos=(0.15, 0.9), parentPos=(0.03, 1))

        #Cross Cursor with lines
        cursor = Qt.CursorShape.CrossCursor
        self.plotWidget.setCursor(cursor)
        self.crosshair_en = True
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False)
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False)
        self.plotWidget.addItem(self.crosshair_v, ignoreBounds=True)
        self.plotWidget.addItem(self.crosshair_h, ignoreBounds=True)
        # Assign slot to the mousemovement
        self.proxy = pg.SignalProxy(self.plotWidget.scene().sigMouseMoved, rateLimit=60, slot=self.update_crosshair)

        #Buttons slot connections
        self.SweepPushButton.clicked.connect(self.getAndPlotSpectrum)
        self.DeletePushButton.clicked.connect(self.deleteTrace)
        self.SavePushButton.clicked.connect(self.saveChecked)
        self.model.check_state_changed.connect(self.handle_check_state_changed)
        self.NewGroupPushButton.clicked.connect(self.create_new_group)

        #Initialize values for comparison of parameters between sweep calls
        self.inputs = {'start': self.startWavlengthDoubleSpinBox, 'stop': self.stopWavelengthDoubleSpinBox, 
                       'resolution': self.resoltuionNmDoubleSpinBox, 'reference':self.referenceLevelDoubleSpinBox, 
                       'sensitivity': self.sensitivityComboBox, 'trace_points': self.PointsNmspinBox}

        #Create a starting group
        self.create_new_group()
        self.previous_color = None


    @Slot()
    def create_new_group(self):
        """This function creates a new group and adds it to the treeview as a root child. Enables the inputs for a new sweep"""
        group_count = self.model.root_item.child_count()
        group_name = f"Group {group_count + 1}"
        self.model.add_parent(group_name)
        for input_widget in self.inputs.values():
            input_widget.setEnabled(True)


    @Slot()
    def get_fake_spectrum(self):
        """This is a fake spectrum, it is used to test the GUI
        The spectrum is a dictonary with the wavelength and power arrays with the units"""
        #Generate fake data
        start = self.startWavlengthDoubleSpinBox.value() 
        stop = self.stopWavelengthDoubleSpinBox.value()
        points_per_nm = self.PointsNmspinBox.value() + 1
        x = np.arange(start, stop, 1/points_per_nm)
        y = (-(x-x[int(x.shape[0]/2)])**2)/100 + np.random.rand(x.shape[0]) + np.random.rand(1)
        time.sleep(1)
        spectrum_data = {
        'wavelength': Q_(x,  ureg.nm),
        'power': Q_(y , ureg.dBm),
        }
        return spectrum_data

    @Slot() 
    def getAndPlotSpectrum(self):
        """Triggers the plot acquisition in a different thread. When the spectrum sweep is finished, it plots it.
        Disables all the spinboxes buttons"""
        for input_widget in self.inputs.values():
            input_widget.setEnabled(False)

        #Create a worker for the spectrum acquisition
        if offline_mode:
            worker_get_spectrum = Worker(self.get_fake_spectrum)
        else:
            worker_get_spectrum = Worker(lambda: osa_driver.get_trace)
        worker_get_spectrum.signals.result.connect(self.plotSpectrum)
        self.threadpool.start(worker_get_spectrum)


    @Slot()
    def plotSpectrum(self, spectrum: dict):
        """Plots the spectrum and adds it to the list of spectra"""
        current_group = self.model.root_item.child(self.model.root_item.child_count()-1)
        if current_group.child_count() == 0:
            #Update the parameters of the OSA
            #self.update_osa_params(self.inputs)
            #Update the metadata of the group
            current_group.metadata = {
                'start': self.startWavlengthDoubleSpinBox.value(),
                'stop': self.stopWavelengthDoubleSpinBox.value(),
                'resolution': self.resoltuionNmDoubleSpinBox.value(),
                'reference': self.referenceLevelDoubleSpinBox.value(),
                'sensitivity': self.sensitivityComboBox.currentText(),
                'trace_points': self.PointsNmspinBox.value()
            }
            
        #Get the previous color from the list or start with the first one
        if self.previous_color is None:
            color = colors[0]
            self.previous_color = color
        else:
            color = colors[colors.index(self.previous_color)+1]
            self.previous_color = color
        
        color= QtGui.QColor(color)
        #Get the color that's the next from the last one in the list
        pen = pg.mkPen(color= color)
        wavelength = spectrum['wavelength'].to(ureg.nm).magnitude
        power = spectrum['power'].to(ureg.dBm).magnitude
        name = f'Trace {current_group.child_count()+1}'
        power_array = xr.DataArray(data = power ,
                                   coords = {'wavelength': wavelength},
                                   attrs= {'units': f'{spectrum["power"].units:~}', 
                                            'date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                                   name= name)
        power_array['wavelength'].attrs['units'] = f'{spectrum["wavelength"].units:~}'

        if save_every_sweep:
            power_array.to_netcdf(f'./temp/{datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")}.nc')
        
        plot = self.plotWidget.plot(wavelength, power, name = name, pen = pen)

        #Add the trace to the model
        current_group_index = self.model.root_item.child_count()-1
        #Create a tree item for the trace
        new_item = TreeItem(name= name, data = power_array, color  = color, parent=current_group, plot = plot)
        #self.model.layoutChanged.emit()
        self.model.add_child(current_group, new_item)
        self.treeView.expand(self.model.index(current_group_index, 0))

        
    @Slot()
    def deleteTrace(self):
        index = self.treeView.selectedIndexes()[0]
        if index.isValid():
            item = index.internalPointer()
            
            button = QtWidgets.QMessageBox.question(self, "Delete confirmation", "Do you want to delete the selected Trace/Group?")
            if button == QtWidgets.QMessageBox.StandardButton.Yes:
                if item.parent() == self.model.root_item:
                    # It's a group (parent is root)
                    for child in item.get_childs():
                        self.plotWidget.removeItem(child.plot)
                    self.model.removeRow(index.row(), index.parent())
                else:
                    # It's a single trace
                    self.plotWidget.removeItem(item.plot)
                    self.model.removeRow(index.row(), index.parent())
                
                self.model.layoutChanged.emit()
                self.treeView.clearSelection()
        else:
            QtWidgets.QMessageBox.warning(self, "No trace selected", "Please select a trace to delete")


    @Slot()
    def saveChecked(self):


        #Get the checked groups and save each group as a separate file
        checked_groups = [group for group in self.model.root_item.get_childs() if group.checked == Qt.CheckState.Checked]

        if len(checked_groups) == 0:
            QtWidgets.QMessageBox.warning(self, "No group selected", "Please select at least one group to save")
            return
        
        if len(checked_groups) != 1:
            QtWidgets.QMessageBox.warning(self, "Multiple groups selected", "Please select only one group to save")
            return
        
        #Ask the user for additional notes
        notes, ok = QtWidgets.QInputDialog.getText(self, "Additional notes", "Please enter additional notes for the file (optional)")  
        if not ok:
            return
        #Add the date and time  to the notes
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


        group = checked_groups[0]
        if len(group.get_childs()) == 0:
            QtWidgets.QMessageBox.warning(self, "No traces in group", "Please select at least one trace to save")
            return
        #Get the traces in the group
        traces = xr.merge([item.data for item in group.get_childs()])
        traces.attrs['Group'] = group.name
        for k,v in group.metadata.items():
            traces.attrs[k] = v
        print(f'Traces: {traces}')

        """Save all the checked traces to a file, asking for name and format"""

        #Ask the user for the name and format of the file
        file_type, ok = QtWidgets.QInputDialog.getItem(self, "File format", "Please select the file format\nSelect NetCDF for processing in python",
                                                       ["NetCDF", "CSV"], 0, False)
        if not ok:
            return
        if file_type == "NetCDF":
            name, ok = QtWidgets.QFileDialog.getSaveFileName(self, "Save file", "", "NetCDF Files (*.nc);;All Files (*)")
            if not ok:
                return
            if not name.endswith('.nc'):
                name += '.nc'

            traces.attrs['notes'] = notes
            traces.attrs['date'] = date
            traces.to_netcdf(f'{name}')
            QtWidgets.QMessageBox.information(self, "File saved", f"File saved as {name}")

        elif file_type == "CSV":
            self.save_to_csv(traces, notes, date)


    def save_to_csv(self, traces, notes, date):
        #Ask the user for the name of the file
        #Get the name and format from the user
        name, ok = QtWidgets.QFileDialog.getSaveFileName(self, "Save file", "", "CSV Files (*.csv);;All Files (*)")
        if not ok:
            return
        if not name.endswith('.csv'):
            name += '.csv'
        #Save the traces to the file
        with open(name, 'w', newline='') as f:
            writer = csv.writer(f)

            writer.writerow([f'Notes: {notes}  Date: {date}'])
            
            # Write header
            header = [f'Wavelength {name} (nm)']
            for trace in traces:
                name = trace
                header.extend([f'Power {name} (dBm)'])
            writer.writerow(header)
            
            # Prepare data
            data = []
            data.append(traces['wavelength'].values)
            for trace in traces:
                
                data.append(traces[trace].values)
            
            # Write data rows
            for row in zip(*data):
                writer.writerow(row)

    @Slot()
    def handle_check_state_changed(self, index, state):
        """Show or hide the trace in the plot"""
        trace = index.internalPointer()
        if trace.parent() == self.model.root_item:
            # It's a group (parent is root)
            # Check or uncheck all the traces in the group of the model

            
            for child in trace.get_childs():
                child.plot.setVisible(state)
        else:
            # It's a single trace
            trace.plot.setVisible(state)
        self.plotWidget.update()
        
    @Slot()
    def update_crosshair(self, e):
        pos = e[0]
        if self.plotWidget.sceneBoundingRect().contains(pos):
            mousePoint = self.plotWidget.getPlotItem().vb.mapSceneToView(pos)
            self.crosshair_v.setPos(mousePoint.x())
            self.crosshair_h.setPos(mousePoint.y())
            self.x_label.setText(f'X: {mousePoint.x():.2f}')
            self.y_label.setText(f'Y: {mousePoint.y():.2f}')
   

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion' )

    window = MainWindow()
    window.show()
    app.exec()