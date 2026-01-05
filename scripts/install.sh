#!/bin/bash
# ============================================
# NPA Ground Station - Script de Instalação
# ============================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       NPA Ground Station - Instalação                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo $ID
    elif [ -f /etc/arch-release ]; then
        echo "arch"
    else
        echo "unknown"
    fi
}

install_system_deps() {
    local distro=$(detect_distro)
    echo -e "${YELLOW}[INFO]${NC} Distribuição: $distro"
    
    case $distro in
        arch|manjaro|endeavouros)
            sudo pacman -Syu --noconfirm
            sudo pacman -S --needed --noconfirm python python-pip qt6-base
            ;;
        ubuntu|debian|linuxmint|pop)
            sudo apt update
            sudo apt install -y python3 python3-pip python3-venv
            ;;
        fedora)
            sudo dnf install -y python3 python3-pip
            ;;
        *)
            echo -e "${YELLOW}[AVISO]${NC} Instale manualmente: python3, pip"
            ;;
    esac
}

create_venv() {
    echo -e "${YELLOW}[INFO]${NC} Criando ambiente virtual..."
    cd "$(dirname "$0")/.."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
    fi
    
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -e .
    
    echo -e "${GREEN}[OK]${NC} Ambiente configurado!"
}

echo "Opções:"
echo "  1) Instalação completa"
echo "  2) Apenas dependências do sistema"
echo "  3) Apenas ambiente Python"
read -p "Escolha [1]: " opt
opt=${opt:-1}

case $opt in
    1) install_system_deps; create_venv ;;
    2) install_system_deps ;;
    3) create_venv ;;
esac

echo -e "${GREEN}Instalação concluída!${NC}"
echo "Execute: source .venv/bin/activate && npags-gui"
