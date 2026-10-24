"""SF Symbols as Qt icons: AppKit draws the symbol, Qt tints it.

set_symbol() keeps the button's text glyph when AppKit or the symbol is
missing, so a button is never blank.
"""
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

try:
    import AppKit
except Exception:  # pragma: no cover - pyobjc missing outside macOS
    AppKit = None

_SCALE = 2.0   # drawn at 2x and marked so, sharp on Retina and fine on 1x
_cache: dict = {}


def symbol_pixmap(name: str, point_size: float, color: str, bold: bool = False) -> QPixmap | None:
    key = (name, point_size, color, bold)
    if key in _cache:
        return _cache[key]
    pm = _render(name, point_size, color, bold)
    _cache[key] = pm
    return pm


def _render(name: str, point_size: float, color: str, bold: bool) -> QPixmap | None:
    if AppKit is None:
        return None
    try:
        img = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
        if img is None:
            return None
        weight = AppKit.NSFontWeightSemibold if bold else AppKit.NSFontWeightMedium
        cfg = AppKit.NSImageSymbolConfiguration.configurationWithPointSize_weight_(point_size, weight)
        img = img.imageWithSymbolConfiguration_(cfg)
        w, h = img.size()
        rep = AppKit.NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
            None, int(w * _SCALE), int(h * _SCALE), 8, 4, True, False,
            AppKit.NSDeviceRGBColorSpace, 0, 0)
        rep.setSize_((w, h))
        AppKit.NSGraphicsContext.saveGraphicsState()
        AppKit.NSGraphicsContext.setCurrentContext_(
            AppKit.NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))
        img.drawInRect_(((0, 0), (w, h)))
        AppKit.NSGraphicsContext.restoreGraphicsState()
        data = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, None)
        pm = QPixmap()
        if not pm.loadFromData(bytes(data), "PNG"):
            return None
    except Exception as e:
        print(f"[symbols] {name} failed: {e}", flush=True)
        return None
    # The symbol is drawn black (a template image); recolor its pixels.
    p = QPainter(pm)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    pm.setDevicePixelRatio(_SCALE)
    return pm


def set_symbol(button, name: str, point_size: float, color: str, bold: bool = False) -> None:
    """Show SF Symbol `name` on `button` in place of its text glyph."""
    pm = symbol_pixmap(name, point_size, color, bold)
    if pm is None:
        return
    button.setText("")
    button.setIcon(QIcon(pm))
    button.setIconSize(QSize(round(pm.width() / _SCALE), round(pm.height() / _SCALE)))
