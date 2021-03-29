from PySide2.QtWidgets import QWidget
from pyqtgraph import PlotWidget


def chart(directory: str) -> QWidget:
    widget = PlotWidget()
    # Create your chart widget here
    return widget
