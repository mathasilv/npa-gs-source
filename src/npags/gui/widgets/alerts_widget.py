# src/npags/gui/widgets/alerts_widget.py
"""
Sistema de Alertas e Alarmes.

Componentes:
    - AlertEngine: Motor que verifica valores e dispara alertas
    - AlertNotification: Pop-up de notificação
    - AlertNotificationManager: Gerencia pop-ups empilhados
    - AlertConfig: Configuração de um alerta

Design agnóstico: alertas são configurados pelo usuário para qualquer campo.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QEasingCurve, QObject, QPoint, QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from npags.gui.styles import THEME_COLORS

# Caminho para ícones SVG
ASSETS_DIR = Path(__file__).parent.parent / "assets"


class AlertSeverity(Enum):
    """Níveis de severidade dos alertas."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertConfig:
    """
    Configuração de um alerta para um campo específico.

    Attributes:
        field_name: Nome do campo monitorado
        description: Descrição amigável do alerta
        min_value: Valor mínimo (abaixo dispara alerta)
        max_value: Valor máximo (acima dispara alerta)
        severity: Nível de severidade
        sound_enabled: Se deve tocar som ao disparar
        enabled: Se o alerta está ativo
    """
    field_name: str
    description: str = ""
    min_value: float | None = None
    max_value: float | None = None
    severity: AlertSeverity = AlertSeverity.WARNING
    sound_enabled: bool = True
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário (para salvar)."""
        return {
            'field_name': self.field_name,
            'description': self.description,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'severity': self.severity.value,
            'sound_enabled': self.sound_enabled,
            'enabled': self.enabled
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertConfig:
        """Cria a partir de dicionário."""
        return cls(
            field_name=data['field_name'],
            description=data.get('description', ''),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            severity=AlertSeverity(data.get('severity', 'warning')),
            sound_enabled=data.get('sound_enabled', True),
            enabled=data.get('enabled', True)
        )


@dataclass
class AlertHistoryEntry:
    """
    Entrada no histórico de alertas.

    Attributes:
        field_name: Nome do campo
        description: Descrição do alerta
        triggered_at: Quando foi disparado
        cleared_at: Quando foi resolvido (None se ainda ativo)
        value: Valor que disparou
        threshold: Limite violado
        violation_type: 'min' ou 'max'
        severity: Severidade do alerta
    """
    field_name: str
    description: str
    triggered_at: datetime
    cleared_at: datetime | None
    value: float
    threshold: float
    violation_type: str
    severity: AlertSeverity

    def to_dict(self) -> dict[str, Any]:
        """Converte para dicionário."""
        return {
            'field_name': self.field_name,
            'description': self.description,
            'triggered_at': self.triggered_at.isoformat(),
            'cleared_at': self.cleared_at.isoformat() if self.cleared_at else None,
            'value': self.value,
            'threshold': self.threshold,
            'violation_type': self.violation_type,
            'severity': self.severity.value
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertHistoryEntry:
        """Cria a partir de dicionário."""
        return cls(
            field_name=data['field_name'],
            description=data.get('description', ''),
            triggered_at=datetime.fromisoformat(data['triggered_at']),
            cleared_at=datetime.fromisoformat(data['cleared_at']) if data.get('cleared_at') else None,
            value=data['value'],
            threshold=data['threshold'],
            violation_type=data['violation_type'],
            severity=AlertSeverity(data.get('severity', 'warning'))
        )


@dataclass
class ActiveAlert:
    """
    Representa um alerta ativo (disparado).

    Attributes:
        config: Configuração do alerta
        triggered_at: Quando foi disparado
        current_value: Valor que disparou o alerta
        violation_type: Tipo de violação ('min' ou 'max')
        acknowledged: Se foi reconhecido pelo usuário
    """
    config: AlertConfig
    triggered_at: datetime
    current_value: float
    violation_type: str  # 'min' ou 'max'
    acknowledged: bool = False

    @property
    def message(self) -> str:
        """Gera mensagem descritiva do alerta."""
        field = self.config.description or self.config.field_name
        if self.violation_type == 'min':
            return f"{field}: {self.current_value:.2f} (abaixo de {self.config.min_value})"
        else:
            return f"{field}: {self.current_value:.2f} (acima de {self.config.max_value})"

    @property
    def title(self) -> str:
        """Título curto do alerta."""
        return self.config.description or self.config.field_name


class AlertNotification(QFrame):
    """
    Pop-up de notificação de alerta.
    Aparece no canto superior direito e desaparece após um tempo.
    """

    closed = pyqtSignal(object)  # self

    # Ícones SVG por severidade (nome do arquivo em assets/)
    ICONS = {
        AlertSeverity.INFO: "alert_info.svg",
        AlertSeverity.WARNING: "alert_warning.svg",
        AlertSeverity.CRITICAL: "alert_critical.svg"
    }

    # Cores por severidade
    COLORS = {
        AlertSeverity.INFO: THEME_COLORS['accent'],
        AlertSeverity.WARNING: '#FFA500',
        AlertSeverity.CRITICAL: '#FF4444'
    }

    def __init__(
        self,
        alert: ActiveAlert,
        parent: QWidget | None = None,
        auto_close: bool = True,
        duration: int = 5000
    ) -> None:
        super().__init__(parent)
        self.alert = alert
        self.auto_close = auto_close
        self.duration = duration

        self._setup_ui()

        if auto_close:
            QTimer.singleShot(duration, self._start_fade_out)

    def _setup_ui(self) -> None:
        """Configura a interface do pop-up."""
        self.setObjectName("AlertNotification")
        self.setFixedWidth(320)
        self.setMinimumHeight(80)

        color = self.COLORS.get(self.alert.config.severity, '#FFA500')

        # Cursor de mão para indicar que é clicável
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet(f"""
            QFrame#AlertNotification {{
                background-color: {THEME_COLORS['surface_secondary']};
                border: 1px solid {color};
                border-left: 4px solid {color};
                border-radius: 4px;
            }}
            QFrame#AlertNotification:hover {{
                background-color: {THEME_COLORS['surface_tertiary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Ícone
        icon_label = QLabel()
        icon_path = ASSETS_DIR / self.ICONS.get(self.alert.config.severity, "alert_warning.svg")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            # Fallback: texto simples
            severity_text = {
                AlertSeverity.INFO: "ℹ",
                AlertSeverity.WARNING: "⚠",
                AlertSeverity.CRITICAL: "⛔"
            }
            icon_label.setText(severity_text.get(self.alert.config.severity, "⚠"))
            icon_label.setStyleSheet(f"""
                color: {color};
                font-size: 20px;
                min-width: 24px;
                max-width: 24px;
            """)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label.setFixedSize(24, 24)
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignTop)

        # Conteúdo
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)

        # Título
        title_label = QLabel(self.alert.title)
        title_label.setStyleSheet(f"color: {THEME_COLORS['text']}; font-size: 13px; font-weight: bold;")
        content_layout.addWidget(title_label)

        # Mensagem
        msg_label = QLabel(self.alert.message)
        msg_label.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 11px;")
        msg_label.setWordWrap(True)
        content_layout.addWidget(msg_label)

        # Timestamp
        time_label = QLabel(self.alert.triggered_at.strftime("%H:%M:%S"))
        time_label.setStyleSheet(f"color: {THEME_COLORS['text_dim']}; font-size: 10px;")
        content_layout.addWidget(time_label)

        layout.addLayout(content_layout, 1)

        # Efeito de opacidade para fade
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)

    def mousePressEvent(self, event) -> None:
        """Fecha a notificação ao clicar."""
        self._close()
        event.accept()

    def _start_fade_out(self) -> None:
        """Inicia animação de fade out."""
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_animation.finished.connect(self._close)
        self.fade_animation.start()

    def _close(self) -> None:
        """Fecha a notificação."""
        self.closed.emit(self)
        self.deleteLater()

    def slide_in(self) -> None:
        """Animação de entrada (slide da direita)."""
        start_pos = QPoint(self.x() + 350, self.y())
        end_pos = QPoint(self.x(), self.y())

        self.move(start_pos)
        self.show()

        self.slide_animation = QPropertyAnimation(self, b"pos")
        self.slide_animation.setDuration(200)
        self.slide_animation.setStartValue(start_pos)
        self.slide_animation.setEndValue(end_pos)
        self.slide_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.slide_animation.start()


class AlertNotificationManager(QObject):
    """
    Gerencia múltiplas notificações empilhadas.
    """

    def __init__(self, parent_widget: QWidget) -> None:
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.notifications: list[AlertNotification] = []
        self.margin = 10
        self.spacing = 10
        self.max_notifications = 5

    def show_alert(self, alert: ActiveAlert, auto_close: bool = True, duration: int = 5000) -> None:
        """
        Mostra uma notificação de alerta.

        Args:
            alert: Alerta a mostrar
            auto_close: Se deve fechar automaticamente
            duration: Duração em ms antes de fechar
        """
        # Limita número de notificações
        while len(self.notifications) >= self.max_notifications:
            oldest = self.notifications[0]
            oldest._close()

        notification = AlertNotification(
            alert=alert,
            parent=self.parent_widget,
            auto_close=auto_close,
            duration=duration
        )
        notification.closed.connect(self._on_notification_closed)

        self.notifications.append(notification)
        self._reposition_all()
        notification.slide_in()

    def _on_notification_closed(self, notification: AlertNotification) -> None:
        """Handler quando uma notificação fecha."""
        if notification in self.notifications:
            self.notifications.remove(notification)
        self._reposition_all()

    def _reposition_all(self) -> None:
        """Reposiciona todas as notificações."""
        parent_rect = self.parent_widget.rect()
        y_offset = self.margin

        for notification in self.notifications:
            x = parent_rect.width() - notification.width() - self.margin
            y = y_offset

            if notification.isVisible():
                # Anima para nova posição
                anim = QPropertyAnimation(notification, b"pos")
                anim.setDuration(150)
                anim.setEndValue(QPoint(x, y))
                anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                anim.start()
                # Guarda referência para não ser coletado
                notification._reposition_anim = anim
            else:
                notification.move(x, y)

            y_offset += notification.height() + self.spacing

    def clear_all(self) -> None:
        """Fecha todas as notificações."""
        for notification in list(self.notifications):
            notification._close()
        self.notifications.clear()


class AlertEngine(QObject):
    """
    Motor de alertas que monitora valores e dispara alarmes.

    Signals:
        alert_triggered: Emitido quando um novo alerta é disparado
        alert_cleared: Emitido quando um alerta é resolvido
        alerts_changed: Emitido quando a lista de alertas muda
    """

    alert_triggered = pyqtSignal(object)  # ActiveAlert
    alert_cleared = pyqtSignal(str)  # field_name
    alerts_changed = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self.configs: dict[str, AlertConfig] = {}
        self.active_alerts: dict[str, ActiveAlert] = {}
        self._last_values: dict[str, float] = {}

        # Histórico de alertas
        self.history: list[AlertHistoryEntry] = []
        self.max_history = 100  # Máximo de entradas no histórico

        # Som de alerta
        self._sound_enabled = True
        self._last_sound_time: datetime | None = None
        self._sound_cooldown = 2.0  # segundos entre sons

    def add_config(self, config: AlertConfig) -> None:
        """Adiciona ou atualiza configuração de alerta."""
        self.configs[config.field_name] = config
        self.alerts_changed.emit()

    def remove_config(self, field_name: str) -> None:
        """Remove configuração de alerta."""
        if field_name in self.configs:
            del self.configs[field_name]
        if field_name in self.active_alerts:
            del self.active_alerts[field_name]
        self.alerts_changed.emit()

    def get_config(self, field_name: str) -> AlertConfig | None:
        """Retorna configuração de um campo."""
        return self.configs.get(field_name)

    def get_all_configs(self) -> list[AlertConfig]:
        """Retorna todas as configurações."""
        return list(self.configs.values())

    def get_active_count(self) -> int:
        """Retorna número de alertas ativos."""
        return len(self.active_alerts)

    def check_value(self, field_name: str, value: Any) -> ActiveAlert | None:
        """
        Verifica um valor contra as configurações de alerta.

        Args:
            field_name: Nome do campo
            value: Valor atual

        Returns:
            ActiveAlert se disparou, None caso contrário
        """
        config = self.configs.get(field_name)
        if not config or not config.enabled:
            # Se não há config ou está desabilitado, limpa alerta ativo
            if field_name in self.active_alerts:
                del self.active_alerts[field_name]
                self.alert_cleared.emit(field_name)
                self.alerts_changed.emit()
            return None

        try:
            val = float(value)
        except (ValueError, TypeError):
            return None

        self._last_values[field_name] = val

        # Verifica violações
        violation = None
        if config.min_value is not None and val < config.min_value:
            violation = 'min'
        elif config.max_value is not None and val > config.max_value:
            violation = 'max'

        if violation:
            # Cria ou atualiza alerta ativo

            alert = ActiveAlert(
                config=config,
                triggered_at=datetime.now(),  # Sempre usa timestamp atual
                current_value=val,
                violation_type=violation,
                acknowledged=False
            )
            self.active_alerts[field_name] = alert

            # Registra TODA violação no histórico
            threshold = config.min_value if violation == 'min' else config.max_value
            self._add_to_history(AlertHistoryEntry(
                field_name=field_name,
                description=config.description or field_name,
                triggered_at=alert.triggered_at,
                cleared_at=None,
                value=val,
                threshold=threshold,
                violation_type=violation,
                severity=config.severity
            ))

            # Emite notificação A CADA pacote em violação
            self.alert_triggered.emit(alert)
            self._play_sound(config)

            self.alerts_changed.emit()
            return alert
        else:
            # Valor voltou ao normal
            if field_name in self.active_alerts:
                # Atualiza histórico com horário de resolução
                self._update_history_cleared(field_name)
                del self.active_alerts[field_name]
                self.alert_cleared.emit(field_name)
                self.alerts_changed.emit()

        return None

    def check_all_values(self, data: dict[str, Any]) -> list[ActiveAlert]:
        """
        Verifica múltiplos valores de uma vez.

        Args:
            data: Dicionário com valores {field_name: value}

        Returns:
            Lista de alertas disparados (apenas novos)
        """
        triggered = []
        checked_fields = set()  # Evita verificar o mesmo campo duas vezes

        for field_name, value in data.items():
            # Remove sufixo _last se presente
            clean_name = field_name.replace('_last', '')

            # Pula se já verificamos este campo neste ciclo
            if clean_name in checked_fields:
                continue

            if clean_name in self.configs:
                checked_fields.add(clean_name)
                alert = self.check_value(clean_name, value)
                if alert:
                    triggered.append(alert)
        return triggered

    def acknowledge_alert(self, field_name: str) -> None:
        """Marca um alerta como reconhecido."""
        if field_name in self.active_alerts:
            self.active_alerts[field_name].acknowledged = True
            self.alerts_changed.emit()

    def acknowledge_all(self) -> None:
        """Reconhece todos os alertas ativos."""
        for alert in self.active_alerts.values():
            alert.acknowledged = True
        self.alerts_changed.emit()

    def get_active_alerts(self) -> list[ActiveAlert]:
        """Retorna lista de alertas ativos."""
        return list(self.active_alerts.values())

    def clear_all(self) -> None:
        """Limpa todos os alertas ativos."""
        # Marca todos como resolvidos no histórico
        for field_name in self.active_alerts:
            self._update_history_cleared(field_name)
        self.active_alerts.clear()
        self.alerts_changed.emit()

    def _add_to_history(self, entry: AlertHistoryEntry) -> None:
        """Adiciona entrada ao histórico."""
        self.history.insert(0, entry)  # Mais recente primeiro
        # Limita tamanho do histórico
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

    def _update_history_cleared(self, field_name: str) -> None:
        """Atualiza entrada do histórico com horário de resolução."""
        for entry in self.history:
            if entry.field_name == field_name and entry.cleared_at is None:
                entry.cleared_at = datetime.now()
                break

    def get_history(self) -> list[AlertHistoryEntry]:
        """Retorna histórico de alertas."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Limpa o histórico de alertas."""
        self.history.clear()

    def _play_sound(self, config: AlertConfig) -> None:
        """Toca som de alerta se habilitado."""
        if not self._sound_enabled or not config.sound_enabled:
            return

        # Cooldown para não tocar som muito frequentemente
        now = datetime.now()
        if self._last_sound_time:
            elapsed = (now - self._last_sound_time).total_seconds()
            if elapsed < self._sound_cooldown:
                return

        self._last_sound_time = now

        # Tenta diferentes métodos para tocar som
        try:
            # Método 1: paplay (PulseAudio) - comum no Linux
            subprocess.Popen(
                ['paplay', '/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            try:
                # Método 2: aplay (ALSA)
                subprocess.Popen(
                    ['aplay', '-q', '/usr/share/sounds/alsa/Front_Center.wav'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except FileNotFoundError:
                try:
                    # Método 3: beep do terminal
                    sys.stdout.write('\a')
                    sys.stdout.flush()
                except Exception:
                    pass  # Erro de som/arquivo ignorado

    def save_configs(self, filepath: str) -> None:
        """Salva configurações em arquivo JSON."""
        data = [c.to_dict() for c in self.configs.values()]
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load_configs(self, filepath: str) -> None:
        """Carrega configurações de arquivo JSON."""
        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
            self.configs.clear()
            for item in data:
                config = AlertConfig.from_dict(item)
                self.configs[config.field_name] = config
            self.alerts_changed.emit()
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Erro de som/arquivo ignorado
