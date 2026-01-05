"""
Sistema de internacionalização (i18n) do NPA Ground Station.

Suporta:
    - Português Brasileiro (pt_BR) - idioma base (código fonte)
    - Inglês Americano (en_US) - tradução via en_US.ts

Uso:
    from npags.gui.translations import tr, set_language, get_available_languages
    
    # Traduzir uma string
    text = tr("Exportar Dados")
    
    # Mudar idioma
    set_language("en_US")
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)

# Diretório das traduções
TRANSLATIONS_DIR = Path(__file__).parent

# Idiomas disponíveis
AVAILABLE_LANGUAGES = {
    "pt_BR": "Português (Brasil)",
    "en_US": "English (US)",
}

# Idioma padrão (código fonte)
DEFAULT_LANGUAGE = "pt_BR"

# Cache de traduções: {lang_code: {source_text: translated_text}}
_translations: dict[str, dict[str, str]] = {}
_current_language: str = DEFAULT_LANGUAGE
_settings_key = "app/language"


def get_available_languages() -> dict[str, str]:
    """Retorna os idiomas disponíveis."""
    return AVAILABLE_LANGUAGES.copy()


def get_current_language() -> str:
    """Retorna o código do idioma atual."""
    return _current_language


def _load_ts_file(filepath: Path) -> dict[str, str]:
    """Carrega traduções de um arquivo .ts (XML)."""
    translations = {}
    
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        for context in root.findall("context"):
            for message in context.findall("message"):
                source = message.find("source")
                translation = message.find("translation")
                
                if source is not None and translation is not None:
                    src_text = source.text or ""
                    trans_text = translation.text or ""
                    
                    if src_text and trans_text:
                        translations[src_text] = trans_text
        
        logger.info(f"Carregadas {len(translations)} traduções de {filepath.name}")
        
    except ET.ParseError as e:
        logger.error(f"Erro ao parsear {filepath}: {e}")
    except Exception as e:
        logger.error(f"Erro ao carregar {filepath}: {e}")
    
    return translations


def _save_language_preference(language_code: str) -> None:
    """Salva preferência de idioma."""
    try:
        from PyQt6.QtCore import QSettings
        settings = QSettings("NPA_UFG", "GroundStation")
        settings.setValue(_settings_key, language_code)
        settings.sync()
    except Exception as e:
        logger.warning(f"Não foi possível salvar preferência de idioma: {e}")


def _load_language_preference() -> str:
    """Carrega preferência de idioma salva."""
    try:
        from PyQt6.QtCore import QSettings
        settings = QSettings("NPA_UFG", "GroundStation")
        lang = settings.value(_settings_key, DEFAULT_LANGUAGE)
        if lang in AVAILABLE_LANGUAGES:
            return lang
    except Exception as e:
        logger.warning(f"Não foi possível carregar preferência de idioma: {e}")
    return DEFAULT_LANGUAGE


def set_language(language_code: str, save: bool = True) -> bool:
    """
    Define o idioma da aplicação.
    
    Args:
        language_code: Código do idioma (ex: "pt_BR", "en_US")
        save: Se True, salva a preferência para próximas sessões
        
    Returns:
        True se o idioma foi carregado com sucesso
    """
    global _current_language
    
    if language_code not in AVAILABLE_LANGUAGES:
        logger.warning(f"Idioma não suportado: {language_code}")
        return False
    
    # Se for o idioma padrão (pt_BR), não precisa carregar traduções
    if language_code == DEFAULT_LANGUAGE:
        _current_language = language_code
        if save:
            _save_language_preference(language_code)
        logger.info(f"Idioma definido: {language_code} (padrão)")
        return True
    
    # Verifica se já está em cache
    if language_code not in _translations:
        # Carrega o arquivo de tradução .ts
        ts_file = TRANSLATIONS_DIR / f"{language_code}.ts"
        
        if not ts_file.exists():
            logger.error(f"Arquivo de tradução não encontrado: {ts_file}")
            return False
        
        translations = _load_ts_file(ts_file)
        
        if not translations:
            logger.error(f"Falha ao carregar idioma: {language_code}")
            return False
        
        _translations[language_code] = translations
    
    _current_language = language_code
    if save:
        _save_language_preference(language_code)
    logger.info(f"Idioma carregado: {language_code} ({len(_translations[language_code])} strings)")
    return True


def init_language() -> None:
    """
    Inicializa o sistema de tradução carregando a preferência salva.
    Deve ser chamado após QApplication ser criada.
    """
    saved_lang = _load_language_preference()
    if saved_lang != DEFAULT_LANGUAGE:
        set_language(saved_lang, save=False)
        logger.info(f"Idioma restaurado da preferência: {saved_lang}")


def tr(text: str, context: str = "") -> str:
    """
    Traduz uma string.
    
    Args:
        text: Texto a ser traduzido (em português)
        context: Contexto (ignorado, para compatibilidade)
        
    Returns:
        Texto traduzido ou original se não houver tradução
    """
    if _current_language == DEFAULT_LANGUAGE:
        return text
    
    translations = _translations.get(_current_language, {})
    return translations.get(text, text)


def reload_translations() -> None:
    """Recarrega todas as traduções do disco."""
    global _translations
    _translations.clear()
    
    if _current_language != DEFAULT_LANGUAGE:
        set_language(_current_language, save=False)


__all__ = [
    "tr",
    "set_language",
    "get_current_language",
    "get_available_languages",
    "reload_translations",
    "init_language",
    "AVAILABLE_LANGUAGES",
    "DEFAULT_LANGUAGE",
]
