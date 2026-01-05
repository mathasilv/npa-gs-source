# src/npags/reports/generator.py
"""
Motor de geração de relatórios PDF profissionais para missões de telemetria.

Baseado em padrões de relatórios de missões espaciais (NASA/ESA) e
relatórios técnicos IEEE. Inclui:
    - Capa profissional com logo
    - Resumo executivo com KPIs destacados
    - Estatísticas detalhadas com visualizações
    - Gráficos temporais de alta qualidade
    - Registro de alertas e anomalias
    - Trajetória GPS com mapa
    - Metadados e configurações
"""

from __future__ import annotations

import io
import logging
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Imports opcionais para PDF
try:
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
        Flowable,
    )
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.widgets.markers import makeMarker
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Import para gráficos
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

# Import para mapas estáticos
try:
    import staticmaps
    STATICMAPS_AVAILABLE = True
except ImportError:
    staticmaps = None
    STATICMAPS_AVAILABLE = False


# =============================================================================
# CORES DO TEMA NPA
# =============================================================================
class NPAColors:
    """Paleta de cores oficial NPA-UFG."""
    PRIMARY = '#ae5516'       # Laranja NPA
    PRIMARY_DARK = '#8a4412'  # Laranja escuro
    PRIMARY_LIGHT = '#d4722e' # Laranja claro
    SECONDARY = '#1a365d'     # Azul escuro
    ACCENT = '#2c5282'        # Azul médio
    SUCCESS = '#38a169'       # Verde
    WARNING = '#d69e2e'       # Amarelo
    DANGER = '#e53e3e'        # Vermelho
    TEXT_DARK = '#1a202c'     # Texto escuro
    TEXT_MEDIUM = '#4a5568'   # Texto médio
    TEXT_LIGHT = '#718096'    # Texto claro
    BG_LIGHT = '#f7fafc'      # Fundo claro
    BG_MEDIUM = '#edf2f7'     # Fundo médio
    BORDER = '#e2e8f0'        # Bordas
    WHITE = '#ffffff'
    BLACK = '#000000'


# =============================================================================
# CONFIGURAÇÃO DO RELATÓRIO
# =============================================================================
@dataclass
class ReportConfig:
    """Configuração para geração de relatório."""

    # Informações básicas
    title: str = "Relatório de Missão"
    mission_name: str = "Missão"
    author: str = "NPA Ground Station"
    organization: str = "NPA - Núcleo de Pesquisas Aeroespaciais - UFG"

    # Período
    start_time: datetime | None = None
    end_time: datetime | None = None

    # Decoders selecionados
    selected_decoders: list[str] = field(default_factory=list)

    # Campos selecionados para incluir
    selected_fields: list[str] = field(default_factory=list)

    # Fontes de dados selecionadas
    selected_sources: list[str] = field(default_factory=list)

    # Seções do relatório
    include_summary: bool = True
    include_statistics: bool = True
    include_charts: bool = True
    include_alerts: bool = True
    include_gps_track: bool = True
    include_raw_data: bool = False
    include_config: bool = True

    # Opções de gráficos
    chart_style: str = "line"
    chart_resolution: str = "medium"
    charts_per_page: int = 2

    # Opções de estatísticas
    stats_include_min: bool = True
    stats_include_max: bool = True
    stats_include_mean: bool = True
    stats_include_std: bool = True
    stats_include_median: bool = True
    stats_include_count: bool = True

    # Formato
    page_size: str = "A4"
    orientation: str = "portrait"

    # Limites
    max_data_points: int = 10000
    max_charts: int = 20


@dataclass
class FieldStatistics:
    """Estatísticas calculadas para um campo."""
    field_name: str
    description: str
    unit: str
    count: int
    min_value: float
    max_value: float
    mean_value: float
    std_value: float
    median_value: float
    first_value: float
    last_value: float
    delta: float


@dataclass
class AlertRecord:
    """Registro de alerta para o relatório."""
    timestamp: datetime
    field_name: str
    description: str
    value: float
    threshold: float
    violation_type: str
    severity: str


# =============================================================================
# COMPONENTES CUSTOMIZADOS
# =============================================================================
class ColoredBox(Flowable):
    """Caixa colorida para destacar KPIs."""
    
    def __init__(self, width, height, color, text, value, unit=""):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.color = color
        self.text = text
        self.value = value
        self.unit = unit
    
    def draw(self):
        self.canv.setFillColor(colors.HexColor(self.color))
        self.canv.roundRect(0, 0, self.width, self.height, 5, fill=1, stroke=0)
        
        # Valor principal
        self.canv.setFillColor(colors.white)
        self.canv.setFont("Helvetica-Bold", 18)
        value_text = f"{self.value}{self.unit}"
        self.canv.drawCentredString(self.width/2, self.height/2 + 5, value_text)
        
        # Label
        self.canv.setFont("Helvetica", 9)
        self.canv.drawCentredString(self.width/2, self.height/2 - 15, self.text)


class HeaderFooter:
    """Gerenciador de cabeçalho e rodapé das páginas."""
    
    def __init__(self, logo_path: str | None, title: str, mission: str):
        self.logo_path = logo_path
        self.title = title
        self.mission = mission
        self.page_count = 0
    
    def __call__(self, canvas, doc):
        self.page_count += 1
        canvas.saveState()
        
        page_width = doc.pagesize[0]
        page_height = doc.pagesize[1]
        
        # Cabeçalho (exceto primeira página)
        if self.page_count > 1:
            # Linha do cabeçalho
            canvas.setStrokeColor(colors.HexColor(NPAColors.PRIMARY))
            canvas.setLineWidth(1)
            canvas.line(1.5*cm, page_height - 1.5*cm, page_width - 1.5*cm, page_height - 1.5*cm)
            
            # Título no cabeçalho
            canvas.setFillColor(colors.HexColor(NPAColors.TEXT_MEDIUM))
            canvas.setFont("Helvetica", 8)
            canvas.drawString(1.5*cm, page_height - 1.3*cm, f"{self.title} - {self.mission}")
            
            # Data no cabeçalho
            canvas.drawRightString(page_width - 1.5*cm, page_height - 1.3*cm, 
                                   datetime.now().strftime("%d/%m/%Y"))
        
        # Rodapé
        canvas.setStrokeColor(colors.HexColor(NPAColors.BORDER))
        canvas.setLineWidth(0.5)
        canvas.line(1.5*cm, 1.2*cm, page_width - 1.5*cm, 1.2*cm)
        
        # Número da página
        canvas.setFillColor(colors.HexColor(NPAColors.TEXT_LIGHT))
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(page_width/2, 0.8*cm, f"Página {self.page_count}")
        
        # Texto do rodapé
        canvas.setFont("Helvetica", 7)
        canvas.drawString(1.5*cm, 0.8*cm, "NPA Ground Station")
        canvas.drawRightString(page_width - 1.5*cm, 0.8*cm, "Documento Confidencial")
        
        canvas.restoreState()


# =============================================================================
# GERADOR DE RELATÓRIOS
# =============================================================================
class ReportGenerator:
    """
    Gerador de relatórios PDF profissionais para missões de telemetria.
    """

    def __init__(
        self,
        config: ReportConfig,
        data_buffer: dict[str, dict[str, Any]],
        timestamp_buffer: dict[str, dict[str, list[datetime]]],
        field_configs: dict[str, dict[str, Any]],
        alerts_history: list[AlertRecord] | None = None
    ) -> None:
        self.config = config
        self.data_buffer = data_buffer
        self.timestamp_buffer = timestamp_buffer
        self.field_configs = field_configs
        self.alerts_history = alerts_history or []
        self._statistics: dict[str, FieldStatistics] = {}
        
        # Caminho da logo
        self._logo_path = self._find_logo()
        
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab não está instalado. Instale com: pip install reportlab")

    def _find_logo(self) -> str | None:
        """Encontra o caminho da logo NPA."""
        possible_paths = [
            Path(__file__).parent.parent / "gui" / "assets" / "logo.png",
            Path(__file__).parent.parent.parent / "gui" / "assets" / "logo.png",
            Path("/home/archie/Documentos/npa_gs/src/npags/gui/assets/logo.png"),
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        return None

    def generate(self, output_path: str) -> tuple[bool, str]:
        """Gera o relatório PDF."""
        try:
            self._calculate_statistics()
            
            page_size = A4 if self.config.page_size == "A4" else letter
            if self.config.orientation == "landscape":
                page_size = (page_size[1], page_size[0])
            
            doc = SimpleDocTemplate(
                output_path,
                pagesize=page_size,
                rightMargin=1.5*cm,
                leftMargin=1.5*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            story = []
            styles = self._setup_styles()
            
            # Capa
            story.extend(self._build_cover_page(styles))
            
            # Sumário executivo
            if self.config.include_summary:
                story.extend(self._build_executive_summary(styles))
            
            # Estatísticas
            if self.config.include_statistics:
                story.extend(self._build_statistics_section(styles))
            
            # Gráficos
            if self.config.include_charts and MATPLOTLIB_AVAILABLE:
                story.extend(self._build_charts_section(styles))
            
            # Alertas
            if self.config.include_alerts and self.alerts_history:
                story.extend(self._build_alerts_section(styles))
            
            # GPS
            if self.config.include_gps_track:
                story.extend(self._build_gps_section(styles))
            
            # Configuração
            if self.config.include_config:
                story.extend(self._build_appendix(styles))
            
            # Gera PDF com cabeçalho/rodapé
            header_footer = HeaderFooter(self._logo_path, self.config.title, self.config.mission_name)
            doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
            
            return True, f"Relatório gerado com sucesso: {output_path}"
            
        except Exception as e:
            logger.exception("Erro ao gerar relatório")
            return False, f"Erro ao gerar relatório: {str(e)}"

    def _setup_styles(self):
        """Configura estilos profissionais."""
        styles = getSampleStyleSheet()
        
        # Título da capa
        styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=styles['Heading1'],
            fontSize=28,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor(NPAColors.PRIMARY),
            fontName='Helvetica-Bold'
        ))
        
        # Subtítulo da capa
        styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=styles['Normal'],
            fontSize=16,
            spaceAfter=5,
            alignment=TA_CENTER,
            textColor=colors.HexColor(NPAColors.SECONDARY),
            fontName='Helvetica'
        ))
        
        # Info da capa
        styles.add(ParagraphStyle(
            name='CoverInfo',
            parent=styles['Normal'],
            fontSize=11,
            spaceBefore=3,
            spaceAfter=3,
            alignment=TA_CENTER,
            textColor=colors.HexColor(NPAColors.TEXT_MEDIUM)
        ))
        
        # Título de seção
        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceBefore=20,
            spaceAfter=15,
            textColor=colors.HexColor(NPAColors.PRIMARY),
            fontName='Helvetica-Bold',
            borderColor=colors.HexColor(NPAColors.PRIMARY),
            borderWidth=2,
            borderPadding=(0, 0, 5, 0),
            borderRadius=None
        ))
        
        # Subtítulo de seção
        styles.add(ParagraphStyle(
            name='SubsectionTitle',
            parent=styles['Heading2'],
            fontSize=13,
            spaceBefore=15,
            spaceAfter=8,
            textColor=colors.HexColor(NPAColors.SECONDARY),
            fontName='Helvetica-Bold'
        ))
        
        # Corpo do texto
        styles.add(ParagraphStyle(
            name='ReportBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceBefore=4,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor(NPAColors.TEXT_DARK),
            leading=14
        ))
        
        # Texto destacado
        styles.add(ParagraphStyle(
            name='Highlight',
            parent=styles['Normal'],
            fontSize=10,
            spaceBefore=8,
            spaceAfter=8,
            alignment=TA_LEFT,
            textColor=colors.HexColor(NPAColors.PRIMARY),
            fontName='Helvetica-Bold',
            leftIndent=10,
            borderColor=colors.HexColor(NPAColors.PRIMARY),
            borderWidth=2,
            borderPadding=8,
            backColor=colors.HexColor('#fff5eb')
        ))
        
        # Texto pequeno
        styles.add(ParagraphStyle(
            name='SmallText',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor(NPAColors.TEXT_LIGHT)
        ))
        
        # Caption de figura
        styles.add(ParagraphStyle(
            name='FigureCaption',
            parent=styles['Normal'],
            fontSize=9,
            spaceBefore=5,
            spaceAfter=15,
            alignment=TA_CENTER,
            textColor=colors.HexColor(NPAColors.TEXT_MEDIUM),
            fontName='Helvetica-Oblique'
        ))
        
        return styles

    def _build_cover_page(self, styles) -> list:
        """Constrói página de capa profissional."""
        elements = []
        
        # Espaço superior
        elements.append(Spacer(1, 1*cm))
        
        # Logo
        if self._logo_path:
            try:
                logo = Image(self._logo_path, width=5*cm, height=5*cm)
                logo.hAlign = 'CENTER'
                elements.append(logo)
                elements.append(Spacer(1, 1*cm))
            except Exception:
                pass
        
        # Linha decorativa superior
        elements.append(self._create_decorative_line())
        elements.append(Spacer(1, 0.5*cm))
        
        # Título principal
        elements.append(Paragraph(self.config.title.upper(), styles['CoverTitle']))
        
        # Nome da missão
        elements.append(Paragraph(f"Missão: {self.config.mission_name}", styles['CoverSubtitle']))
        
        elements.append(Spacer(1, 0.5*cm))
        elements.append(self._create_decorative_line())
        elements.append(Spacer(1, 1.5*cm))
        
        # Informações da missão em caixa
        info_data = []
        
        if self.config.start_time and self.config.end_time:
            duration = self.config.end_time - self.config.start_time
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            info_data.append(["Período da Missão", 
                f"{self.config.start_time.strftime('%d/%m/%Y %H:%M')} - {self.config.end_time.strftime('%d/%m/%Y %H:%M')}"])
            info_data.append(["Duração Total", f"{hours}h {minutes}min"])
        
        if self.config.selected_decoders:
            info_data.append(["Decoders Utilizados", ", ".join(self.config.selected_decoders)])
        
        info_data.append(["Gerado por", self.config.author])
        info_data.append(["Organização", self.config.organization or "NPA-UFG"])
        info_data.append(["Data de Geração", datetime.now().strftime("%d/%m/%Y às %H:%M:%S")])
        
        if info_data:
            info_table = Table(info_data, colWidths=[150, 280])
            info_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor(NPAColors.TEXT_MEDIUM)),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor(NPAColors.TEXT_DARK)),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('LINEBELOW', (0, 0), (-1, -2), 0.5, colors.HexColor(NPAColors.BORDER)),
            ]))
            elements.append(info_table)
        
        elements.append(Spacer(1, 2*cm))
        
        # Aviso de confidencialidade
        elements.append(Paragraph(
            "<i>Este documento contém informações técnicas da missão. "
            "Distribuição restrita aos membros autorizados do projeto.</i>",
            styles['SmallText']
        ))
        
        elements.append(PageBreak())
        return elements

    def _create_decorative_line(self) -> Drawing:
        """Cria linha decorativa com gradiente."""
        d = Drawing(450, 4)
        d.add(Rect(0, 0, 450, 3, fillColor=colors.HexColor(NPAColors.PRIMARY), strokeColor=None))
        d.add(Rect(0, 0, 150, 3, fillColor=colors.HexColor(NPAColors.PRIMARY_DARK), strokeColor=None))
        return d

    def _build_executive_summary(self, styles) -> list:
        """Constrói resumo executivo com KPIs destacados."""
        elements = []
        
        elements.append(Paragraph("1. Resumo Executivo", styles['SectionTitle']))
        
        # Texto introdutório
        intro_text = f"""Este relatório apresenta os dados coletados durante a missão 
        <b>{self.config.mission_name}</b>. A análise abrange telemetria de sensores, 
        estatísticas de desempenho e registro de eventos relevantes."""
        elements.append(Paragraph(intro_text, styles['ReportBody']))
        elements.append(Spacer(1, 0.5*cm))
        
        # Calcula métricas para KPIs
        total_points = 0
        total_fields = 0
        sources_count = len(self.config.selected_sources) if self.config.selected_sources else len(self.data_buffer)
        
        for source_id in (self.config.selected_sources or self.data_buffer.keys()):
            if source_id not in self.data_buffer:
                continue
            buffer = self.data_buffer[source_id]
            for field_name, values in buffer.items():
                if isinstance(values, list) and not field_name.endswith('_last'):
                    total_points += len(values)
                    total_fields += 1
        
        # Duração
        duration_str = "N/A"
        duration_hours = 0
        if self.config.start_time and self.config.end_time:
            duration = self.config.end_time - self.config.start_time
            duration_hours = duration.total_seconds() / 3600
            hours, remainder = divmod(int(duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m"
        
        # KPI Cards
        elements.append(Paragraph("<b>Indicadores Principais</b>", styles['SubsectionTitle']))
        
        kpi_data = [
            [ColoredBox(100, 60, NPAColors.PRIMARY, "Duração", duration_str),
             ColoredBox(100, 60, NPAColors.SECONDARY, "Fontes", str(sources_count)),
             ColoredBox(100, 60, NPAColors.ACCENT, "Campos", str(total_fields)),
             ColoredBox(100, 60, NPAColors.SUCCESS if len(self.alerts_history) == 0 else NPAColors.WARNING, 
                       "Alertas", str(len(self.alerts_history)))]
        ]
        
        kpi_table = Table(kpi_data, colWidths=[110, 110, 110, 110])
        kpi_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(kpi_table)
        elements.append(Spacer(1, 0.8*cm))
        
        # Tabela de resumo detalhado
        elements.append(Paragraph("<b>Visão Geral da Missão</b>", styles['SubsectionTitle']))
        
        summary_data = [
            ["Métrica", "Valor", "Observação"],
            ["Total de Pontos de Dados", f"{total_points:,}", 
             f"~{total_points/max(duration_hours,1):.0f} pontos/hora" if duration_hours > 0 else "-"],
            ["Campos Monitorados", str(total_fields), 
             f"{total_fields/max(sources_count,1):.1f} campos/fonte" if sources_count > 0 else "-"],
            ["Taxa de Alertas", f"{len(self.alerts_history)}", 
             "Normal" if len(self.alerts_history) < 10 else "Atenção requerida"],
            ["Cobertura Temporal", duration_str, 
             f"{self.config.start_time.strftime('%d/%m %H:%M') if self.config.start_time else 'N/A'} - "
             f"{self.config.end_time.strftime('%d/%m %H:%M') if self.config.end_time else 'N/A'}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[150, 100, 180])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.SECONDARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), 
             [colors.HexColor(NPAColors.BG_LIGHT), colors.HexColor(NPAColors.WHITE)]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]))
        elements.append(summary_table)
        
        # Destaques (se houver estatísticas)
        if self._statistics:
            elements.append(Spacer(1, 0.5*cm))
            elements.append(Paragraph("<b>Destaques da Telemetria</b>", styles['SubsectionTitle']))
            
            # Encontra valores extremos
            highlights = []
            for field_name, stats in list(self._statistics.items())[:5]:
                if abs(stats.delta) > 0:
                    direction = "↑" if stats.delta > 0 else "↓"
                    highlights.append(
                        f"• <b>{stats.description}</b>: variou de {stats.first_value:.2f} para "
                        f"{stats.last_value:.2f} {stats.unit} ({direction} {abs(stats.delta):.2f})"
                    )
            
            for h in highlights:
                elements.append(Paragraph(h, styles['ReportBody']))
        
        elements.append(PageBreak())
        return elements

    def _calculate_statistics(self) -> None:
        """Calcula estatísticas para todos os campos selecionados."""
        self._statistics.clear()
        
        selected_fields = self.config.selected_fields or list(self.field_configs.keys())
        selected_sources = self.config.selected_sources or list(self.data_buffer.keys())
        
        for field_name in selected_fields:
            all_values = []
            
            for source_id in selected_sources:
                if source_id not in self.data_buffer:
                    continue
                buffer = self.data_buffer[source_id]
                if field_name in buffer and isinstance(buffer[field_name], list):
                    all_values.extend(buffer[field_name])
            
            if not all_values or len(all_values) < 2:
                continue
            
            numeric_values = [v for v in all_values if isinstance(v, (int, float))]
            if len(numeric_values) < 2:
                continue
            
            field_cfg = self.field_configs.get(field_name, {})
            
            try:
                self._statistics[field_name] = FieldStatistics(
                    field_name=field_name,
                    description=field_cfg.get('description', field_name),
                    unit=field_cfg.get('unit', ''),
                    count=len(numeric_values),
                    min_value=min(numeric_values),
                    max_value=max(numeric_values),
                    mean_value=statistics.mean(numeric_values),
                    std_value=statistics.stdev(numeric_values) if len(numeric_values) > 1 else 0,
                    median_value=statistics.median(numeric_values),
                    first_value=numeric_values[0],
                    last_value=numeric_values[-1],
                    delta=numeric_values[-1] - numeric_values[0]
                )
            except Exception:
                continue

    def _build_statistics_section(self, styles) -> list:
        """Constrói seção de estatísticas detalhadas."""
        elements = []
        
        elements.append(Paragraph("2. Estatísticas de Telemetria", styles['SectionTitle']))
        
        if not self._statistics:
            elements.append(Paragraph(
                "Nenhuma estatística disponível para os campos selecionados.",
                styles['ReportBody']
            ))
            return elements
        
        elements.append(Paragraph(
            "Esta seção apresenta a análise estatística dos dados coletados durante a missão. "
            "Os valores incluem medidas de tendência central e dispersão para cada variável monitorada.",
            styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Tabela principal de estatísticas
        header = ["Campo", "N", "Mín", "Máx", "Média", "σ", "Mediana", "Unid."]
        table_data = [header]
        
        for field_name, stats in self._statistics.items():
            row = [
                stats.description[:25],
                f"{stats.count:,}",
                f"{stats.min_value:.2f}",
                f"{stats.max_value:.2f}",
                f"{stats.mean_value:.2f}",
                f"{stats.std_value:.2f}",
                f"{stats.median_value:.2f}",
                stats.unit or "-"
            ]
            table_data.append(row)
        
        col_widths = [120, 45, 50, 50, 50, 45, 50, 40]
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.PRIMARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), 
             [colors.HexColor(NPAColors.BG_LIGHT), colors.HexColor(NPAColors.WHITE)]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(
            "<i>N = número de amostras; σ = desvio padrão</i>",
            styles['SmallText']
        ))
        
        # Análise de variação
        elements.append(Spacer(1, 0.5*cm))
        elements.append(Paragraph("<b>Análise de Variação</b>", styles['SubsectionTitle']))
        
        variation_data = [["Campo", "Valor Inicial", "Valor Final", "Variação", "Tendência"]]
        
        for field_name, stats in list(self._statistics.items())[:10]:
            delta_pct = (stats.delta / stats.first_value * 100) if stats.first_value != 0 else 0
            trend = "↑ Aumento" if stats.delta > 0 else ("↓ Redução" if stats.delta < 0 else "→ Estável")
            
            variation_data.append([
                stats.description[:20],
                f"{stats.first_value:.2f} {stats.unit}",
                f"{stats.last_value:.2f} {stats.unit}",
                f"{stats.delta:+.2f} ({delta_pct:+.1f}%)",
                trend
            ])
        
        var_table = Table(variation_data, colWidths=[100, 85, 85, 90, 80])
        var_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.SECONDARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), 
             [colors.HexColor(NPAColors.BG_LIGHT), colors.HexColor(NPAColors.WHITE)]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]))
        
        elements.append(var_table)
        elements.append(PageBreak())
        
        return elements

    def _build_charts_section(self, styles) -> list:
        """Constrói seção de gráficos profissionais."""
        elements = []
        
        if not MATPLOTLIB_AVAILABLE:
            return elements
        
        elements.append(Paragraph("3. Gráficos de Telemetria", styles['SectionTitle']))
        elements.append(Paragraph(
            "Os gráficos a seguir apresentam a evolução temporal das variáveis monitoradas "
            "durante a missão. Cada gráfico inclui a série temporal completa com indicadores "
            "de valores mínimo, máximo e médio.",
            styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        dpi_map = {'low': 80, 'medium': 120, 'high': 150}
        dpi = dpi_map.get(self.config.chart_resolution, 120)
        
        selected_fields = self.config.selected_fields or list(self._statistics.keys())
        charts_generated = 0
        figure_num = 1
        
        for field_name in selected_fields:
            if charts_generated >= self.config.max_charts:
                break
            
            if field_name not in self._statistics:
                continue
            
            stats = self._statistics[field_name]
            values, timestamps = self._collect_field_data(field_name)
            
            if len(values) < 2:
                continue
            
            chart_image = self._generate_professional_chart(
                field_name=field_name,
                description=stats.description,
                unit=stats.unit,
                values=values,
                timestamps=timestamps,
                stats=stats,
                dpi=dpi
            )
            
            if chart_image:
                if charts_generated > 0 and charts_generated % self.config.charts_per_page == 0:
                    elements.append(PageBreak())
                
                elements.append(Image(chart_image, width=450, height=220))
                elements.append(Paragraph(
                    f"Figura {figure_num}: {stats.description} ao longo do tempo",
                    styles['FigureCaption']
                ))
                
                charts_generated += 1
                figure_num += 1
        
        if charts_generated == 0:
            elements.append(Paragraph(
                "Nenhum gráfico disponível para os campos selecionados.",
                styles['ReportBody']
            ))
        
        elements.append(PageBreak())
        return elements

    def _collect_field_data(self, field_name: str) -> tuple[list, list]:
        """Coleta dados e timestamps de um campo."""
        values = []
        timestamps = []
        
        for source_id in (self.config.selected_sources or self.data_buffer.keys()):
            if source_id not in self.data_buffer:
                continue
            
            buffer = self.data_buffer[source_id]
            ts_buffer = self.timestamp_buffer.get(source_id, {})
            
            if field_name in buffer and isinstance(buffer[field_name], list):
                field_values = buffer[field_name]
                field_ts = ts_buffer.get(field_name, [])
                
                max_points = self.config.max_data_points
                if len(field_values) > max_points:
                    step = len(field_values) // max_points
                    field_values = field_values[::step]
                    field_ts = field_ts[::step] if field_ts else []
                
                values.extend(field_values)
                timestamps.extend(field_ts)
        
        return values, timestamps

    def _generate_professional_chart(
        self,
        field_name: str,
        description: str,
        unit: str,
        values: list[float],
        timestamps: list[datetime],
        stats: FieldStatistics,
        dpi: int = 120
    ) -> io.BytesIO | None:
        """Gera gráfico profissional com estilo NPA."""
        try:
            fig, ax = plt.subplots(figsize=(9, 4), dpi=dpi)
            
            # Estilo profissional claro
            fig.patch.set_facecolor('#ffffff')
            ax.set_facecolor('#fafafa')
            
            # Eixo X
            if timestamps and len(timestamps) == len(values):
                x_data = timestamps
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.AutoDateLocator())
                xlabel = 'Tempo'
            else:
                x_data = list(range(len(values)))
                xlabel = 'Amostra'
            
            # Cor principal NPA
            main_color = NPAColors.PRIMARY
            
            # Plot baseado no estilo
            if self.config.chart_style == 'scatter':
                ax.scatter(x_data, values, c=main_color, s=15, alpha=0.7, edgecolors='white', linewidth=0.5)
            elif self.config.chart_style == 'area':
                ax.fill_between(x_data, values, alpha=0.3, color=main_color)
                ax.plot(x_data, values, color=main_color, linewidth=1.5)
            else:
                ax.plot(x_data, values, color=main_color, linewidth=1.5, label=description)
            
            # Linhas de referência
            ax.axhline(y=stats.mean_value, color=NPAColors.SECONDARY, linestyle='--', 
                       linewidth=1, alpha=0.7, label=f'Média: {stats.mean_value:.2f}')
            ax.axhline(y=stats.max_value, color=NPAColors.DANGER, linestyle=':', 
                       linewidth=1, alpha=0.5, label=f'Máx: {stats.max_value:.2f}')
            ax.axhline(y=stats.min_value, color=NPAColors.SUCCESS, linestyle=':', 
                       linewidth=1, alpha=0.5, label=f'Mín: {stats.min_value:.2f}')
            
            # Labels
            ylabel = f"{description}"
            if unit:
                ylabel += f" ({unit})"
            ax.set_ylabel(ylabel, fontsize=10, color=NPAColors.TEXT_DARK)
            ax.set_xlabel(xlabel, fontsize=10, color=NPAColors.TEXT_DARK)
            
            # Título
            ax.set_title(f"{description}", fontsize=12, fontweight='bold', 
                        color=NPAColors.PRIMARY, pad=10)
            
            # Grid
            ax.grid(True, alpha=0.3, color='#cccccc', linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True)
            
            # Spines
            for spine in ax.spines.values():
                spine.set_color('#dddddd')
                spine.set_linewidth(0.5)
            
            # Legenda
            ax.legend(loc='upper right', fontsize=8, framealpha=0.9, 
                     facecolor='white', edgecolor='#dddddd')
            
            # Ticks
            ax.tick_params(colors=NPAColors.TEXT_MEDIUM, labelsize=8)
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor='white', edgecolor='none', 
                       bbox_inches='tight', pad_inches=0.1)
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.warning("Erro ao gerar gráfico para %s: %s", field_name, e)
            return None

    def _build_alerts_section(self, styles) -> list:
        """Constrói seção de alertas e anomalias."""
        elements = []
        
        elements.append(Paragraph("4. Registro de Alertas", styles['SectionTitle']))
        
        if not self.alerts_history:
            elements.append(Paragraph(
                "✓ Nenhum alerta foi registrado durante a missão. "
                "Todos os parâmetros permaneceram dentro dos limites estabelecidos.",
                styles['Highlight']
            ))
            elements.append(PageBreak())
            return elements
        
        # Resumo de severidade
        severity_count = {'info': 0, 'warning': 0, 'critical': 0}
        for alert in self.alerts_history:
            sev = alert.severity.lower()
            if sev in severity_count:
                severity_count[sev] += 1
        
        elements.append(Paragraph(
            f"Durante a missão foram registrados <b>{len(self.alerts_history)}</b> alertas, "
            f"sendo <font color='{NPAColors.DANGER}'>{severity_count['critical']} críticos</font>, "
            f"<font color='{NPAColors.WARNING}'>{severity_count['warning']} avisos</font> e "
            f"<font color='{NPAColors.ACCENT}'>{severity_count['info']} informativos</font>.",
            styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        # Tabela de alertas
        table_data = [
            ["Data/Hora", "Campo", "Valor", "Limite", "Severidade"]
        ]
        
        for alert in self.alerts_history[-30:]:  # Últimos 30
            violation = "<" if alert.violation_type == 'min' else ">"
            
            # Cor baseada na severidade
            sev_text = alert.severity.upper()
            
            table_data.append([
                alert.timestamp.strftime('%d/%m %H:%M:%S'),
                alert.description[:20],
                f"{alert.value:.2f}",
                f"{violation} {alert.threshold:.2f}",
                sev_text
            ])
        
        table = Table(table_data, colWidths=[90, 120, 70, 80, 70])
        
        # Estilo base
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.SECONDARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]
        
        # Cores por severidade nas linhas
        for i, alert in enumerate(self.alerts_history[-30:], start=1):
            if alert.severity.lower() == 'critical':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#fed7d7')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor(NPAColors.DANGER)))
            elif alert.severity.lower() == 'warning':
                table_style.append(('BACKGROUND', (4, i), (4, i), colors.HexColor('#fefcbf')))
                table_style.append(('TEXTCOLOR', (4, i), (4, i), colors.HexColor(NPAColors.WARNING)))
        
        table.setStyle(TableStyle(table_style))
        elements.append(table)
        
        if len(self.alerts_history) > 30:
            elements.append(Spacer(1, 0.2*cm))
            elements.append(Paragraph(
                f"<i>Exibindo últimos 30 de {len(self.alerts_history)} alertas registrados.</i>",
                styles['SmallText']
            ))
        
        elements.append(PageBreak())
        return elements

    def _build_gps_section(self, styles) -> list:
        """Constrói seção de trajetória GPS."""
        elements = []
        
        # Busca dados GPS
        lat_data, lon_data = [], []
        
        for source_id in (self.config.selected_sources or self.data_buffer.keys()):
            if source_id not in self.data_buffer:
                continue
            buffer = self.data_buffer[source_id]
            
            for key in ["latitude", "lat", "gps_lat"]:
                if key in buffer and isinstance(buffer[key], list):
                    lat_data.extend(buffer[key])
                    break
            
            for key in ["longitude", "lon", "lng", "gps_lon"]:
                if key in buffer and isinstance(buffer[key], list):
                    lon_data.extend(buffer[key])
                    break
        
        if not lat_data or not lon_data or len(lat_data) != len(lon_data):
            return elements
        
        # Filtra coordenadas válidas
        valid_coords = [(lat, lon) for lat, lon in zip(lat_data, lon_data)
                        if lat != 0 and lon != 0 and -90 <= lat <= 90 and -180 <= lon <= 180]
        
        if len(valid_coords) < 2:
            return elements
        
        elements.append(Paragraph("5. Trajetória GPS", styles['SectionTitle']))
        elements.append(Paragraph(
            f"A missão registrou <b>{len(valid_coords):,}</b> pontos de posição GPS válidos. "
            "O mapa abaixo apresenta a trajetória completa com marcadores de início (verde) e fim (vermelho).",
            styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        lat_vals = [c[0] for c in valid_coords]
        lon_vals = [c[1] for c in valid_coords]
        
        # Tenta gerar mapa com staticmaps
        map_image = None
        if STATICMAPS_AVAILABLE:
            map_image = self._generate_trajectory_map(valid_coords)
        
        if map_image:
            elements.append(Image(map_image, width=450, height=300))
            elements.append(Paragraph(
                "Figura: Trajetória GPS da missão (OpenStreetMap)",
                styles['FigureCaption']
            ))
        else:
            # Fallback para matplotlib
            chart = self._generate_gps_chart(lat_vals, lon_vals)
            if chart:
                elements.append(Image(chart, width=400, height=300))
                elements.append(Paragraph(
                    "Figura: Trajetória GPS da missão",
                    styles['FigureCaption']
                ))
        
        # Estatísticas GPS
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph("<b>Estatísticas de Posição</b>", styles['SubsectionTitle']))
        
        gps_stats = [
            ["Parâmetro", "Valor"],
            ["Total de Pontos", f"{len(valid_coords):,}"],
            ["Latitude Inicial", f"{lat_vals[0]:.6f}°"],
            ["Latitude Final", f"{lat_vals[-1]:.6f}°"],
            ["Longitude Inicial", f"{lon_vals[0]:.6f}°"],
            ["Longitude Final", f"{lon_vals[-1]:.6f}°"],
            ["Range Latitude", f"{min(lat_vals):.6f}° a {max(lat_vals):.6f}°"],
            ["Range Longitude", f"{min(lon_vals):.6f}° a {max(lon_vals):.6f}°"],
        ]
        
        gps_table = Table(gps_stats, colWidths=[150, 200])
        gps_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.PRIMARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), 
             [colors.HexColor(NPAColors.BG_LIGHT), colors.HexColor(NPAColors.WHITE)]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]))
        
        elements.append(gps_table)
        elements.append(PageBreak())
        
        return elements

    def _generate_trajectory_map(self, coords: list[tuple[float, float]]) -> io.BytesIO | None:
        """Gera mapa com trajetória usando staticmaps."""
        if not STATICMAPS_AVAILABLE or not coords or staticmaps is None:
            return None
        
        try:
            context = staticmaps.Context()
            context.set_tile_provider(staticmaps.tile_provider_OSM)
            
            line_coords = [staticmaps.create_latlng(lat, lon) for lat, lon in coords]
            context.add_object(
                staticmaps.Line(
                    line_coords,
                    color=staticmaps.Color(174, 85, 22, 220),  # NPA Orange
                    width=3
                )
            )
            
            if len(coords) >= 2:
                context.add_object(
                    staticmaps.Marker(
                        staticmaps.create_latlng(coords[0][0], coords[0][1]),
                        color=staticmaps.GREEN,
                        size=12
                    )
                )
                context.add_object(
                    staticmaps.Marker(
                        staticmaps.create_latlng(coords[-1][0], coords[-1][1]),
                        color=staticmaps.RED,
                        size=12
                    )
                )
            
            image = context.render_cairo(800, 600)
            buf = io.BytesIO()
            image.write_to_png(buf)
            buf.seek(0)
            return buf
            
        except Exception as e:
            logger.warning("Erro ao gerar mapa: %s", e)
            return None

    def _generate_gps_chart(self, lat_vals: list, lon_vals: list) -> io.BytesIO | None:
        """Gera gráfico de trajetória como fallback."""
        if not MATPLOTLIB_AVAILABLE:
            return None
        
        try:
            fig, ax = plt.subplots(figsize=(8, 6), dpi=120)
            fig.patch.set_facecolor('#ffffff')
            ax.set_facecolor('#fafafa')
            
            ax.plot(lon_vals, lat_vals, color=NPAColors.PRIMARY, linewidth=2, label='Trajetória')
            ax.scatter(lon_vals[0], lat_vals[0], color=NPAColors.SUCCESS, s=100, 
                      zorder=5, label='Início', marker='^', edgecolors='white', linewidth=2)
            ax.scatter(lon_vals[-1], lat_vals[-1], color=NPAColors.DANGER, s=100, 
                      zorder=5, label='Fim', marker='v', edgecolors='white', linewidth=2)
            
            ax.set_xlabel('Longitude', fontsize=10, color=NPAColors.TEXT_DARK)
            ax.set_ylabel('Latitude', fontsize=10, color=NPAColors.TEXT_DARK)
            ax.set_title('Trajetória GPS', fontsize=12, fontweight='bold', color=NPAColors.PRIMARY)
            
            ax.grid(True, alpha=0.3, color='#cccccc')
            ax.legend(loc='upper right', fontsize=9, framealpha=0.9)
            ax.set_aspect('equal', adjustable='box')
            
            for spine in ax.spines.values():
                spine.set_color('#dddddd')
            
            plt.tight_layout()
            
            buf = io.BytesIO()
            plt.savefig(buf, format='png', facecolor='white', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            return buf
            
        except Exception as e:
            logger.warning("Erro ao gerar gráfico GPS: %s", e)
            return None

    def _build_appendix(self, styles) -> list:
        """Constrói apêndice com configurações e metadados."""
        elements = []
        
        elements.append(Paragraph("Apêndice: Configuração do Relatório", styles['SectionTitle']))
        
        elements.append(Paragraph(
            "Esta seção documenta os parâmetros utilizados na geração deste relatório "
            "para fins de rastreabilidade e reprodutibilidade.",
            styles['ReportBody']
        ))
        elements.append(Spacer(1, 0.3*cm))
        
        config_data = [
            ["Parâmetro", "Valor"],
            ["Título do Relatório", self.config.title],
            ["Nome da Missão", self.config.mission_name],
            ["Autor", self.config.author],
            ["Organização", self.config.organization or "NPA-UFG"],
            ["Decoders", ", ".join(self.config.selected_decoders) or "Todos"],
            ["Campos Selecionados", str(len(self.config.selected_fields)) if self.config.selected_fields else "Todos"],
            ["Fontes de Dados", str(len(self.config.selected_sources)) if self.config.selected_sources else "Todas"],
            ["Formato de Página", f"{self.config.page_size} - {self.config.orientation.title()}"],
            ["Estilo de Gráficos", self.config.chart_style.title()],
            ["Resolução", self.config.chart_resolution.title()],
            ["Data de Geração", datetime.now().strftime('%d/%m/%Y %H:%M:%S')],
            ["Versão do Gerador", "2.0.0"],
        ]
        
        config_table = Table(config_data, colWidths=[180, 270])
        config_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(NPAColors.PRIMARY)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), 
             [colors.HexColor(NPAColors.BG_LIGHT), colors.HexColor(NPAColors.WHITE)]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor(NPAColors.BORDER)),
        ]))
        
        elements.append(config_table)
        elements.append(Spacer(1, 1*cm))
        
        # Seções incluídas
        elements.append(Paragraph("<b>Seções Incluídas</b>", styles['SubsectionTitle']))
        
        sections = [
            ("Resumo Executivo", self.config.include_summary),
            ("Estatísticas", self.config.include_statistics),
            ("Gráficos", self.config.include_charts),
            ("Alertas", self.config.include_alerts),
            ("Trajetória GPS", self.config.include_gps_track),
            ("Configuração", self.config.include_config),
        ]
        
        for section_name, included in sections:
            status = "✓ Incluída" if included else "✗ Não incluída"
            color = NPAColors.SUCCESS if included else NPAColors.TEXT_LIGHT
            elements.append(Paragraph(
                f"<font color='{color}'>{status}</font> - {section_name}",
                styles['ReportBody']
            ))
        
        elements.append(Spacer(1, 1*cm))
        
        # Rodapé final
        elements.append(self._create_decorative_line())
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(
            "<b>NPA Ground Station</b> - Sistema de Estação Terrena",
            styles['SmallText']
        ))
        elements.append(Paragraph(
            "Núcleo de Pesquisas Aeroespaciais - Universidade Federal de Goiás",
            styles['SmallText']
        ))
        elements.append(Paragraph(
            f"Relatório gerado automaticamente em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}",
            styles['SmallText']
        ))
        
        return elements


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================
def check_dependencies() -> dict[str, bool]:
    """Verifica dependências disponíveis."""
    return {
        'reportlab': REPORTLAB_AVAILABLE,
        'matplotlib': MATPLOTLIB_AVAILABLE,
        'staticmaps': STATICMAPS_AVAILABLE
    }
