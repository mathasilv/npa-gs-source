# src/npags/gui/views/editor_view.py

"""
Interface de edição de arquivos YAML.

Editor de schemas de decoder com:
    - Syntax highlighting para YAML
    - Validação de sintaxe
    - Template de decoder
"""

from collections.abc import Callable

from PyQt6.QtCore import QRegularExpression, Qt
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from npags.decoders.loader import DecoderLoader
from npags.gui.translations import tr
from npags.gui.styles import THEME_COLORS

# Template YAML para novos decoders
DEFAULT_TEMPLATE = '''# Decoder Configuration
name: novo_decoder
version: "1.0"
description: "Descrição do decoder"

# Configuração do header
header:
  sync_word: 0xAA
  length_field: true

# Campos de dados
fields:
  - name: temperature
    type: int16
    unit: "°C"
    scale: 0.1
    widget: gauge

  - name: humidity
    type: uint8
    unit: "%"
    widget: card

  - name: latitude
    type: float32
    widget: map

  - name: longitude
    type: float32
    widget: map
'''


class YAMLHighlighter(QSyntaxHighlighter):
    """
    Syntax highlighter para YAML.
    Cores ajustadas para combinar com o tema 'Flat Dark' (Laranja/Cinzento).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        # Chaves: Usam a cor de destaque (Accent)
        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor(THEME_COLORS['accent']))
        key_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"^\s*[\w\-\_]+(?=:)"), key_fmt))

        # Comentários: Usam cinzento discreto (Text Dim)
        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor(THEME_COLORS['text_dim']))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

        # Números: Usam uma variação mais clara do Accent para leitura fácil
        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor(THEME_COLORS['accent_hover']))
        self.rules.append((QRegularExpression(r"\b\d+\.?\d*\b"), number_fmt))

    def highlightBlock(self, text: str):
        for pattern, fmt in self.rules:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class EditorView(QWidget):
    """View de edição de arquivos de decoder YAML."""

    def __init__(self, parent=None, on_back: Callable[[], None] | None = None) -> None:
        super().__init__(parent)

        self.on_back = on_back
        self.current_decoder: str | None = None
        self.is_new = False
        self.loader = DecoderLoader()

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        layout.addLayout(self._create_header())

        # Editor
        self.text_editor = self._create_editor_area()
        layout.addWidget(self.text_editor)

        # Footer
        layout.addLayout(self._create_footer())

    def _create_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(16)

        btn_back = QPushButton(tr("Voltar"))
        btn_back.setMinimumHeight(32)
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        # Usa classe secundária para borda fina automática
        btn_back.setProperty("class", "secondary")
        if self.on_back:
            btn_back.clicked.connect(self.on_back)
        layout.addWidget(btn_back)

        self.title_label = QLabel("Editor de Decoder")
        font = QFont()
        font.setPointSize(16)
        # Removed setBold(True) to align with global non-bold style if desired,
        # but title usually keeps it. Let's keep title bold as it's a Header.
        font.setBold(True)
        self.title_label.setFont(font)
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.name_input_widget = QWidget()
        name_layout = QHBoxLayout(self.name_input_widget)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(8)

        lbl_name = QLabel("Nome do Arquivo:")
        lbl_name.setProperty("class", "InfoLabel")
        name_layout.addWidget(lbl_name)

        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("ex: sensor_v1")
        self.name_entry.setFixedWidth(200)
        name_layout.addWidget(self.name_entry)

        lbl_ext = QLabel(".yaml")
        lbl_ext.setProperty("class", "InfoLabel")
        name_layout.addWidget(lbl_ext)

        self.name_input_widget.setVisible(False)
        layout.addWidget(self.name_input_widget)

        return layout

    def _create_editor_area(self) -> QPlainTextEdit:
        editor = QPlainTextEdit()
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Fonte monoespaçada para código
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Monospace", 11)
        editor.setFont(font)
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        editor.setPlaceholderText("Digite ou cole o conteúdo YAML do decoder aqui...")

        # Estilos de borda e cores são herdados de QPlainTextEdit no styles.py

        self.highlighter = YAMLHighlighter(editor.document())
        return editor

    def _create_footer(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        # Botões de ação (neutros)
        btn_template = self._create_action_button("Carregar Template", self._load_template)
        btn_validate = self._create_action_button("Validar Sintaxe", self._validate_yaml)

        layout.addWidget(btn_template)
        layout.addWidget(btn_validate)

        self.btn_delete = QPushButton("Excluir Decoder")
        self.btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_delete.setFixedHeight(38)

        # Define o ID para aplicar o estilo de PERIGO (Vermelho) definido no styles.py
        # Removemos o setStyleSheet manual
        self.btn_delete.setObjectName("btn_delete")

        self.btn_delete.clicked.connect(self._delete_decoder)
        self.btn_delete.setVisible(False)
        layout.addWidget(self.btn_delete)

        layout.addStretch()

        # Botão Salvar (Principal) - AJUSTADO
        btn_save = QPushButton("Salvar Decoder")
        btn_save.setFixedHeight(38) # Igual aos outros botões (era 42)
        # Removido setMinimumWidth(160) para não ficar desproporcional
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)

        # Removida configuração manual de Fonte (Bold/11pt)
        # Agora ele herda a fonte padrão do styles.py (Normal/13px)

        # Estilo padrão de QPushButton no styles.py é a cor Accent (Laranja)
        btn_save.clicked.connect(self._save_decoder)
        layout.addWidget(btn_save)

        return layout

    def _create_action_button(self, text: str, callback: Callable) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Define como secundário para ter fundo transparente
        btn.setProperty("class", "secondary")
        btn.clicked.connect(callback)
        return btn

    def open_new_decoder(self):
        self.is_new = True
        self.current_decoder = None
        self.title_label.setText("Novo Decoder")
        self.name_input_widget.setVisible(True)
        self.btn_delete.setVisible(False)
        self.name_entry.clear()
        self.name_entry.setFocus()
        self.text_editor.clear()

    def open_edit_decoder(self, decoder_name: str) -> bool:
        success, content, error = self.loader.load_decoder(decoder_name)
        if not success:
            QMessageBox.critical(self, "Erro de Leitura", f"Não foi possível carregar:\n\n{error}")
            return False
        self.is_new = False
        self.current_decoder = decoder_name
        self.title_label.setText(f"Editando: {decoder_name}.yaml")
        self.name_input_widget.setVisible(False)
        self.btn_delete.setVisible(True)
        self.text_editor.setPlainText(content)
        return True

    def _load_template(self):
        """Carrega o template padrão."""
        if self.text_editor.toPlainText().strip():
            reply = QMessageBox.question(
                self, tr("Substituir"),
                "O conteúdo atual será perdido. Continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.text_editor.setPlainText(DEFAULT_TEMPLATE)

    def _validate_yaml(self):
        """Valida a sintaxe YAML."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Vazio", "O editor está vazio.")
            return

        try:
            import yaml
            yaml.safe_load(content)
            QMessageBox.information(self, "Validado", "Sintaxe YAML correta!")
        except yaml.YAMLError as e:
            QMessageBox.warning(self, "Erro de Sintaxe", f"Erro YAML:\n{e}")
        except ImportError:
            QMessageBox.warning(self, tr("Aviso"), "Módulo PyYAML não instalado.")

    def _delete_decoder(self):
        """Exclui o decoder atual (modo demonstração)."""
        if self.is_new or not self.current_decoder:
            return
        reply = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Excluir '{self.current_decoder}.yaml'?\nAção irreversível.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Demo", "Exclusão simulada (modo demonstração).")
            if self.on_back:
                self.on_back()

    def _save_decoder(self):
        """Salva o decoder (modo demonstração)."""
        content = self.text_editor.toPlainText()
        if not content.strip():
            QMessageBox.warning(self, "Vazio", "Arquivo vazio.")
            return

        if self.is_new:
            raw = self.name_entry.text().strip()
            if not raw:
                QMessageBox.warning(self, "Nome Obrigatório", "Defina um nome.")
                return
            target_name = "".join(c for c in raw if c.isalnum() or c in ('_', '-'))
        else:
            target_name = self.current_decoder

        # Valida YAML antes de salvar
        try:
            import yaml
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            if QMessageBox.question(
                self, "Erro Sintaxe",
                f"{e}\nSalvar mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) != QMessageBox.StandardButton.Yes:
                return
        except ImportError:
            pass  # PyYAML não instalado, validação ignorada

        QMessageBox.information(self, "Demo", f"Decoder '{target_name}' salvo (modo demonstração).")
        if self.on_back:
            self.on_back()
