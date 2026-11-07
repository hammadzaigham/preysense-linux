"""Original PreySense icons with native raster backing and sharp HiDPI SVG rendering.

QIcon keeps the complete PNG source; consumers request the target logical size
and DPR together instead of first shrinking to16pixels and then enlarging it.
Theme color is resolved at call time so light/dark switches keep the same assets.
"""
import math
from pathlib import Path
from PySide6.QtCore import QSize, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

FRONTEND_ROOT=Path(__file__).resolve().parent/'assets'
RESOURCE_ROOT=FRONTEND_ROOT/'Resources'
SVG_ROOT=Path(__file__).resolve().parent/'assets'


def _ratio(dpr=None,screen=None):
    if dpr is None:
        app=QGuiApplication.instance()
        target=screen or (app.primaryScreen() if app else None)
        dpr=target.devicePixelRatio() if target else 1.0
    if isinstance(dpr,bool):raise ValueError('DPR must be a positive finite number')
    try:value=float(dpr)
    except (TypeError,ValueError):raise ValueError('DPR must be a positive finite number') from None
    if not math.isfinite(value) or value<=0:raise ValueError('DPR must be a positive finite number')
    return value


def _logical_size(size):
    if type(size) is not int or size<=0:raise ValueError('Icon size must be a positive integer')
    return QSize(size,size)


def _tint(pixmap):
    from appearance import icon_color
    painter=QPainter(pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(),QColor(icon_color()))
    painter.end()
    return pixmap


def themed_icon(filename,size=16):
    """Return a themed QIcon retaining the original PNG's full pixel dimensions.

    ``size`` is accepted for existing call sites but never used to pre-resample
    the source. QIcon selects/resamples its full backing at the final target DPR.
    """
    _logical_size(size)
    pixmap=QPixmap(str(RESOURCE_ROOT/filename))
    if pixmap.isNull():return QIcon()
    return QIcon(_tint(pixmap))


def themed_pixmap(filename,size=16,dpr=None,*,screen=None):
    """Request logical size and target-screen DPR in one QIcon operation."""
    return themed_icon(filename,size).pixmap(_logical_size(size),_ratio(dpr,screen))


def svg_icon_pixmap(path,size=16,dpr=None,*,screen=None):
    """Render an original SVG directly to its physical backing, without tint."""
    _logical_size(size);ratio=_ratio(dpr,screen)
    renderer=QSvgRenderer(str(path))
    if not renderer.isValid():return QPixmap()
    physical=max(1,math.ceil(size*ratio))
    pixmap=QPixmap(physical,physical);pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.setAspectRatioMode(Qt.KeepAspectRatio)
    renderer.render(painter,QRectF(0,0,physical,physical))
    painter.end()
    # Set DPR after rendering: renderer coordinates above are physical pixels.
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def svg_mode_pixmap(name,size=18,dpr=None,*,screen=None):
    """Render the existing monochrome mode path at the final pixel density."""
    pixmap=svg_icon_pixmap(SVG_ROOT/f'{name}.svg',size,dpr,screen=screen)
    if pixmap.isNull():return pixmap
    return _tint(pixmap)
