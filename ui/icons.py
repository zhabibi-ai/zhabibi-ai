"""All icons are inline SVG (24x24 viewBox) rendered to QPixmap/QIcon. No external files."""
from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_FILE = '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'

_P = {
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>',
    "file": _FILE + '<path d="M9 13h6M9 17h6"/>',
    "doc": _FILE + '<path d="M9 13h6M9 17h4"/>',
    "list": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
    "music": '<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4M12 19v4M1 12h4M19 12h4"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
    "play": '<path d="M7 4l13 8-13 8z"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "folder": '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "min": '<path d="M5 12h14"/>',
    "max": '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron": '<path d="M6 9l6 6 6-6"/>',
    "volume": '<path d="M4 9v6h4l5 4V5L8 9z"/><path d="M16 9a4 4 0 0 1 0 6"/>',
    "sparkle": '<path d="M12 2l2.2 6.3L21 10l-6.8 1.7L12 18l-2.2-6.3L3 10l6.8-1.7z"/><path d="M19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
    "check": '<path d="M5 12l5 5L20 7"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "compare": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 8v8M8 12h8"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5"/><path d="M5 20h14"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "pin": '<path d="M12 21v-6"/><path d="M8 4h8l-1 6 3 3H6l3-3z"/>',
    "locate": '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "thermo": '<path d="M14 14.5V5a2 2 0 0 0-4 0v9.5a4 4 0 1 0 4 0z"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "paste": '<rect x="6" y="5" width="12" height="16" rx="2"/><path d="M9 5V3h6v2M9 11h6M9 15h6"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2 6"/><path d="M20 4v7h-7"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "wave": '<path d="M3 12h1M7 8v8M11 4v16M15 7v10M19 10v4M22 12h0"/>',
}
_FILLED = {"play", "pause"}


@lru_cache(maxsize=None)
def pixmap(name: str, color: str = "#CFE3D6", size: int = 20, dpr: float = 2.0) -> QPixmap:
    if name in _FILLED:
        attrs = f'fill="{color}" stroke="none"'
    else:
        attrs = (f'fill="none" stroke="{color}" stroke-width="1.8" '
                 'stroke-linecap="round" stroke-linejoin="round"')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" {attrs}>{_P[name]}</svg>'
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icon(name: str, color: str = "#CFE3D6", size: int = 20, hover: str | None = None) -> QIcon:
    ic = QIcon()
    ic.addPixmap(pixmap(name, color, size), QIcon.Normal)
    ic.addPixmap(pixmap(name, hover or color, size), QIcon.Active)
    return ic
