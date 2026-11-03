"""Labeled, separated teaching views for corner-turning puzzles."""
import math
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QImage, QPainter, QPen, QPolygonF
from .i18n import pick


def corner_puzzle_image(puzzle, moves, size):
    from .puzzles import Pyraminx, Skewb, _NET_POS, _SKEWB_FACES
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor("#101010"), max(1, size / 180)))
    font = QFont()
    font.setPixelSize(max(9, int(size * 0.035)))
    font.setBold(True)
    p.setFont(font)
    if puzzle == "pyram":
        model = Pyraminx().apply(moves)
        h = math.sqrt(3) / 2
        frames = [((0, 0), (-.5, h), (.5, h)), ((0, 0), (-.5, h), (-1, 0)),
                  ((0, 0), (.5, h), (1, 0)), ((-.5, h), (.5, h), (0, 2*h))]
        labels = [pick(("Front · U at top", "Спереди · U сверху")), pick(("Left", "Слева")),
                  pick(("Right", "Справа")), pick(("Bottom / back", "Снизу / сзади"))]
        for face, (a, b, c) in enumerate(frames):
            ox, oy = (face % 2) * .5, (face // 2) * .5
            det = (b[0]-a[0])*(c[1]-a[1]) - (c[0]-a[0])*(b[1]-a[1])
            for index in range(face * 9, (face + 1) * 9):
                pts = []
                for x, y in model.slots[index][1]:
                    u = ((x-a[0])*(c[1]-a[1]) - (y-a[1])*(c[0]-a[0])) / det
                    v = ((b[0]-a[0])*(y-a[1]) - (b[1]-a[1])*(x-a[0])) / det
                    pts.append(QPointF((ox+.05+.4*(.5-.5*u+.5*v))*size,
                                       (oy+.035+.37*(u+v))*size))
                p.setPen(QPen(QColor("#101010"), max(1, size / 180)))
                p.setBrush(QColor(model.colors[index]))
                p.drawPolygon(QPolygonF(pts))
            p.setPen(QColor("#eeeeee"))
            p.drawText(QRectF(ox*size, (oy+.42)*size, .5*size, .06*size), Qt.AlignCenter, labels[face])
    else:
        model = Skewb().apply(moves)
        faces = list(_SKEWB_FACES)
        for face in ("U", "F", "R"):
            offset = faces.index(face) * 5
            nx, ny = _NET_POS[face]
            for index in range(offset, offset+5):
                points = []
                for x, y in model.slots[index][1]:
                    u, v = x-nx*1.08, y-ny*1.08
                    if face == "U":
                        x3, y3, z3 = 2*u-1, 1, 2*v-1
                    elif face == "F":
                        x3, y3, z3 = 2*u-1, 1-2*v, 1
                    else:
                        x3, y3, z3 = 1, 1-2*v, 1-2*u
                    px = (x3-z3)*.866
                    py = (x3+z3)*.5-y3
                    points.append(QPointF((.5+px*.24)*size, (.5+py*.24)*size))
                p.setBrush(QColor(model.colors[index]))
                p.drawPolygon(QPolygonF(points))
        p.setPen(QColor("#eeeeee"))
        p.drawText(QRectF(0, size*.92, size, size*.07), Qt.AlignCenter,
                   pick(("U above · F left · R right", "U сверху · F слева · R справа")))
    p.end()
    return image
