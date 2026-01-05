"""Receptor UDP executado em thread separada."""

import logging
import socket
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class UDPReceiver(threading.Thread):
    """
    Receptor UDP Thread-Safe para captura de pacotes de rede.

    Executa em thread daemon separada, recebendo datagramas UDP
    e encaminhando para um callback.

    Attributes:
        ip: Endereço de bind.
        port: Porta de escuta.
        running: Flag de controle do loop.
    """

    def __init__(
        self, ip: str, port: int, callback_packet: Callable[[bytes], None]
    ) -> None:
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
        # Permite reutilizar o endereço imediatamente após fechar
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Timeout permite que a thread verifique self.running periodicamente
        self.sock.settimeout(1.0)
    
    def run(self) -> None:
        """Loop principal da thread."""
        try:
            self.sock.bind((self.ip, self.port))
            logger.info("UDP Receiver ativo em %s:%d", self.ip, self.port)
        except OSError as e:
            logger.error("Falha ao iniciar bind UDP em %s:%d: %s", self.ip, self.port, e)
            return
        
        packets_received = 0
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                if data:
                    packets_received += 1
                    logger.debug(
                        "Pacote #%d recebido de %s:%d (%d bytes)",
                        packets_received,
                        addr[0],
                        addr[1],
                        len(data),
                    )
                    self.callback(data)
            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    logger.error("Erro na recepção UDP: %s", e)
                break
    
        logger.info(
            "UDP Receiver encerrado. Total de pacotes recebidos: %d", packets_received
        )

    def stop(self) -> None:
        """Sinaliza para a thread parar e fecha o socket."""
        logger.debug("Solicitado encerramento do UDP Receiver")
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass

    def wait(self, timeout: float | None = None) -> None:
        """
        Aguarda a thread terminar.

        Args:
            timeout: Tempo máximo de espera em segundos.
        """
        self.join(timeout=timeout)
