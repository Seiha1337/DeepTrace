"""Icône vectorielle native, rendue en ICO multi-résolutions pour Windows."""

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication


def main():
    app = QApplication.instance() or QApplication([])
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 256, size / 256)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#101b2b"))
        painter.drawRoundedRect(4, 4, 248, 248, 54, 54)
        painter.setPen(
            QPen(
                QColor("#62e0c7"),
                14,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        path = QPainterPath(QPointF(76, 65))
        path.lineTo(122, 65)
        path.cubicTo(207, 65, 207, 184, 122, 184)
        path.lineTo(76, 184)
        path.closeSubpath()
        painter.drawPath(path)
        painter.setPen(
            QPen(
                QColor("#e9f6fb"),
                11,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        path = QPainterPath(QPointF(52, 130))
        for x, y in ((92, 130), (107, 100), (126, 155), (143, 124), (204, 124)):
            path.lineTo(x, y)
        painter.drawPath(path)
        painter.end()
        icon.addPixmap(QPixmap.fromImage(image))
    output = Path(__file__).resolve().parents[1] / "src/deeptrace/assets/deeptrace.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Le plugin ICO de Qt encode une image ; PyInstaller en génère les entrées nécessaires.
    if not icon.pixmap(256, 256).save(str(output), "ICO"):
        raise OSError("Création de l'icône impossible")
    app.processEvents()
    print("Icône DeepTrace créée.")


if __name__ == "__main__":
    main()
