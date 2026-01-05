#!/usr/bin/env python3
"""
Formatador de Telemetria - Estilo Terminal Linux.
Logs limpos sem emojis ou ASCII art.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SessionStats:
    """Estatísticas da sessão de telemetria."""
    
    start_time: datetime = field(default_factory=datetime.now)
    total_packets: int = 0
    total_bytes: int = 0
    valid_packets: int = 0
    invalid_packets: int = 0
    _packet_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_packet(self, size: int, valid: bool = True) -> None:
        now = datetime.now()
        self.total_packets += 1
        self.total_bytes += size
        if valid:
            self.valid_packets += 1
        else:
            self.invalid_packets += 1
        self._packet_times.append(now)
    
    @property
    def uptime_str(self) -> str:
        total_seconds = int((datetime.now() - self.start_time).total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @property
    def packet_rate(self) -> float:
        if len(self._packet_times) < 2:
            return 0.0
        now = datetime.now()
        recent = [t for t in self._packet_times if (now - t).total_seconds() <= 10]
        if len(recent) < 2:
            return 0.0
        time_span: float = (recent[-1] - recent[0]).total_seconds()
        if time_span <= 0:
            return 0.0
        return float((len(recent) - 1) / time_span)
    
    @property
    def success_rate(self) -> float:
        if self.total_packets == 0:
            return 100.0
        return (self.valid_packets / self.total_packets) * 100
    
    @property
    def avg_packet_size(self) -> float:
        if self.total_packets == 0:
            return 0.0
        return self.total_bytes / self.total_packets


@dataclass
class PacketInfo:
    """Informações de um pacote."""
    sequence: int
    timestamp: datetime
    size: int
    raw_hex: str
    decoded: dict[str, Any]
    valid: bool = True
    error: str | None = None
    rssi: int | None = None


class TelemetryFormatter:
    """Formatador de logs estilo terminal Linux."""
    
    def __init__(self, decoder_name: str = "Unknown") -> None:
        self.decoder_name = decoder_name
        self.stats = SessionStats()
        self._field_cache: dict[str, dict[str, Any]] = {}
    
    def set_field_cache(self, cache: dict[str, dict[str, Any]]) -> None:
        self._field_cache = cache
    
    def reset_session(self) -> None:
        self.stats = SessionStats()
    
    def format_packet(self, packet_info: PacketInfo) -> str:
        """Formata um pacote para o log."""
        self.stats.record_packet(packet_info.size, packet_info.valid)
        
        lines: list[str] = []
        ts = packet_info.timestamp.strftime("%H:%M:%S")
        rssi_str = f"{packet_info.rssi}dBm" if packet_info.rssi else "--"
        
        if not packet_info.valid:
            lines.append(f"[{ts}] ERR #{packet_info.sequence:05d}  {packet_info.size}B  {rssi_str}  {packet_info.error}")
            lines.append(f"           RAW: {packet_info.raw_hex}")
            return '\n'.join(lines)
        
        main_values = self._extract_main_values(packet_info.decoded)
        lines.append(f"[{ts}] OK  #{packet_info.sequence:05d}  {packet_info.size}B  {rssi_str}  {main_values}")
        lines.extend(self._format_details(packet_info.decoded))
        
        return '\n'.join(lines)
    
    def _extract_main_values(self, decoded: dict[str, Any]) -> str:
        """Extrai valores principais para o resumo."""
        parts = []
        priority_fields = ['battery', 'temperature', 'altitude', 'satellites']
        
        for section_data in decoded.values():
            if not isinstance(section_data, dict):
                continue
            for fld in priority_fields:
                if fld in section_data:
                    value = section_data[fld]
                    formatted = self._format_value_short(fld, value)
                    if formatted:
                        parts.append(formatted)
        
        for section_name, section_data in decoded.items():
            if 'relay' in section_name.lower() and isinstance(section_data, list):
                if len(section_data) > 0:
                    parts.append(f"+{len(section_data)}nodes")
        
        return '  '.join(parts)
    
    def _format_value_short(self, key: str, value: Any) -> str:
        """Formata valor curto."""
        if value is None:
            return ""
        
        field_cfg = self._field_cache.get(key, {})
        unit = field_cfg.get('unit', '')
        
        key_short = {
            'battery': 'bat', 'temperature': 'temp', 'altitude': 'alt',
            'satellites': 'sats', 'pressure': 'pres', 'humidity': 'hum',
        }.get(key, key[:4])
        
        if isinstance(value, float):
            if value == 0:
                return f"{key_short}:0{unit}"
            return f"{key_short}:{value:.1f}{unit}"
        
        return f"{key_short}:{value}{unit}"
    
    def _format_details(self, decoded: dict[str, Any]) -> list[str]:
        """Formata detalhes do pacote."""
        lines = []
        indent = "           "
        shown_fields = {'battery', 'temperature', 'altitude', 'satellites'}
        
        sat_values = []
        for section_name, section_data in decoded.items():
            if section_name in ['decoder', 'version', 'header', 'error', 'partial', '_meta']:
                continue
            if 'relay' in section_name.lower():
                continue
            
            if isinstance(section_data, dict):
                for key, value in section_data.items():
                    if key == 'gps_map' or key in shown_fields:
                        continue
                    formatted = self._format_field_value(key, value)
                    sat_values.append(f"{key}:{formatted}")
        
        if sat_values:
            current_line: list[str] = []
            current_len = 0
            for val in sat_values:
                if current_len + len(val) + 2 > 70:
                    lines.append(indent + "  ".join(current_line))
                    current_line = [val]
                    current_len = len(val)
                else:
                    current_line.append(val)
                    current_len += len(val) + 2
            if current_line:
                lines.append(indent + "  ".join(current_line))
        
        for section_name, section_data in decoded.items():
            if 'relay' in section_name.lower() and isinstance(section_data, list):
                for item in section_data:
                    if isinstance(item, dict):
                        node_id = item.get('node_id', item.get('id', '?'))
                        node_parts = []
                        for key, value in item.items():
                            if key in ['node_id', 'id']:
                                continue
                            short_key = {
                                'soil_moisture': 'soil', 'ambient_temp': 'temp',
                                'node_humidity': 'hum', 'irrigation_status': 'irrig'
                            }.get(key, key)
                            formatted = self._format_field_value(key, value)
                            node_parts.append(f"{short_key}:{formatted}")
                        lines.append(f"{indent}  node/{node_id}: " + "  ".join(node_parts))
        
        return lines
    
    def _format_field_value(self, key: str, value: Any) -> str:
        """Formata um valor de campo."""
        if value is None:
            return "N/A"
        
        field_cfg = self._field_cache.get(key, {})
        unit = field_cfg.get('unit', '')
        mapping = field_cfg.get('mapping', {})
        
        if mapping and value in mapping:
            return str(mapping[value])
        
        if isinstance(value, float):
            if 'lat' in key.lower() or 'lon' in key.lower():
                return f"{value:.6f}"
            if value == 0:
                return f"0{unit}"
            if abs(value) < 0.01:
                return f"{value:.3f}{unit}"
            return f"{value:.2f}{unit}"
        
        if isinstance(value, int):
            if 'sync' in key.lower():
                return f"0x{value:04X}"
            return f"{value}{unit}"
        
        return f"{value}{unit}"
    
    def format_session_summary(self) -> str:
        """Resumo da sessão."""
        s = self.stats
        return (
            f"\n--- SESSION SUMMARY ---\n"
            f"  decoder:    {self.decoder_name}\n"
            f"  duration:   {s.uptime_str}\n"
            f"  packets:    {s.total_packets} ({s.valid_packets} ok, {s.invalid_packets} errors)\n"
            f"  success:    {s.success_rate:.1f}%\n"
            f"  bytes:      {s.total_bytes} ({s.total_bytes/1024:.1f} KB)\n"
            f"  avg size:   {s.avg_packet_size:.1f} bytes\n"
            f"  rate:       {s.packet_rate:.2f} pkt/s\n"
            f"-----------------------\n"
        )


def create_packet_info(
    sequence: int,
    raw_data: bytes,
    decoded: dict[str, Any],
    rssi: int | None = None,
) -> PacketInfo:
    """Cria PacketInfo."""
    has_error = 'error' in decoded
    return PacketInfo(
        sequence=sequence,
        timestamp=datetime.now(),
        size=len(raw_data),
        raw_hex=raw_data.hex().upper(),
        decoded=decoded,
        valid=not has_error,
        error=decoded.get('error'),
        rssi=rssi
    )
