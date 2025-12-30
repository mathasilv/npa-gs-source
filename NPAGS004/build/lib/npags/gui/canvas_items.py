# src/npags/gui/canvas_items.py

"""
Componentes gráficos para a cena da Dashboard (Scene e Items).
Refatorado: Cores centralizadas no styles.py e remoção de estilos manuais.
"""

from PyQt6.QtWidgets import QGraphicsProxyWidget, QGraphicsItem, QGraphicsScene
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QBrush, QPen, QPolygonF
from npags.gui.styles import THEME_COLORS # Importação da Paleta

GRID_SIZE = 20

class SmartDashboardItem(QGraphicsProxyWidget):
    """
    Encapsula widgets normais (gráficos, cards) para viverem na QGraphicsScene.
    Adiciona funcionalidades de arrasto por título e redimensionamento manual.
    """
    def __init__(self, widget, title="Widget"):
        super().__init__()
        widget.show()
        self.setWidget(widget)
        self.resize(widget.width(), widget.height())
        
        # Configurações de Interação
        self.setAcceptHoverEvents(True) 
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # Movimento manual via mouseEvents para evitar conflitos com o interior do widget
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False) 
        
        self.title = title
        self.snap_enabled = True
        self._mode = None
        self._resize_handle_size = 20
        self._title_bar_height = 25 

    def hoverMoveEvent(self, event):
        """Altera o cursor conforme a zona de interação."""
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

    def mousePressEvent(self, event):
        """Inicia a operação de mover ou redimensionar."""
        pos = event.pos()
        rect = self.boundingRect()
        
        # Detecta redimensionamento (canto inferior direito)
        if (pos.x() > rect.width() - self._resize_handle_size and 
            pos.y() > rect.height() - self._resize_handle_size):
            self._mode = 'RESIZE'
            event.accept()
            return
            
        # Detecta movimento (barra de título)
        if pos.y() < self._title_bar_height:
            self._mode = 'MOVE'
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
            
        self._mode = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Executa a transformação geométrica do item."""
        if self._mode == 'MOVE':
            # Diferença de posição na cena (evita saltos)
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

    def mouseReleaseEvent(self, event):
        """Aplica o alinhamento magnético ao soltar o item."""
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

    def paint(self, painter, option, widget):
        """Desenha elementos visuais auxiliares (borda de seleção e pega de redimensionamento)."""
        super().paint(painter, option, widget)
        
        # Desenha contorno de seleção com a cor da paleta
        # Alterado de DashLine para SolidLine para manter consistência visual flat
        if self.isSelected():
            painter.setPen(QPen(QColor(THEME_COLORS['selection']), 2, Qt.PenStyle.SolidLine))
            painter.drawRect(self.boundingRect())
        
        # Desenha o triângulo de redimensionamento
        rect = self.boundingRect()
        s = self._resize_handle_size
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Substituída a cor hardcoded (255, 255, 255, 40) pela cor Accent com transparência
        grip_color = QColor(THEME_COLORS['accent'])
        grip_color.setAlpha(100) # Transparência sutil
        painter.setBrush(QBrush(grip_color))
        
        triangle = QPolygonF([
            QPointF(rect.width(), rect.height()), 
            QPointF(rect.width() - s, rect.height()), 
            QPointF(rect.width(), rect.height() - s)
        ])
        painter.drawPolygon(triangle)


class BlueprintScene(QGraphicsScene):
    """Área de desenho infinita com fundo de grade dinâmico."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid_visible = True
        self.setSceneRect(0, 0, 4000, 4000)
        # Define o fundo da cena como PRETO
        self.setBackgroundBrush(QBrush(QColor(THEME_COLORS['background'])))
        
    def drawBackground(self, painter, rect):
        """Desenha a grade de pontos de forma eficiente apenas na área visível."""
        super().drawBackground(painter, rect)
        if not self.grid_visible:
            return
        
        left = int(rect.left()) - (int(rect.left()) % GRID_SIZE)
        top = int(rect.top()) - (int(rect.top()) % GRID_SIZE)
        
        # Gera pontos para a grade
        points = []
        for x in range(left, int(rect.right()), GRID_SIZE):
            for y in range(top, int(rect.bottom()), GRID_SIZE):
                points.append(QPointF(x, y))
        
        if points: 
            # Grade sutil usando a cor de grid definida (cinza escuro)
            painter.setPen(QPen(QColor(THEME_COLORS['grid']), 2))
            painter.drawPoints(points)