"""Converts units in inches to units in pixels using logical dpi of the application."""
from typing import Union
from functools import lru_cache
from PySide2.QtCore import QPoint, QPointF, QSize, QSizeF, QRect, QRectF
from PySide2.QtWidgets import QApplication, QWidget


@lru_cache(maxsize=None)
def logicalDpi():
    """Return this application's logical dpi"""
    # Check if the application has been created. If the application has not been created, dpi cannot be measured.
    if QApplication.instance() is None:
        raise RuntimeError("dpi(): Must construct a QApplication before measuring dpi")

    w = QWidget()
    return w.logicalDpiX()

@lru_cache(maxsize=None)
def physicalDpi():
    """Return this application's logical dpi"""
    # Check if the application has been created. If the application has not been created, dpi cannot be measured.
    if QApplication.instance() is None:
        raise RuntimeError("dpi(): Must construct a QApplication before measuring dpi")

    w = QWidget()
    return w.physicalDpiX()

@lru_cache(maxsize=None)
def logicalDpp():
    """Return this application's logical dots-per-point (font point)"""
    return logicalDpi() / 72

@lru_cache(maxsize=None)
def physicalDpp():
    """Return this application's logical dots-per-point (font point)"""
    return physicalDpi() / 72

def scale(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF], factor):
    """Scale a value like an int, a float, a QPoint, a QRect, or other by some factor. Return a new value."""
    if type(value) is QPoint:
        return QPoint(round(value.x() * factor), round(value.y() * factor))

    if type(value) is QPointF:
        return QPointF(value.x() * factor, value.y() * factor)

    if type(value) is QSize:
        return QSize(round(value.width() * factor), round(value.height() * factor))

    if type(value) is QSizeF:
        return QSizeF(value.width() * factor, value.height() * factor)
    
    if type(value) is QRect:
        return QRect(round(value.topLeft() * factor), round(value.bottomRight() * factor))

    if type(value) is QRectF:
        return QRectF(value.topLeft() * factor, value.bottomRight() * factor)

    return round(value * factor)

def inchToLogicalPx(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in inches to a value in logical pixels."""
    return scale(value, logicalDpi())

def logicalPxToInch(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in logical pixels to a value in inches."""
    return scale(value, 1/logicalDpi())

def inchToPhysicalPx(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in inches to a value in physical pixels."""
    return scale(value, logicalDpi())

def physicalPxToInch(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in physical pixels to a value in inches."""
    return scale(value, 1/logicalDpi())

def ptToLogicalPx(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in points to a value in logical pixels."""
    return scale(value, logicalDpp())

def logicalPxToPt(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in logical pixels to a value in points."""
    return scale(value, 1/logicalDpp())

def ptToPhysicalPx(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in points to a value in physical pixels."""
    return scale(value, physicalDpp())

def physicalPxToPt(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF]):
    """Convert a value in physical pixels to a value in points."""
    return scale(value, 1/physicalDpp())

def fontSizesToLogicalPx(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF], font=None):
    """Convert a value in font-sizes to a value in logicsl pixels.
    This is useful when you must match something like an icon to the width of the button. In this case, logical DPI is
    unreliable, because Windows often returns a logical DPI of 96 and uses small font sizes, while MacOS returns a
    logical DPI of 72 and uses bigger font sizes.
    When font is None, application default font is used instead.
    """
    dpp = logicalDpp()
    if font is None:
        fontSize = QApplication.instance().font().pointSizeF()
    else:
        fontSize = font.pointSizeF()

    return scale(value, dpp * fontSize)

def logicalPxToFontSizes(value: Union[int, float, QPoint, QPointF, QSize, QSizeF, QRect, QRectF], font=None):
    """Convert a value in physical pixels to a value in font sizes."""
    dpp = logicalDpp()
    if font is None:
        fontSize = QApplication.instance().font().pointSizeF()
    else:
        fontSize = font.pointSizeF()
    
    return scale(value, 1/(dpp * fontSize))
