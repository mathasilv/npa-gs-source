# src/npags/gui/canvas_items.py

"""
Componentes graficos para a cena da Dashboard (Scene e Items).
"""

from __future__ import annotations


from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsProxyWidget,
    QGraphicsScene,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from npags.gui.styles import THEME_COLORS

GRID_SIZE = 20

class SmartDashboardItem(QGraphicsProxyWidget):
    """
    Encapsula widgets normais (graficos, cards) para viverem na QGraphicsScene.
    Adiciona funcionalidades de arrasto por titulo e redimensionamento manual.
    """

    def __init__(self, widget: QWidget, title: str = "Widget") -> None:
        super().__init__()
        widget.show()
        self.setWidget(widget)
        self.resize(widget.width(), widget.height())

        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

        self.title = title
        self.snap_enabled = True
        self._mode: str | None = None
        self._resize_handle_size = 20
        self._title_bar_height = 25

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent | None) -> None:
        """Altera o cursor conforme a zona de interacao."""
        if event is None:
            return
        pos = event.pos()
        rect = self.boundingRect()

        in_resize = (pos.x() > rect.width() - self._resize_handle_size and
                     pos.y() > rect.height() - self._resize_handle_size)

        if in_resize:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif pos.y() < self._title_bar_height:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Inicia a operacao de mover ou redimensionar."""
        if event is None:
            return
        pos = event.pos()
        rect = self.boundingRect()

        # Detecta redimensionamento (canto inferior direito)
        if (pos.x() > rect.width() - self._resize_handle_size and
            pos.y() > rect.height() - self._resize_handle_size):
            self._mode = 'RESIZE'
            event.accept()
            return

        # Detecta movimento (barra de titulo)
        if pos.y() < self._title_bar_height:
            self._mode = 'MOVE'
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Fora das areas de controle: passa para o widget interno
        self._mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Executa a transformacao geometrica do item."""
        if event is None:
            return
        if self._mode == 'MOVE':
            delta = event.scenePos() - event.lastScenePos()
            self.setPos(self.pos() + delta)
            event.accept()
        elif self._mode == 'RESIZE':
            delta = event.scenePos() - event.lastScenePos()
            new_w = max(120, self.size().width() + delta.x())
            new_h = max(80, self.size().height() + delta.y())
            self.resize(new_w, new_h)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent | None) -> None:
        """Aplica o alinhamento magnetico ao soltar o item."""
        if self._mode == 'MOVE' and self.snap_enabled:
            p = self.pos()
            new_x = round(p.x() / GRID_SIZE) * GRID_SIZE
            new_y = round(p.y() / GRID_SIZE) * GRID_SIZE
            self.setPos(new_x, new_y)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._mode == 'RESIZE' and self.snap_enabled:
            s = self.size()
            new_w = round(s.width() / GRID_SIZE) * GRID_SIZE
            new_h = round(s.height() / GRID_SIZE) * GRID_SIZE
            self.resize(new_w, new_h)

        self._mode = None
        super().mouseReleaseEvent(event)

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionGraphicsItem | None,
        widget: QWidget | None = None,
    ) -> None:
        """Desenha elementos visuais auxiliares."""
        if painter is None:
            return
        super().paint(painter, option, widget)

        if self.isSelected():
            painter.setPen(QPen(QColor(THEME_COLORS['selection']), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(self.boundingRect())

        rect = self.boundingRect()
        s = self._resize_handle_size
        painter.setPen(Qt.PenStyle.NoPen)

        grip_color = QColor(THEME_COLORS['accent'])
        grip_color.setAlpha(100)
        painter.setBrush(QBrush(grip_color))

        triangle = QPolygonF([
            QPointF(rect.width(), rect.height()),
            QPointF(rect.width() - s, rect.height()),
            QPointF(rect.width(), rect.height() - s)
        ])
        painter.drawPolygon(triangle)


class BlueprintScene(QGraphicsScene):
    """Area de desenho infinita com fundo de grade dinamico."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.grid_visible = True
        self.setSceneRect(0, 0, 4000, 4000)
        self.setBackgroundBrush(QBrush(QColor(THEME_COLORS['background'])))

    def drawBackground(self, painter: QPainter | None, rect: QRectF) -> None:
        """Desenha a grade de pontos."""
        if painter is None:
            return
        super().drawBackground(painter, rect)
        if not self.grid_visible:
            return

        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)

        points = []
        for x in range(left, int(rect.right()), GRID_SIZE):
            for y in range(top, int(rect.bottom()), GRID_SIZE):
                points.append(QPointF(x, y))

        if points:
            painter.setPen(QPen(QColor(THEME_COLORS['grid']), 2))
            painter.drawPoints(QPolygonF(points))
