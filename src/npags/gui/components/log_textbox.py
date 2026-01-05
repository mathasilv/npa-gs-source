# src/npags/gui/components/log_textbox.py
"""
Widget de log híbrido (HTML + Texto Puro).

Suporta inserção de HTML (para logos) e texto puro monospace
(para dados de telemetria com alinhamento correto).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import QTextBrowser, QWidget


class LogTextbox(QTextBrowser):
    """
    Log Híbrido: Suporta HTML (para o logo) e Texto Puro (para o log de dados).

    Usa fonte Monospace para garantir alinhamento correto das tabelas.

    Attributes:
        max_lines: Número máximo de linhas a manter (para performance).
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        max_lines: int = 1000,
    ) -> None:
        """
        Inicializa o widget de log.

        Args:
            parent: Widget pai.
            max_lines: Limite de linhas para evitar consumo excessivo de memória.
        """
        super().__init__(parent)
        self.max_lines = max_lines
        self.setObjectName("LogConsole")

        self.setOpenExternalLinks(True)
        self.setPlaceholderText("Aguardando telemetria...")

        # Força fonte de terminal (Monospace)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Monospace")
        font.setPointSize(10)
        self.setFont(font)

    def append_html(self, html: str) -> None:
        """
        Insere conteúdo HTML (como o Logo).

        Move o cursor para o fim antes de inserir.

        Args:
            html: String HTML a inserir.
        """
        self.moveCursor(QTextCursor.MoveOperation.End)
        self.insertHtml(html)
        self.insertPlainText("\n")
        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def append_log(self, text: str) -> None:
        """
        Insere texto de log como TEXTO PURO (PlainText).

        Corrige automaticamente o alinhamento para esquerda e
        remove formatação herdada.

        Args:
            text: Texto a inserir.
        """
        self.moveCursor(QTextCursor.MoveOperation.End)
        cursor = self.textCursor()

        # Força Alinhamento à Esquerda
        block_fmt = cursor.blockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cursor.setBlockFormat(block_fmt)

        # Reseta estilos de fonte
        char_fmt = cursor.charFormat()
        char_fmt.setFontWeight(QFont.Weight.Normal)
        char_fmt.setFontItalic(False)
        cursor.setCharFormat(char_fmt)

        # Insere o texto limpo
        self.insertPlainText(text + "\n")
        scrollbar = self.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

        # Limita número de linhas
        self._trim_lines()

    def append(self, text: str) -> None:
        """
        Sobrescreve o método padrão para usar a inserção segura de log.

        Mantém compatibilidade com código que chama .append()

        Args:
            text: Texto a inserir.
        """
        self.append_log(text)

    def _trim_lines(self) -> None:
        """Remove linhas antigas se exceder o limite."""
        doc = self.document()
        if doc is None:
            return

        if doc.blockCount() > self.max_lines:
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            # Remove as primeiras linhas excedentes
            lines_to_remove = doc.blockCount() - self.max_lines
            for _ in range(lines_to_remove):
                cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()  # Remove o newline

    def clear_log(self) -> None:
        """Limpa todo o conteúdo do log."""
        self.clear()

    def get_text(self) -> str:
        """Retorna todo o texto do log."""
        return self.toPlainText()
