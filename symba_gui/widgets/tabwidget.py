from PySide2.QtCore import Signal, QSize
from PySide2.QtWidgets import QTabBar, QPushButton, QTabWidget


class TabBarPlus(QTabBar):
    """Tab bar that has a plus button floating to the right of the tabs."""
    plusClicked = Signal()

    def __init__(self):
        super().__init__()

        # Plus Button
        self.plusButton = QPushButton("+", self)
        #self.plusButton.setFixedSize(20, 20)  # Small Fixed size
        self.plusButton.clicked.connect(self.plusClicked.emit)
        self._adjust() # Move to the correct location

        g = super().geometry()
        self.setGeometry(g.x(), g.y(), g.width() + 30, g.height())


    def sizeHint(self):
        """Return the size of the TabBar with increased width for the plus button."""
        sizeHint = super().sizeHint() 
        width = sizeHint.width()
        height = sizeHint.height()
        return QSize(width+30, height)

    def resizeEvent(self, event):
        """Resize the widget and make sure the plus button is in the correct location."""
        super().resizeEvent(event)
        self._adjust()

    def tabLayoutChange(self):
        """This virtual handler is called whenever the tab layout changes.
        If anything changes make sure the plus button is in the correct location.
        """
        super().tabLayoutChange()
        self._adjust()
        g = super().geometry()
        self.setGeometry(g.x(), g.y(), g.width() + 30, g.height())
    
    def _adjust(self):
        """Move the plus button to the correct location."""
        # Find the width of all of the tabs
        size = sum([self.tabRect(i).width() for i in range(self.count())])
        print(size)
        # size = 0
        for i in range(self.count()):
            print("Width:", self.tabRect(i).width())
        
        print(self.plusButton.pos())
        self.plusButton.move(160, 0)

        # Set the plus button location in a visible area
        # h = self.geometry().y()
        # w = self.width()
        # if size > w: # Show just to the left of the scroll buttons
        #     self.plusButton.move(w-54, h)
        # else:
        #     self.plusButton.move(size, h)
        
        # print(f"+ button is at {size}, {h}")


class TabWidget(QTabWidget):
    """Tab Widget that that can have new tabs easily added to it."""
    def __init__(self):
        super().__init__()

        # Tab Bar
        tabbar = TabBarPlus()
        self.setTabBar(tabbar)

        # Properties
        self.setMovable(True)
        self.setTabsClosable(True)

        # Signals
        tabbar.plusClicked.connect(self.addTab)
        #tabbar.tabMoved.connect(self.moveTab)
        self.tabCloseRequested.connect(self.removeTab)
