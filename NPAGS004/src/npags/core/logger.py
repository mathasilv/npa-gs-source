# src/npags/core/logger.py
"""
Sistema centralizado de logging para dados de telemetria.
Implementa rotação de arquivos para evitar consumo excessivo de disco.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_telemetry_logger(name='TelemetryData', log_file='station_data.jsonl'):
    """
    Cria ou recupera um logger configurado para salvar dados em JSONL.
    
    Args:
        name (str): Identificador único do logger.
        log_file (str): Nome do arquivo (salvo em data/logs/).
        
    Returns:
        logging.Logger: Logger pronto para uso.
    """
    # Garante criação da pasta
    log_dir = Path('data/logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = log_dir / log_file
    
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