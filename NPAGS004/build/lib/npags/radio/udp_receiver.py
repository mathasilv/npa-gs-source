"""
Receptor UDP executado em thread separada.
"""

import socket
import threading
from typing import Callable

class UDPReceiver(threading.Thread):
    """Receptor UDP Thread-Safe para captura de pacotes de rede."""
    
    def __init__(self, ip: str, port: int, callback_packet: Callable[[bytes], None]):
        """
        Inicializa e configura o socket.
        
        Args:
            ip: Endereço de bind (ex: '0.0.0.0' ou '127.0.0.1')
            port: Porta de escuta
            callback_packet: Função a ser chamada quando um datagrama chega.
        """
        super().__init__(daemon=True)
        self.ip = ip
        self.port = port
        self.callback = callback_packet
        self.running = True
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Timeout permite que a thread verifique self.running periodicamente
        self.sock.settimeout(1.0)
    
    def run(self):
        """Loop principal da thread."""
        try:
            self.sock.bind((self.ip, self.port))
            print(f"UDP Receiver ativo em {self.ip}:{self.port}")
        except Exception as e:
            print(f"Falha ao iniciar bind UDP: {e}")
            return
        
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if data:
                    self.callback(data)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"Erro na recepção UDP: {e}")
                break
        
        self.sock.close()
        print("UDP Receiver encerrado.")
    
    def stop(self):
        """Sinaliza para a thread parar."""
        self.running = Falses