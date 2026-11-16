import sys
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

SIZE = 256


def main() -> int:
    app = QApplication(sys.argv)
    pix = QPixmap(SIZE, SIZE)
    pix.fill(Qt.GlobalColor.transparent)

    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(43, 46, 52))
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 40, 40)

    tiles = [
        (QColor(58, 63, 71), 44, 44),
        (QColor(58, 63, 71), 140, 44),
        (QColor(61, 143, 95), 44, 140),
        (QColor(58, 63, 71), 140, 140),
    ]
    p.setPen(QPen(QColor(90, 96, 106), 3))
    for color, x, y in tiles:
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x, y, 72, 72), 12, 12)

    check_pen = QPen(QColor(235, 245, 238), 8)
    check_pen.setBrush(QColor(235, 245, 238))
    check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(check_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(58, 176, 70, 190)
    p.drawLine(70, 190, 100, 158)
    p.end()

    out = Path(__file__).resolve().parent.parent / "packaging" / "icon-256.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not pix.save(str(out)):
        print(f"failed to save {out}", file=sys.stderr)
        return 1
    print(f"wrote {out}")

    ico = out.with_name("icon.ico")
    try:
        from PIL import Image
    except ImportError:
        print(f"Pillow not installed, skipping {ico}", file=sys.stderr)
        return 0
    with Image.open(out) as img:
        img.save(
            ico,
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
    print(f"wrote {ico}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
