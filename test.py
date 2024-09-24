import sys
from PySide6.QtCore import Qt, QModelIndex, QAbstractItemModel
from PySide6.QtWidgets import QApplication, QTreeView, QVBoxLayout, QWidget

class TreeItem:
    """Represents each item in the tree, which could be a root or child."""
    def __init__(self, data, parent=None):
        self.data = data  # This holds the item data (name in this case)
        self.parent_item = parent  # The parent of this item
        self.child_items = []  # A list of child items
        self.checked = Qt.Checked  # Default to checked

    def append_child(self, child):
        """Adds a child to the current item."""
        self.child_items.append(child)

    def child(self, row):
        """Returns the child at the specified row."""
        return self.child_items[row]

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
    """Custom model for representing a list of dictionaries in a tree."""
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.root_item = TreeItem("Root")
        self.setup_model_data(data)

    def setup_model_data(self, lists):
        """Sets up the hierarchical model data from the input lists."""
        for idx, lst in enumerate(lists, 1):
            root_item = TreeItem(f'List {idx}', self.root_item)
            self.root_item.append_child(root_item)

            for entry in lst:
                child_item = TreeItem(entry['name'], root_item)
                root_item.append_child(child_item)

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

    def data(self, index, role=Qt.DisplayRole):
        """Returns the data stored under the given role for the item at index."""
        if not index.isValid():
            return None
        if role != Qt.DisplayRole:
            return None
        item = index.internalPointer()
        return item.data_at_column(index.column())

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
    
    def setData(self, index, value, role=Qt.EditRole):
        """Sets the role data for the item at index to value."""
        if role not in (Qt.EditRole, Qt.CheckStateRole):
            return False

        if not index.isValid():
            return False

        item = index.internalPointer()
        if role == Qt.EditRole:
            item.data = value
        elif role == Qt.CheckStateRole:
            item.checked = value
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
            return item.data
        elif role == Qt.CheckStateRole:
            return Qt.Checked if item.checked else Qt.Unchecked


        return None        
   

class TreeViewExample(QWidget):
    def __init__(self):
        super().__init__()

        # Layout
        layout = QVBoxLayout(self)

        # QTreeView
        self.tree_view = QTreeView()

        # Sample data: 3 lists containing dictionaries with 'name' keys
        list1 = [{'name': 'Alice'}, {'name': 'Bob'}, {'name': 'Charlie'}]
        list2 = [{'name': 'David'}, {'name': 'Eve'}, {'name': 'Frank'}]
        list3 = [{'name': 'Grace'}, {'name': 'Heidi'}, {'name': 'Ivan'}]

        # Create the model
        self.model = TreeModel([list1, list2, list3])

        # Set the model for the QTreeView
        self.tree_view.setModel(self.model)

        # Add the QTreeView to the layout
        layout.addWidget(self.tree_view)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    window = TreeViewExample()
    window.setWindowTitle('QTreeView with QAbstractItemModel Example')
    window.resize(400, 300)
    window.show()

    sys.exit(app.exec())
