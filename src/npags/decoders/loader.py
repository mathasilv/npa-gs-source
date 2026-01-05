# src/npags/decoders/loader.py
"""
Gerenciamento e carregamento de schemas YAML para os decoders.
Utiliza caminhos relativos ao pacote para garantir portabilidade.
"""

import glob
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class DecoderLoader:
    """
    Carrega, valida, salva e exclui arquivos de definição de decoders (.yaml).

    Attributes:
        decoder_path: Caminho para o diretório de schemas.
    """

    def __init__(self, decoder_path: Path | None = None) -> None:
        """
        Inicializa o loader.
        
        Args:
            decoder_path: Caminho customizado para os schemas. 
                          Se None, usa o diretório padrão 'config/decoder_schemas' do pacote.
        """
        if decoder_path is None:
            # Localiza a raiz do pacote 'npags' dinamicamente
            package_root = Path(__file__).resolve().parent.parent
            self.decoder_path = package_root / "config" / "decoder_schemas"
        else:
            self.decoder_path = decoder_path
        
        # Garante a existência do diretório
        self.decoder_path.mkdir(parents=True, exist_ok=True)
        logger.debug("DecoderLoader inicializado em: %s", self.decoder_path)

    def scan_decoders(self) -> list[str]:
        """
        Retorna lista de nomes dos decoders disponíveis (sem a extensão .yaml).
        """
        pattern = str(self.decoder_path / "*.yaml")
        files = glob.glob(pattern)
        decoder_names = [Path(f).stem for f in files]
        logger.debug("Decoders encontrados: %s", decoder_names)
        return decoder_names

    def get_decoder_path(self, decoder_name: str) -> Path:
        """Retorna o caminho completo (Path) para um arquivo de decoder."""
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
        """Lê o conteúdo textual de um decoder."""
        try:
            decoder_path = self.get_decoder_path(decoder_name)
            if not decoder_path.exists():
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
