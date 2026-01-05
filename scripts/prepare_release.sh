#!/bin/bash
# Script para preparar o pacote de release do NPA Ground Station
# Uso: ./scripts/prepare_release.sh [versão]

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Diretório raiz do projeto
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Obtém versão do pyproject.toml se não fornecida
if [ -z "$1" ]; then
    VERSION=$(grep -oP '^version = "\K[^"]+' pyproject.toml | head -1)
else
    VERSION="$1"
fi

echo -e "${GREEN}=== Preparando Release v${VERSION} ===${NC}"

# Diretórios
DIST_DIR="$PROJECT_ROOT/dist/NPA-GroundStation"
RELEASE_DIR="$PROJECT_ROOT/releases"
RELEASE_NAME="NPA-GroundStation-v${VERSION}-linux-x64"
RELEASE_PATH="$RELEASE_DIR/$RELEASE_NAME"

# Verifica se o binário existe
if [ ! -f "$DIST_DIR/NPA-GroundStation" ]; then
    echo -e "${RED}ERRO: Binário não encontrado em $DIST_DIR${NC}"
    echo -e "${YELLOW}Execute primeiro: python build_app.py${NC}"
    exit 1
fi

# Cria diretório de releases
mkdir -p "$RELEASE_DIR"

# Remove release anterior se existir
rm -rf "$RELEASE_PATH"
rm -f "$RELEASE_PATH.tar.gz"

echo -e "${YELLOW}Copiando arquivos...${NC}"

# Copia a estrutura do dist
cp -r "$DIST_DIR" "$RELEASE_PATH"

# Garante que o manual está atualizado
cp "$PROJECT_ROOT/docs/MANUAL_USUARIO.md" "$RELEASE_PATH/"

# Copia imagens do manual se existirem
if [ -d "$PROJECT_ROOT/docs/images" ]; then
    mkdir -p "$RELEASE_PATH/docs/images"
    cp -r "$PROJECT_ROOT/docs/images/"* "$RELEASE_PATH/docs/images/" 2>/dev/null || true
fi

echo -e "${YELLOW}Criando arquivo tar.gz...${NC}"

# Cria o tarball
cd "$RELEASE_DIR"
tar -czvf "${RELEASE_NAME}.tar.gz" "$RELEASE_NAME"

# Remove diretório temporário
rm -rf "$RELEASE_PATH"

echo ""
echo -e "${GREEN}✓ Release criado com sucesso!${NC}"
echo -e "  Arquivo: ${YELLOW}$RELEASE_DIR/${RELEASE_NAME}.tar.gz${NC}"
echo ""
echo -e "Tamanho: $(du -h "${RELEASE_NAME}.tar.gz" | cut -f1)"
echo ""
echo -e "${GREEN}Próximos passos:${NC}"
echo "  1. Faça upload do arquivo para o GitHub Releases"
echo "  2. Ou use: gh release create v${VERSION} ${RELEASE_NAME}.tar.gz"