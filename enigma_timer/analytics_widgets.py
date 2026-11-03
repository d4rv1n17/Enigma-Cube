"""Compact, interactive session analytics in the shared application palette."""
import math
import statistics

from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget, QToolTip

from . import theme
from .i18n import tr
from .stats import INF, fmt_ms, fmt_avg


def finite(value):
    return value is not None and math.isfinite(value)


def nice_step(span, count):
    raw = max(1, span / max(1, count))
    power = 10 ** math.floor(math.log10(raw))
    return next(m * power for m in (1, 2, 2.5, 5, 10) if m * power >= raw)


class TimeChart(QWidget):
    solve_clicked = pyqtSignal(int)
    MAX_POINTS = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self._singles, self._ao5, self._ao12 = [], [], []
        self._offset = 0
        self._decimals = 2
        self._geom = None
        self._hover = None

    def set_data(self, singles, ao5, ao12, decimals=2):
        self._offset = max(0, len(singles) - self.MAX_POINTS)
        self._singles = list(singles[self._offset:])
        self._ao5 = list(ao5[self._offset:])
        self._ao12 = list(ao12[self._offset:])
        self._decimals = decimals
        self._hover = None
        self._geom = None
        QToolTip.hideText()
        self.update()

    def _finite(self):
        return [v for seq in (self._singles, self._ao5, self._ao12)
                for v in seq if finite(v)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(theme.ui_font())
        font.setPixelSize(11)
        p.setFont(font)
        values = self._finite()
        if not self._singles or not values:
            self._geom = None
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(), Qt.AlignCenter, tr("not_enough_data"))
            return
        step = nice_step(max(1000, max(values) - min(values)), 4)
        lo = max(0, math.floor((min(values) - step * .2) / step) * step)
        hi = math.ceil((max(values) + step * .2) / step) * step
        if hi <= lo:
            hi = lo + step
        label_width = max(p.fontMetrics().horizontalAdvance(fmt_ms(v, 1))
                          for v in (lo, hi)) + 8
        plot = QRectF(label_width, 34, max(10, self.width()-label_width-12),
                      max(10, self.height()-66))
        n = len(self._singles)
        def X(i):
            return plot.center().x() if n == 1 else plot.left()+i*plot.width()/(n-1)
        def Y(v):
            return plot.bottom()-(v-lo)/(hi-lo)*plot.height()
        self._geom = (plot, n, X)
        ticks = int(round((hi-lo)/step))
        for k in range(ticks+1):
            v = lo+k*step
            y = Y(v)
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.DotLine))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(0, y-9, label_width-8, 18),
                       Qt.AlignRight | Qt.AlignVCenter, fmt_ms(v, 1))
        for i in sorted({0, (n-1)//2, n-1}):
            x = min(plot.right()-18, max(plot.left()+18, X(i)))
            p.drawText(QRectF(x-25, plot.bottom()+8, 50, 18), Qt.AlignCenter,
                       "#%d" % (i+1+self._offset))
        legend_x = plot.left()
        for label, color, style in ((tr("chart_single"), theme.MUTED, Qt.SolidLine),
                                     ("ao5", theme.ACCENT, Qt.SolidLine),
                                     ("ao12", theme.TEXT, Qt.DashLine)):
            p.setPen(QPen(QColor(color), 2, style))
            p.drawLine(QPointF(legend_x, 13), QPointF(legend_x+12, 13))
            p.setPen(QColor(theme.MUTED))
            p.drawText(QPointF(legend_x+17, 17), label)
            legend_x += p.fontMetrics().horizontalAdvance(label)+30
        for seq, color, width, style in (
                (self._singles, theme.MUTED, 1.5, Qt.SolidLine),
                (self._ao12, theme.TEXT, 1.8, Qt.DashLine),
                (self._ao5, theme.ACCENT, 2.4, Qt.SolidLine)):
            path = QPainterPath()
            started = False
            for i, v in enumerate(seq):
                if not finite(v):
                    started = False
                    continue
                pt = QPointF(X(i), Y(v))
                path.lineTo(pt) if started else path.moveTo(pt)
                started = True
            p.setPen(QPen(QColor(color), width, style, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
            if len(seq) <= 80:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                for i, v in enumerate(seq):
                    if finite(v):
                        p.drawEllipse(QPointF(X(i), Y(v)), 2.5, 2.5)
        p.setPen(QPen(QColor(theme.DNF_RED), 1.7))
        for i, v in enumerate(self._singles):
            if v == INF:
                x, y = X(i), plot.top()+5
                p.drawLine(QPointF(x-3,y-3), QPointF(x+3,y+3))
                p.drawLine(QPointF(x-3,y+3), QPointF(x+3,y-3))
        if self._hover is not None:
            i = self._hover
            p.setPen(QPen(QColor(theme.ACCENT), 1, Qt.DashLine))
            p.drawLine(QPointF(X(i),plot.top()), QPointF(X(i),plot.bottom()))
            if finite(self._singles[i]):
                p.setBrush(QColor(theme.PANEL))
                p.setPen(QPen(QColor(theme.ACCENT),2))
                p.drawEllipse(QPointF(X(i),Y(self._singles[i])),4.5,4.5)

    def _index_at(self, pos):
        if not self._geom:
            return None
        plot, n, _ = self._geom
        if not plot.contains(QPointF(pos)):
            return None
        return max(0,min(n-1,round((pos.x()-plot.left())/plot.width()*(n-1))))

    def mouseMoveEvent(self, event):
        self._hover = self._index_at(event.pos())
        self.update()
        i = self._hover
        if i is None:
            QToolTip.hideText()
            return
        lines = ["#%d · %s" % (i+1+self._offset,fmt_ms(self._singles[i],self._decimals))]
        for label, seq in (("ao5",self._ao5),("ao12",self._ao12)):
            if i < len(seq) and seq[i] is not None:
                lines.append("%s  %s" % (label,fmt_avg(seq[i],self._decimals)))
        lines.append(tr("solve_click_hint"))
        QToolTip.showText(event.globalPos(), "\n".join(lines), self)

    def mouseReleaseEvent(self, event):
        i = self._index_at(event.pos())
        if event.button() == Qt.LeftButton and i is not None:
            QToolTip.hideText()
            self.solve_clicked.emit(i+self._offset)

    def leaveEvent(self, event):
        self._hover = None
        QToolTip.hideText()
        self.update()


class TimeHistogram(QWidget):
    MIN_SOLVES = 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self._values = []
        self._dnfs = 0
        self._bars = []

    def set_data(self, singles):
        self._values = [v for v in singles if finite(v)]
        self._dnfs = sum(v == INF for v in singles)
        self._bars = []
        QToolTip.hideText()
        self.update()

    def buckets(self, max_rows=8):
        if not self._values:
            return []
        lo, hi = min(self._values),max(self._values)
        step = nice_step(max(1000,hi-lo+1),max(1,max_rows-1))
        start = math.floor(lo/step)*step
        count = int((hi-start)//step)+1
        bins = [0]*count
        for v in self._values:
            bins[min(count-1,int((v-start)//step))] += 1
        return [(start+i*step,start+(i+1)*step,c) for i,c in enumerate(bins)]

    def paintEvent(self, event):
        p=QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f=QFont(theme.ui_font())
        f.setPixelSize(11)
        p.setFont(f)
        self._bars=[]
        if not self._values:
            p.setPen(QColor(theme.MUTED))
            p.drawText(self.rect(),Qt.AlignCenter,tr("not_enough_data"))
            return
        left,right=8,self.width()-10
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(left,4,right-left,20),Qt.AlignLeft | Qt.AlignVCenter,
                   tr("chart_median")+"  "+fmt_ms(statistics.median(self._values)))
        total=len(self._values)
        p.setPen(QColor(theme.MUTED))
        p.drawText(QRectF(left,25,right-left,18),Qt.AlignLeft | Qt.AlignVCenter,
                   tr("chart_sample") % (total,self._dnfs))
        rows=self.buckets(max(2,min(8,int((self.height()-60)/39))))
        max_count=max(c for _,_,c in rows)
        row_h=min(46,max(27,(self.height()-60)/len(rows)))
        for i,(start,end,count) in enumerate(rows):
            y=54+i*row_h
            decimals=1 if start % 1000 or end % 1000 else 0
            def label(v):
                return fmt_ms(v,1) if decimals else fmt_ms(v).split('.')[0]
            text=label(start)+" – "+label(end)
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(left,y,right-left,16),Qt.AlignLeft | Qt.AlignVCenter,text)
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(left,y,right-left,16),Qt.AlignRight | Qt.AlignVCenter,
                       "%d · %.0f%%" % (count,100*count/total))
            track=QRectF(left,y+21,right-left,max(4,min(8,row_h-24)))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.BORDER))
            p.drawRoundedRect(track,3,3)
            if count:
                color=QColor(theme.ACCENT)
                color.setAlpha(255 if count==max_count else 160)
                p.setBrush(color)
                p.drawRoundedRect(QRectF(track.left(),track.top(),track.width()*count/max_count,track.height()),3,3)
            self._bars.append((QRectF(left,y,right-left,row_h),start,end,count))

    def mouseMoveEvent(self,event):
        for rect,start,end,count in self._bars:
            if rect.contains(QPointF(event.pos())):
                QToolTip.showText(event.globalPos(),"%s ≤ t < %s\n%s: %d" %
                                  (fmt_ms(start),fmt_ms(end),tr("solves"),count),self)
                return
        QToolTip.hideText()

    def leaveEvent(self,event):
        QToolTip.hideText()
