# ============================================
# NPA Ground Station - Makefile
# ============================================
# Uso:
#   make install    - Instala dependências
#   make build      - Compila executável
#   make build-one  - Compila executável único
#   make clean      - Limpa builds
#   make run        - Executa a aplicação
#   make test       - Executa testes
# ============================================

.PHONY: all install-dev install-build build build-one clean run test lint help venv

# Variáveis
PYTHON := python3
APP_NAME := NPA-GroundStation
DIST_DIR := dist/$(APP_NAME)
VENV_DIR := .venv-build
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

# Detecta sistema operacional
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
    PLATFORM := linux
    EXE := $(DIST_DIR)/$(APP_NAME)
endif
ifeq ($(UNAME_S),Darwin)
    PLATFORM := macos
    EXE := $(DIST_DIR)/$(APP_NAME)
endif
ifeq ($(OS),Windows_NT)
    PLATFORM := windows
    EXE := $(DIST_DIR)/$(APP_NAME).exe
    PYTHON := python
    VENV_PYTHON := $(VENV_DIR)/Scripts/python.exe
    VENV_PIP := $(VENV_DIR)/Scripts/pip.exe
endif

# Alvo padrão
all: help

# Ajuda
help:
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║       NPA Ground Station - Sistema de Build                ║"
	@echo "╠════════════════════════════════════════════════════════════╣"
	@echo "║  Comandos disponíveis:                                     ║"
	@echo "║                                                            ║"
	@echo "║  make venv        - Cria virtual environment               ║"
	@echo "║  make install     - Instala dependências básicas           ║"
	@echo "║  make install-dev - Instala deps de desenvolvimento        ║"
	@echo "║  make install-build- Instala deps de build                 ║"
	@echo "║  make build       - Compila executável (pasta)             ║"
	@echo "║  make build-one   - Compila executável único               ║"
	@echo "║  make clean       - Remove arquivos de build               ║"
	@echo "║  make clean-venv  - Remove virtual environment             ║"
	@echo "║  make run         - Executa a aplicação                    ║"
	@echo "║  make test        - Executa testes                         ║"
	@echo "║  make lint        - Verifica código com ruff               ║"
	@echo "║  make package     - Cria pacote ZIP para distribuição      ║"
	@echo "║                                                            ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Plataforma detectada: $(PLATFORM)"
	@echo ""

# Cria virtual environment
venv:
	@if [ ! -f "$(VENV_PYTHON)" ]; then \
		echo "📦 Criando virtual environment..."; \
		$(PYTHON) -m venv $(VENV_DIR); \
		echo "✅ Virtual environment criado em $(VENV_DIR)"; \
	else \
		echo "✅ Virtual environment já existe: $(VENV_DIR)"; \
	fi

# Instalação básica (no venv)
install: venv
	@echo "📦 Instalando dependências básicas..."
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e .
	@echo "✅ Instalação concluída!"

# Instalação para desenvolvimento
install-dev: venv
	@echo "📦 Instalando dependências de desenvolvimento..."
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e ".[dev]"
	@echo "✅ Ambiente de desenvolvimento configurado!"

# Instalação para build
install-build: venv
	@echo "📦 Instalando dependências de build..."
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e ".[build,reports]"
	@echo "✅ Dependências de build instaladas!"

# Build padrão (pasta)
build: install-build clean-build
	@echo "🔨 Compilando $(APP_NAME) para $(PLATFORM)..."
	$(VENV_PYTHON) build_app.py --no-venv
	@echo ""
	@echo "✅ Build concluído!"
	@echo "📁 Executável em: $(DIST_DIR)/"

# Build executável único
build-one: install-build clean-build
	@echo "🔨 Compilando $(APP_NAME) (arquivo único)..."
	$(VENV_PYTHON) build_app.py --onefile --no-venv
	@echo ""
	@echo "✅ Build concluído!"
	@echo "📁 Executável em: dist/"

# Limpeza de build (mantém venv)
clean-build:
	@echo "🧹 Limpando builds anteriores..."
	rm -rf build/ dist/ *.spec
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "✅ Limpeza concluída!"

# Limpeza completa
clean: clean-build
	@echo "🧹 Limpeza completa..."

# Remove virtual environment
clean-venv:
	@echo "🧹 Removendo virtual environment..."
	rm -rf $(VENV_DIR)
	@echo "✅ Virtual environment removido!"

# Executa a aplicação (usando venv se existir)
run:
	@echo "🚀 Iniciando NPA Ground Station..."
	@if [ -f "$(VENV_PYTHON)" ]; then \
		$(VENV_PYTHON) -m npags.gui.main_window; \
	else \
		$(PYTHON) -m npags.gui.main_window; \
	fi

# Executa testes
test: install-dev
	@echo "🧪 Executando testes..."
	$(VENV_PYTHON) -m pytest tests/ -v

# Lint do código
lint: install-dev
	@echo "🔍 Verificando código..."
	$(VENV_PYTHON) -m ruff check src/
	@echo "✅ Verificação concluída!"

# Formata código
format: install-dev
	@echo "✨ Formatando código..."
	$(VENV_PYTHON) -m black src/
	$(VENV_PYTHON) -m ruff check --fix src/
	@echo "✅ Formatação concluída!"

# Cria pacote para distribuição
package: build
	@echo "📦 Criando pacote de distribuição..."
	@mkdir -p releases
	@cd dist && zip -r ../releases/$(APP_NAME)-$(PLATFORM)-$(shell date +%Y%m%d).zip $(APP_NAME)/
	@echo "✅ Pacote criado em: releases/"

# Verifica dependências do sistema (Linux)
check-deps:
	@echo "🔍 Verificando dependências do sistema..."
ifeq ($(PLATFORM),linux)
	@which python3 > /dev/null || echo "❌ Python3 não encontrado"
	@if [ -f "$(VENV_PYTHON)" ]; then \
		$(VENV_PYTHON) -c "import PyQt6" 2>/dev/null && echo "✅ PyQt6" || echo "❌ PyQt6 não instalado"; \
		$(VENV_PYTHON) -c "import numpy" 2>/dev/null && echo "✅ NumPy" || echo "❌ NumPy não instalado"; \
		$(VENV_PYTHON) -c "import yaml" 2>/dev/null && echo "✅ PyYAML" || echo "❌ PyYAML não instalado"; \
	else \
		echo "⚠️  Virtual environment não encontrado. Execute 'make install' primeiro."; \
	fi
endif
	@echo ""
