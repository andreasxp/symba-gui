"""Converts units in inches to units in pixels using logical dpi of the application."""
from typing import Union
from functools import cache
from PySide2.QtCore import QPoint, QPointF, QSize, QSizeF, QRect, QRectF
from PySide2.QtWidgets import QApplication, QWidget


@cache
def dpi():
    """Return this application's logical dpi"""
    # Check if the application has been created. If the application has not been created, dpi cannot be measured.
    if QApplication.instance() is None:
        raise RuntimeError("dpi(): Must construct a QApplication before measuring dpi")

    w = QWidget()
    physical_dpi = w.physicalDpiX()
    logical_dpi = w.logicalDpiX()

    if logical_dpi == 72:
        # The function assumes that a dpi of 72 is fake. (like the dpi reported on MacOS)
        # In this case, return physical dpi.
        return physical_dpi
    return logical_dpi

def inches_to_pixels(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in inches to a value in pixels.
    Supports values: plain numbers, QPoint, QPointF, QSize, QSizeF, QRect, QRectF.
    """
    if type(value) is QRect:
        return QRect(
            value.topLeft() * dpi(),
            value.bottomRight() * dpi()
        )

    if type(value) is QRectF:
        return QRectF(
            value.topLeft() * dpi(),
            value.bottomRight() * dpi()
        )

    return round(value * dpi())


def pixels_to_inches(value):
    """Convert a value in pixels to a value in inches."""
    if type(value) is QRect:
        return QRect(
            value.topLeft() / dpi(),
            value.bottomRight() / dpi()
        )

    if type(value) is QRectF:
        return QRectF(
            value.topLeft() / dpi(),
            value.bottomRight() / dpi()
        )

    return value / dpi()
