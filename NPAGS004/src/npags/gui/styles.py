# src/npags/gui/styles.py

"""
Definições de estilos (CSS/QSS) e Paleta de Cores Global.
Versão Final (Caminho Absoluto): 
- Resolve o erro de "Cannot open file" usando caminho dinâmico via Python.
- Remove avisos de "Unknown property content".
"""

import os
from pathlib import Path

# === DESCOBERTA AUTOMÁTICA DO CAMINHO DO ÍCONE ===
# Pega o diretório onde este arquivo (styles.py) está: .../src/npags/gui/
BASE_DIR = Path(__file__).parent.resolve()
# Monta o caminho: .../src/npags/gui/assets/down.svg
ICON_PATH = (BASE_DIR / "assets" / "down.svg").as_posix()

# === PALETA DE CORES ===
THEME_COLORS = {
    "background": "#000000",
    "surface_secondary": "#111111", 
    "surface_tertiary": "#222222",  
    "text": "#ffffff",
    "text_dim": "#888888",          
    "accent": "#ae5516",       
    "accent_hover": "#c96f28", 
    "accent_pressed": "#8a4311", 
    "border": "#ae5516",
    "border_subtle": "#333333",
    "grid": "#333333",
    "selection": "#ae5516", 
    "danger": "#8a2020",
    "danger_hover": "#a33030",
    "success": "#ae5516", 
    "success_hover": "#c96f28"
}

# === FOLHA DE ESTILO (QSS) ===
# Usamos f-string para injetar o ICON_PATH calculado dinamicamente
FLAT_DARK_STYLESHEET = f"""
/* === BASE & SELEÇÃO === */
QWidget {{
    background-color: {THEME_COLORS['background']};
    color: {THEME_COLORS['text']};
    font-family: "Segoe UI", "Roboto", "Arial", sans-serif;
    font-size: 13px;
    font-weight: normal;
    
    selection-background-color: {THEME_COLORS['selection']};
    selection-color: #ffffff;
}}
QMainWindow, QDialog {{ background-color: {THEME_COLORS['background']}; }}
QFrame {{ border: none; background: transparent; }}
QLabel {{ color: {THEME_COLORS['text']}; }}

/* === ESTRUTURA === */
QWidget#Sidebar {{
    background-color: {THEME_COLORS['background']};
    border-right: 1px solid {THEME_COLORS['border_subtle']};
}}
QFrame.SectionContainer {{
    border: 1px solid {THEME_COLORS['border_subtle']};
    border-radius: 4px;
    background-color: {THEME_COLORS['background']};
}}
QLabel.SectionTitle {{
    background-color: {THEME_COLORS['surface_secondary']};
    color: {THEME_COLORS['text']};
    font-weight: normal; 
    border-bottom: 1px solid {THEME_COLORS['border_subtle']};
    border-top-left-radius: 4px; border-top-right-radius: 4px;
}}
QFrame#SeparatorLine {{
    background-color: {THEME_COLORS['border_subtle']};
    border: none;
    max-height: 1px;
}}

/* === SCROLLBARS === */
QScrollBar:vertical {{
    border: none;
    background: {THEME_COLORS['surface_secondary']};
    width: 10px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:vertical {{
    background: {THEME_COLORS['border_subtle']};
    min-height: 20px;
    border-radius: 2px;
}}
QScrollBar::handle:vertical:hover {{ background: {THEME_COLORS['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}

QScrollBar:horizontal {{
    border: none;
    background: {THEME_COLORS['surface_secondary']};
    height: 10px;
    margin: 0px 0px 0px 0px;
}}
QScrollBar::handle:horizontal {{
    background: {THEME_COLORS['border_subtle']};
    min-width: 20px;
    border-radius: 2px;
}}
QScrollBar::handle:horizontal:hover {{ background: {THEME_COLORS['accent']}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

QSizeGrip {{ background: transparent; width: 0; height: 0; border: none; }}
QStatusBar {{ background: {THEME_COLORS['background']}; border: none; min-height: 0; }}
QAbstractScrollArea::corner {{ background: {THEME_COLORS['background']}; border: none; }}

/* === SPLITTER === */
QSplitter::handle {{ 
    background-color: {THEME_COLORS['border_subtle']}; 
    border: none;
    height: 1px;
}}
QSplitter::handle:hover {{ background-color: {THEME_COLORS['accent']}; }}

/* === INPUTS & LISTAS === */
QLineEdit, QSpinBox, QComboBox, QDateTimeEdit, QPlainTextEdit {{
    background-color: {THEME_COLORS['background']};
    border: 1px solid {THEME_COLORS['border_subtle']};
    border-radius: 4px;
    padding: 6px 12px;
    color: {THEME_COLORS['text']};
    min-height: 15px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateTimeEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {THEME_COLORS['accent']};
    background-color: #0a0a0a;
}}

/* 1. Botão Dropdown */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right; 
    width: 30px; 
    border-left-width: 0px; 
    border-top-right-radius: 4px;
    border-bottom-right-radius: 4px;
    background: transparent; 
}}

/* 2. Seta Personalizada (SVG) - Caminho Absoluto Injetado */
QComboBox::down-arrow {{
    image: url({ICON_PATH});
    
    width: 10px;  
    height: 10px; 
    margin-right: 8px;
}}

/* Listas internas */
QComboBox QAbstractItemView {{ 
    background-color: {THEME_COLORS['surface_secondary']}; 
    border: 1px solid {THEME_COLORS['accent']}; 
    color: {THEME_COLORS['text']};
    outline: none;
}}
QAbstractItemView::item:selected {{
    background-color: {THEME_COLORS['accent']};
    color: #ffffff;
}}
QAbstractItemView::item:hover {{
    background-color: {THEME_COLORS['surface_tertiary']};
}}

/* === SLIDERS === */
QSlider::groove:horizontal {{
    border: 1px solid {THEME_COLORS['border_subtle']};
    height: 3px;
    background: {THEME_COLORS['surface_tertiary']};
    margin: 2px 0;
    border-radius: 1px;
}}
QSlider::handle:horizontal {{
    background: {THEME_COLORS['accent']};
    border: 1px solid {THEME_COLORS['accent']};
    width: 10px;
    height: 10px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: {THEME_COLORS['accent_hover']};
}}
QSlider::sub-page:horizontal {{
    background: {THEME_COLORS['accent']};
    border-radius: 2px;
    height: 5px;
}}

/* === CHECKBOXES === */
QCheckBox {{ spacing: 8px; color: {THEME_COLORS['text']}; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    background-color: {THEME_COLORS['background']};
    border: 1px solid {THEME_COLORS['border_subtle']};
    border-radius: 2px;
}}
QCheckBox::indicator:hover {{ border: 1px solid {THEME_COLORS['text_dim']}; }}
QCheckBox::indicator:checked {{
    background-color: {THEME_COLORS['accent']};
    border: 1px solid {THEME_COLORS['accent']};
}}
QCheckBox::indicator:checked:hover {{
    background-color: {THEME_COLORS['accent_hover']};
    border-color: {THEME_COLORS['accent_hover']};
}}

/* === BOTÕES GERAIS === */
QPushButton {{
    background-color: {THEME_COLORS['accent']};
    border: 1px solid {THEME_COLORS['accent']};
    border-radius: 4px;
    padding: 8px 16px;
    color: #ffffff;
    font-weight: normal; 
}}
QPushButton:hover {{ 
    background-color: {THEME_COLORS['accent_hover']}; 
    border-color: {THEME_COLORS['accent_hover']}; 
}}
QPushButton:pressed {{ 
    background-color: {THEME_COLORS['accent_pressed']}; 
    border-color: {THEME_COLORS['accent_pressed']}; 
}}

/* Botão Secundário (Outline) */
QPushButton.secondary {{
    background-color: transparent;
    border: 1px solid {THEME_COLORS['border_subtle']};
    color: {THEME_COLORS['text']};
}}
QPushButton.secondary:hover {{
    background-color: {THEME_COLORS['surface_secondary']};
    border-color: {THEME_COLORS['accent']};
    color: {THEME_COLORS['accent']};
}}

/* === BOTÕES ESPECÍFICOS === */
QPushButton#btn_delete, QPushButton#btn_cancel {{
    background-color: {THEME_COLORS['danger']};
    border: 1px solid {THEME_COLORS['danger']};
    color: #ffffff;
}}
QPushButton#btn_delete:hover, QPushButton#btn_cancel:hover {{ 
    background-color: {THEME_COLORS['danger_hover']}; 
    border-color: {THEME_COLORS['danger_hover']}; 
}}

/* Botão de Filtro */
QPushButton#btn_filter {{
    background-color: {THEME_COLORS['success']};
    border: 1px solid {THEME_COLORS['success']};
}}
QPushButton#btn_filter:hover {{ 
    background-color: {THEME_COLORS['success_hover']}; 
    border-color: {THEME_COLORS['success_hover']}; 
}}

QPushButton#btn_quick {{
    background-color: transparent;
    border: 1px solid {THEME_COLORS['border_subtle']};
    color: {THEME_COLORS['text_dim']};
}}
QPushButton#btn_quick:hover {{ border-color: {THEME_COLORS['text']}; color: {THEME_COLORS['text']}; }}

/* Station View */
QPushButton#btn_connect_start {{
    background-color: {THEME_COLORS['accent']};
    border: 1px solid {THEME_COLORS['accent']};
}}
QPushButton#btn_connect_stop {{
    background-color: {THEME_COLORS['danger']};
    border: 1px solid {THEME_COLORS['danger']};
}}
QPushButton#btn_dashboard_main {{
    background-color: transparent; 
    border: 1px solid {THEME_COLORS['border_subtle']}; 
    color: {THEME_COLORS['text']}; 
    border-radius: 4px;
}}
QPushButton#btn_dashboard_main:hover {{ 
    background-color: {THEME_COLORS['surface_secondary']}; 
    border-color: {THEME_COLORS['accent']}; 
    color: {THEME_COLORS['accent']};
}}

/* Mode Toggle */
QPushButton.ModeToggle {{
    background-color: {THEME_COLORS['surface_secondary']}; 
    border: 1px solid {THEME_COLORS['border_subtle']}; 
    color: {THEME_COLORS['text_dim']}; 
    padding: 10px; 
    border-radius: 4px; 
    font-size: 12px; 
    font-weight: normal; 
}}
QPushButton.ModeToggle:checked {{
    background-color: {THEME_COLORS['background']}; 
    color: {THEME_COLORS['text']}; 
    border: 1px solid {THEME_COLORS['accent']}; 
    border-bottom: 2px solid {THEME_COLORS['accent']};
}}
QPushButton.ModeToggle:hover:!checked {{ 
    background-color: {THEME_COLORS['surface_tertiary']}; 
}}

/* === COMPONENTES DA DASHBOARD === */
QFrame#DashboardHeader {{
    background-color: {THEME_COLORS['background']};
    border-bottom: 1px solid {THEME_COLORS['accent']};
}}
QFrame#DashboardFrame {{
    background-color: {THEME_COLORS['background']};
    border: 1px solid {THEME_COLORS['border_subtle']};
    border-radius: 4px;
}}
QFrame#DashboardFrame:hover {{
    border: 1px solid {THEME_COLORS['accent']};
}}
QLabel.WidgetTitle {{
    background-color: {THEME_COLORS['accent']};
    color: #ffffff;
    padding: 2px 5px;
    font-size: 11px;
    font-weight: normal; 
    border-top-left-radius: 3px;
    border-top-right-radius: 3px;
}}
QLabel.CardValue {{ color: #ffffff; font-size: 22px; font-weight: normal; }}
QLabel.InfoLabel {{ color: {THEME_COLORS['text_dim']}; font-size: 12px; }}
QLabel.LedBulb {{ border-radius: 8px; border: none; }}
QProgressBar.DashboardGauge {{
    border: none;
    background: {THEME_COLORS['surface_tertiary']};
    border-radius: 3px;
    text-align: center;
}}
QProgressBar.DashboardGauge::chunk {{
    background: {THEME_COLORS['accent']};
    border-radius: 3px;
}}

/* Menus */
QMenu {{ 
    background-color: {THEME_COLORS['background']}; 
    color: {THEME_COLORS['text']}; 
    border: 1px solid {THEME_COLORS['border_subtle']}; 
}}
QMenu::item {{ padding: 5px 20px; }}
QMenu::item:selected {{ background-color: {THEME_COLORS['accent']}; color: #ffffff; }}

QPlainTextEdit#LogConsole {{
    background-color: transparent;
    border: none;
    color: {THEME_COLORS['text']};
    font-family: "Consolas", monospace;
}}
QToolTip {{ 
    border: 1px solid {THEME_COLORS['accent']}; 
    background-color: {THEME_COLORS['surface_secondary']}; 
    color: {THEME_COLORS['text']}; 
    padding: 4px; 
}}
"""