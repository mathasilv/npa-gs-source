# src/npags/core/logger.py
"""
Sistema centralizado de logging para dados de telemetria.
Implementa rotação de arquivos para evitar consumo excessivo de disco.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Diretório padrão de logs
_LOG_DIR = Path('data/logs')
_CURRENT_LOG_PATH: Path | None = None


def get_log_directory() -> Path:
    """
    Retorna o diretório de logs.

    Returns:
        Path: Caminho do diretório de logs.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def get_current_log_path() -> Path | None:
    """
    Retorna o caminho do arquivo de log atual.

    Returns:
        Path ou None: Caminho do arquivo de log atual.
    """
    if _CURRENT_LOG_PATH and _CURRENT_LOG_PATH.exists():
        return _CURRENT_LOG_PATH

    # Fallback: retorna o arquivo padrão se existir
    default_path = _LOG_DIR / 'station_data.jsonl'
    if default_path.exists():
        return default_path
    return None


def get_logger(name: str) -> logging.Logger:
    """
    Retorna um logger padrão.

    Args:
        name: Nome do logger.

    Returns:
        Logger configurado.
    """
    return logging.getLogger(name)


def setup_telemetry_logger(
    name: str = 'TelemetryData',
    log_file: str = 'station_data.jsonl'
) -> logging.Logger:
    """
    Cria ou recupera um logger configurado para salvar dados em JSONL.

    Args:
        name (str): Identificador único do logger.
        log_file (str): Nome do arquivo (salvo em data/logs/).

    Returns:
        logging.Logger: Logger pronto para uso.
    """
    global _CURRENT_LOG_PATH

    # Garante criação da pasta
    log_dir = get_log_directory()
    log_path = log_dir / log_file

    # Registra o caminho atual
    _CURRENT_LOG_PATH = log_path

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Padrão Singleton: Configura apenas se ainda não tiver handlers
    if not logger.handlers:
        # Rotação: 5MB por arquivo, mantém os últimos 5 arquivos
        handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        # Formatter simples: grava apenas a mensagem (JSON) sem timestamps do logging
        # (pois o JSON interno já tem timestamps precisos)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)

    return logger
