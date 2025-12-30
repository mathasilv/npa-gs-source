# src/npags/core/multi_decoder.py
"""
Motor de decodificação múltipla.
Permite tentar vários schemas diferentes em um mesmo pacote até encontrar um compatível.
"""

from npags.decoders.loader import DecoderLoader
from npags.core.decoder_engine import DecoderEngine

class MultiDecoderEngine:
    """
    Fachada que gerencia múltiplos DecoderEngines.
    Útil quando a estação recebe dados de fontes desconhecidas ou mistas.
    """
    
    def __init__(self):
        self.loader = DecoderLoader()
        self.engines = {}
        self._load_engines()
        
    def _load_engines(self):
        """Inicializa todos os decoders encontrados na pasta de configuração."""
        decoder_names = self.loader.scan_decoders()
        # Opcional: Converter print para log se desejar silêncio no console
        print(f"Carregando {len(decoder_names)} decoders para o modo Auto-Detect...")
        
        for name in decoder_names:
            try:
                path = self.loader.get_decoder_path(name)
                self.engines[name] = DecoderEngine(path)
            except Exception as e:
                print(f"Aviso: Falha ao carregar decoder '{name}': {e}")
                
    def get_loaded_decoders(self):
        """Retorna lista de nomes dos decoders ativos."""
        return list(self.engines.keys())

    def decode_payload(self, data):
        """
        Itera sobre todos os decoders disponíveis.
        
        Returns:
            dict: Resultado do primeiro decoder que validar o pacote com sucesso.
                  Se nenhum funcionar, retorna um relatório de erros.
        """
        tried_decoders = []
        
        for name, engine in self.engines.items():
            result = engine.decode_payload(data)
            
            # Se não houve erro, encontramos o decoder correto
            if 'error' not in result:
                result['matched_decoder'] = name
                return result
            
            tried_decoders.append(name)
            
        # Falha total
        return {
            'error': 'Nenhum decoder compatível encontrado (Magic Bytes ou Estrutura inválida)',
            'tried_decoders': tried_decoders,
            'decoder': 'MultiDecoder'
        }

    def format_output(self, decoded_data, output_format='text'):
        """
        Delega a formatação visual para o decoder específico que processou o pacote.
        Mantém compatibilidade com a interface do DecoderEngine.
        """
        decoder_name = decoded_data.get('matched_decoder')
        
        # 1. Delegação Direta (Caminho Feliz)
        if decoder_name and decoder_name in self.engines:
            return self.engines[decoder_name].format_output(decoded_data, output_format)
            
        # 2. Fallback Genérico (Se não soubermos quem decodificou)
        if self.engines:
            first_engine = next(iter(self.engines.values()))
            return first_engine.format_output(decoded_data, output_format)
            
        return str(decoded_data)