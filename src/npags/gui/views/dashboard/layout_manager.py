"""
Gerenciador de layouts do Dashboard.

Responsável por:
    - Salvar posições e tamanhos dos widgets
    - Restaurar layouts salvos
    - Aplicar layout padrão em cascata

Extraído de dashboard_view.py para reduzir complexidade.
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from PyQt6.QtCore import QSettings

if TYPE_CHECKING:
    from npags.gui.widgets import SmartDashboardItem


class DashboardLayoutManager:
    """
    Gerenciador de layouts do dashboard.
    
    Persiste posições e tamanhos dos widgets usando QSettings.
    
    Attributes:
        settings: QSettings para persistência.
        app_name: Nome do grupo de configurações.
    """
    
    def __init__(self, organization: str = "NPA_UFG", app_name: str = "GroundStation_Dashboard") -> None:
        """
        Inicializa o gerenciador.
        
        Args:
            organization: Nome da organização para QSettings.
            app_name: Nome da aplicação para QSettings.
        """
        self.settings = QSettings(organization, app_name)
        self._group_prefix = "ProLayouts"
    
    def save_layout(self, layout_name: str, items_map: Dict[str, "SmartDashboardItem"]) -> None:
        """
        Salva o layout atual.
        
        Args:
            layout_name: Nome do layout (geralmente nome do decoder).
            items_map: Mapeamento {field_name: SmartDashboardItem}.
        """
        if not layout_name or not items_map:
            return
        
        self.settings.beginGroup(f"{self._group_prefix}/{layout_name}")
        self.settings.remove("")  # Limpa grupo anterior
        
        for field, item in items_map.items():
            self.settings.setValue(f"{field}/x", item.pos().x())
            self.settings.setValue(f"{field}/y", item.pos().y())
            self.settings.setValue(f"{field}/w", item.widget().size().width())
            self.settings.setValue(f"{field}/h", item.widget().size().height())
        
        self.settings.endGroup()
        self.settings.sync()
    
    def restore_layout(self, layout_name: Optional[str], items_map: Dict[str, "SmartDashboardItem"]) -> bool:
        """
        Restaura um layout salvo.
        
        Args:
            layout_name: Nome do layout.
            items_map: Mapeamento {field_name: SmartDashboardItem}.
            
        Returns:
            True se restaurou pelo menos um item.
        """
        if not layout_name:
            return False
        
        self.settings.beginGroup(f"{self._group_prefix}/{layout_name}")
        
        if not self.settings.childGroups():
            self.settings.endGroup()
            return False
        
        restored = 0
        
        for field, item in items_map.items():
            x = self.settings.value(f"{field}/x", type=float)
            y = self.settings.value(f"{field}/y", type=float)
            w = self.settings.value(f"{field}/w", type=float)
            h = self.settings.value(f"{field}/h", type=float)
            
            if x is not None and w > 10:
                item.setPos(x, y)
                item.widget().resize(int(w), int(h))
                item.resize(w, h)
                restored += 1
        
        self.settings.endGroup()
        return restored > 0
    
    def apply_default_layout(self, items_map: Dict[str, "SmartDashboardItem"]) -> None:
        """
        Aplica layout padrão em cascata.
        
        Args:
            items_map: Mapeamento {field_name: SmartDashboardItem}.
        """
        cx, cy = 20, 20
        
        for item in items_map.values():
            item.setPos(cx, cy)
            cx += 40
            cy += 40
            
            if cy > 500:
                cy = 20
                cx += 300
    
    def has_saved_layout(self, layout_name: str) -> bool:
        """
        Verifica se existe um layout salvo.
        
        Args:
            layout_name: Nome do layout.
            
        Returns:
            True se existe layout salvo.
        """
        if not layout_name:
            return False
        
        self.settings.beginGroup(f"{self._group_prefix}/{layout_name}")
        has_layout = bool(self.settings.childGroups())
        self.settings.endGroup()
        
        return has_layout
    
    def delete_layout(self, layout_name: str) -> None:
        """
        Remove um layout salvo.
        
        Args:
            layout_name: Nome do layout.
        """
        if not layout_name:
            return
        
        self.settings.beginGroup(f"{self._group_prefix}/{layout_name}")
        self.settings.remove("")
        self.settings.endGroup()
        self.settings.sync()
    
    def list_saved_layouts(self) -> list[str]:
        """
        Lista todos os layouts salvos.
        
        Returns:
            Lista de nomes de layouts.
        """
        self.settings.beginGroup(self._group_prefix)
        layouts = self.settings.childGroups()
        self.settings.endGroup()
        
        return layouts
