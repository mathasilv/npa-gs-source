# src/npags/reports/__init__.py
"""
Módulo de geração de relatórios PDF.

Gera relatórios profissionais de sessões de telemetria com:
    - Resumo executivo
    - Estatísticas de telemetria
    - Gráficos de dados
    - Registro de alertas
    - Trajetória GPS
"""

from npags.reports.generator import (
    AlertRecord,
    FieldStatistics,
    ReportConfig,
    ReportGenerator,
    check_dependencies,
)

__all__ = [
    'ReportGenerator',
    'ReportConfig',
    'FieldStatistics',
    'AlertRecord',
    'check_dependencies'
]
