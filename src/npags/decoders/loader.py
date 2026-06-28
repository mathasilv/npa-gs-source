# src/npags/decoders/loader.py
"""
Gerenciamento e carregamento de schemas YAML para os decoders.
Utiliza diretório persistente do usuário para decoders customizados
e mantém os schemas embutidos do pacote como fallback somente leitura.
"""

import logging
import os
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def _resolve_user_decoder_dir() -> Path:
    """
    Retorna o diretório persistente para decoders do usuário.
      - Linux/Mac: $XDG_DATA_HOME/npags/decoders  (padrão ~/.local/share/npags/decoders)
      - Windows  : %APPDATA%/npags/decoders
      - Fallback : ~/.npags/decoders
    """
    xdg = os.environ.get("XDG_DATA_HOME", "")
    if xdg:
        base = Path(xdg)
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        base = Path(appdata) if appdata else Path.home()
    else:
        base = Path.home() / ".local" / "share"
    return base / "npags" / "decoders"


def _resolve_bundled_decoder_dir() -> Path:
    """Retorna o diretório dos schemas embutidos no pacote."""
    return Path(__file__).resolve().parent.parent / "config" / "decoder_schemas"


class DecoderLoader:
    """
    Carrega, valida, salva e exclui arquivos de definição de decoders (.yaml).

    Attributes:
        decoder_path: Caminho para o diretório persistente de schemas do usuário.
        bundled_path: Caminho para os schemas embutidos no pacote (somente leitura).
    """

    def __init__(self, decoder_path: Path | None = None) -> None:
        """
        Inicializa o loader.
        
        Args:
            decoder_path: Caminho customizado para os schemas. 
                          Se None, usa o diretório persistente do usuário.
        """
        if decoder_path is None:
            self.decoder_path = _resolve_user_decoder_dir()
        else:
            self.decoder_path = decoder_path

        self.bundled_path = _resolve_bundled_decoder_dir()
        
        self.decoder_path.mkdir(parents=True, exist_ok=True)
        logger.debug("DecoderLoader: usuário=%s | bundled=%s", self.decoder_path, self.bundled_path)

    def scan_decoders(self) -> list[str]:
        """
        Retorna lista de nomes dos decoders disponíveis (sem a extensão .yaml).
        Busca tanto no diretório do usuário quanto nos schemas embutidos.
        Decoders do usuário sobrescrevem homônimos bundled.
        """
        seen: set[str] = set()
        result: list[str] = []
        for base in (self.decoder_path, self.bundled_path):
            if not base.is_dir():
                continue
            for f in sorted(base.iterdir()):
                if f.suffix == ".yaml" and f.stem not in seen:
                    seen.add(f.stem)
                    result.append(f.stem)
        logger.debug("Decoders encontrados: %s", result)
        return result

    def find_decoder_path(self, decoder_name: str) -> Path | None:
        """
        Busca um decoder pelo nome, retornando o caminho.
        Prioriza o diretório do usuário sobre o bundled.
        Retorna None se não encontrado.
        """
        user_path = self.decoder_path / f"{decoder_name}.yaml"
        if user_path.is_file():
            return user_path
        bundled_path = self.bundled_path / f"{decoder_name}.yaml"
        if bundled_path.is_file():
            return bundled_path
        return None

    def get_decoder_path(self, decoder_name: str) -> Path:
        """Retorna o caminho completo (apenas diretório do usuário) para um arquivo de decoder."""
        return self.decoder_path / f"{decoder_name}.yaml"
    
    def validate_yaml(self, content: str) -> tuple[bool, str | None]:
        """Valida a sintaxe de uma string YAML."""
        try:
            yaml.safe_load(content)
            return True, None
        except yaml.YAMLError as e:
            logger.warning("YAML inválido: %s", e)
            return False, str(e)
    
    def save_decoder(self, decoder_name: str, content: str) -> tuple[bool, str | None]:
        """Salva um novo decoder ou sobrescreve existente após validação."""
        valid, error = self.validate_yaml(content)
        if not valid:
            return False, f"YAML inválido: {error}"
        
        try:
            decoder_path = self.get_decoder_path(decoder_name)
            with open(decoder_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info("Decoder salvo: %s", decoder_path)
            return True, None
        except OSError as e:
            logger.error("Erro ao salvar decoder '%s': %s", decoder_name, e)
            return False, f"Erro ao salvar arquivo: {e}"

    def load_decoder(self, decoder_name: str) -> tuple[bool, str, str | None]:
        """Lê o conteúdo textual de um decoder. Busca no user dir e no bundled."""
        try:
            decoder_path = self.find_decoder_path(decoder_name)
            if decoder_path is None:
                logger.warning("Decoder não encontrado: %s", decoder_name)
                return False, "", f"Decoder '{decoder_name}' não encontrado"
            
            with open(decoder_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.debug("Decoder carregado: %s", decoder_name)
            return True, content, None
        except OSError as e:
            logger.error("Erro ao ler decoder '%s': %s", decoder_name, e)
            return False, "", f"Erro ao ler arquivo: {e}"

    def delete_decoder(self, decoder_name: str) -> tuple[bool, str | None]:
        """Exclui permanentemente um arquivo de decoder."""
        try:
            path = self.get_decoder_path(decoder_name)
            if not path.exists():
                logger.warning("Tentativa de excluir decoder inexistente: %s", decoder_name)
                return False, "Arquivo não encontrado."

            path.unlink()
            logger.info("Decoder excluído: %s", decoder_name)
            return True, None
        except OSError as e:
            logger.error("Erro ao excluir decoder '%s': %s", decoder_name, e)
            return False, f"Erro ao excluir: {e}"
    
    def get_template(self) -> str:
        """Retorna um template básico para criação de novos decoders."""
        return """# Template de Decoder
name: "Novo Decoder"
version: "1.0"
description: "Descrição do protocolo"

# Configuração do Header
header:
  fields:
    - name: magic_byte
      type: uint8
      expected: 0xAB
      description: "Identificador de início"
    - name: device_id
      type: uint16be
      description: "ID do dispositivo"

# Estrutura do Payload
payload:
  - name: sensor_data
    fields:
      - name: temp
        type: int16be
        scale: 0.1
        unit: "°C"
        format: "{:.1f}"
        description: "Temperatura Ambiente"
"""
