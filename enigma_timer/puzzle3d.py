"""Shared camera, materials and animation for every notation discipline."""
import math
import time
from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QPolygonF, QImage, QRadialGradient, QBrush, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import QStackedWidget
from .widgets import LiveCube3DWidget
from .notation import CUBE_EVENTS, notation_facelets
from .puzzle_mesh import NON_CUBES, scene, transition_scene, normal_of, tokens, move_spec
from .puzzles import _dot


class PolyPuzzle3DWidget(LiveCube3DWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.puzzle = "pyram"
        self.algorithm = ""
        self._transition = None
        self._mesh = scene(self.puzzle)
        # Camera animation is inherited; facelet transitions are never used here.
        self._facelets = "U"*54
        self._selected_move = None

    def set_puzzle(self,puzzle):
        if puzzle not in NON_CUBES:
            raise ValueError("Unsupported 3D puzzle")
        self.puzzle,self.algorithm = puzzle,""
        self._transition = None
        self._mesh = scene(puzzle)
        self._selected_move = None
        self.reset_view()
        self.update()

    def _home_view(self):
        if getattr(self,"puzzle",None)=="clock":
            return math.radians(-12),math.radians(8),0.0,1.0
        if getattr(self,"puzzle",None)=="pyram":
            return math.radians(-48),math.radians(12),0.0,1.0
        return super()._home_view()

    def set_algorithm(self,algorithm):
        target = scene(self.puzzle,algorithm)  # validate before changing current state
        if algorithm==self.algorithm:
            return
        previous = tokens(self.puzzle,self.algorithm)
        current = tokens(self.puzzle,algorithm)
        token,inverse = None,False
        if len(current)==len(previous)+1 and current[:-1]==previous:
            token = current[-1]
        elif len(previous)==len(current)+1 and previous[:-1]==current:
            token,inverse = previous[-1],True
        self._transition = None
        if token and self.isVisible() and not self._reduced_motion():
            self._transition = (self.algorithm,token,inverse,time.perf_counter(),.62)
        self.algorithm,self._mesh = algorithm,target
        if self._transition:
            self._ensure_frames()
        self.update()

    def set_highlight(self,move):
        self._selected_move = move
        self.update()

    def _advance_turn(self):
        super()._advance_turn()
        if self._transition:
            if self._reduced_motion() or time.perf_counter()-self._transition[3]>=self._transition[4]:
                self._transition = None
            else:
                self._ensure_frames()
        self.update()

    def hideEvent(self,event):
        self._transition = None
        super().hideEvent(event)

    def _paint_cube(self,painter):
        mesh = self._mesh
        if self._transition:
            source,token,inverse,began,duration = self._transition
            t = max(0,min(1,(time.perf_counter()-began)/duration))
            ease = t*t*t*(10-15*t+6*t*t)
            mesh = transition_scene(self.puzzle,source,token,ease,inverse)
        rect = self.rect().adjusted(10,10,-10,-10)
        scale = min(rect.width(),rect.height())/3.55*self._zoom
        scale *= 1.6 if self.puzzle=="pyram" else 1.15 if self.puzzle in ("minx","clock") else 1.0
        cx,cy = rect.center().x(),rect.center().y()
        if self._arrival is not None:
            t = min(1,max(0,(time.perf_counter()-self._arrival)/.28))
            scale *= .96+.04*(1-(1-t)**3)
            painter.setOpacity(.35+.65*t)
        shadow = QRadialGradient(QPointF(cx,cy+scale*.94),scale*.85)
        shadow.setColorAt(0,QColor(0,0,0,100))
        shadow.setColorAt(1,QColor(0,0,0,0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(shadow))
        painter.drawEllipse(QRectF(cx-scale*.85,cy+scale*.72,scale*1.7,scale*.35))
        selected = None
        if self._selected_move and self.puzzle in ("pyram","skewb","minx"):
            try:
                selected = move_spec(self.puzzle,self._selected_move)
            except (KeyError,ValueError):
                pass
        surfaces = []
        for surface in mesh:
            normal = normal_of(surface.points)
            view_normal = self._rotate(*normal)
            if view_normal[2]<=1e-7:
                continue
            view_points = [self._rotate(*p) for p in surface.points]
            depth = sum(p[2] for p in view_points)/len(view_points)
            points = QPolygonF([QPointF(cx+p[0]*scale,cy-p[1]*scale) for p in view_points])
            surfaces.append((depth,surface,points,view_normal))
        if self.puzzle=="clock":
            # A tilted, large face plate overlaps smaller coplanar dials.
            # Sorting only by centroid depth can paint it over the far dials.
            # These are surface details on one visible face: material layers
            # must be drawn in their physical stacking order.
            layers = {"case":0,"bezel":1,"dial":2,"tick":3,"hand":4,"hub":5,"pinSide":6,"pin":7}
            surfaces.sort(key=lambda item:(layers[item[1].key[0] if isinstance(item[1].key,tuple) else item[1].key],item[0]))
        else:
            surfaces.sort(key=lambda item:item[0])
        for _depth,surface,points,normal in surfaces:
            color = QColor(surface.color)
            brightness = .66+.34*max(0,_dot(normal,(-.28,.48,.83)))
            color.setRgb(*(min(255,int(c*brightness)) for c in (color.red(),color.green(),color.blue())))
            detailed = self.puzzle=="clock"
            painter.setPen(Qt.NoPen if detailed else QPen(QColor("#101011"),1))
            painter.setBrush(QColor("#0d0e10") if not detailed else color)
            painter.drawPolygon(points)
            if not detailed:
                center = QPointF(sum(p.x() for p in points)/len(points),sum(p.y() for p in points)/len(points))
                inset = .94 if self.puzzle=="pyram" else .965
                sticker = QPolygonF([center+(p-center)*inset for p in points])
                painter.setBrush(color)
                painter.setPen(QPen(QColor("#151517"),.8))
                path = QPainterPath()
                for index,point in enumerate(sticker):
                    previous,nxt = sticker[(index-1)%len(sticker)],sticker[(index+1)%len(sticker)]
                    entry,exit = point+(previous-point)*.075,point+(nxt-point)*.075
                    path.moveTo(entry) if index==0 else path.lineTo(entry)
                    path.quadTo(point,exit)
                path.closeSubpath()
                painter.drawPath(path)
                painter.save()
                painter.setClipPath(path)
                sheen = QLinearGradient(path.boundingRect().topLeft(),path.boundingRect().bottomRight())
                sheen.setColorAt(0,QColor(255,255,255,20))
                sheen.setColorAt(1,QColor(0,0,0,12))
                painter.fillRect(path.boundingRect(),QBrush(sheen))
                painter.restore()
                if selected and self._transition is None:
                    axis,threshold,complement,_angle = selected
                    dot = _dot(surface.center,axis)
                    if (dot<threshold if complement else dot>threshold):
                        painter.setPen(QPen(QColor(244,204,12,130),1.2))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawPath(path)


class Puzzle3DView(QStackedWidget):
    """One viewer API, including the established live-cube renderer."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.cube = LiveCube3DWidget()
        self.poly = PolyPuzzle3DWidget()
        self.addWidget(self.cube)
        self.addWidget(self.poly)
        self.puzzle = "333"
        self.algorithm = ""
        self.set_puzzle("333")

    def set_puzzle(self,puzzle):
        self.puzzle = puzzle
        self.algorithm = ""
        if puzzle in CUBE_EVENTS:
            self.cube.set_cube_size(CUBE_EVENTS[puzzle])
            self.cube.set_state(None)
            self.setCurrentWidget(self.cube)
            self.cube.reset_view()
        else:
            self.poly.set_puzzle(puzzle)
            self.setCurrentWidget(self.poly)
        self.set_algorithm("")

    def set_algorithm(self,algorithm):
        if self.puzzle in CUBE_EVENTS:
            from .cube import tokens as cube_tokens,invert
            old,new = cube_tokens(self.algorithm),cube_tokens(algorithm)
            move = new[-1] if len(new)==len(old)+1 and new[:-1]==old else invert(old[-1]) if len(old)==len(new)+1 and old[:-1]==new else None
            self.cube.set_state(notation_facelets(self.puzzle,algorithm),move=move)
        else:
            self.poly.set_algorithm(algorithm)
        self.algorithm = algorithm

    def set_highlight(self,move):
        self.currentWidget().set_highlight(move)

    def reset_view(self):
        self.currentWidget().reset_view()

    def _reduced_motion(self):
        return self.currentWidget()._reduced_motion()

    @property
    def cube_size(self):
        return self.cube.cube_size if self.puzzle in CUBE_EVENTS else None

    @property
    def _facelets(self):
        return self.cube._facelets if self.puzzle in CUBE_EVENTS else None


def puzzle_image(puzzle,algorithm,size=144):
    view = PolyPuzzle3DWidget()
    view.resize(size,size)
    view.set_puzzle(puzzle)
    view.set_algorithm(algorithm)
    view._arrival = None
    result = QImage(size,size,QImage.Format_ARGB32_Premultiplied)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.Antialiasing)
    view._paint_cube(painter)
    painter.end()
    view.deleteLater()
    return result
