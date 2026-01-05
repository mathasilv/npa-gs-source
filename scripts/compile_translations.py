#!/usr/bin/env python3
"""
Script para compilar arquivos de tradução .ts para .qm

Uso:
    python scripts/compile_translations.py
    
Requisitos:
    - PyQt6-tools (contém lrelease)
    
Instalação:
    pip install PyQt6-tools
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Compila todos os arquivos .ts para .qm"""
    
    # Diretório das traduções
    translations_dir = Path(__file__).parent.parent / "src" / "npags" / "gui" / "translations"
    
    if not translations_dir.exists():
        print(f"❌ Diretório não encontrado: {translations_dir}")
        sys.exit(1)
    
    # Encontra todos os arquivos .ts
    ts_files = list(translations_dir.glob("*.ts"))
    
    if not ts_files:
        print("❌ Nenhum arquivo .ts encontrado")
        sys.exit(1)
    
    print(f"📁 Diretório: {translations_dir}")
    print(f"📄 Arquivos encontrados: {len(ts_files)}")
    print()
    
    # Tenta encontrar lrelease
    lrelease_cmd = None
    for cmd in ["lrelease", "lrelease-qt6", "pyside6-lrelease"]:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True)
            lrelease_cmd = cmd
            break
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    if lrelease_cmd is None:
        print("❌ lrelease não encontrado!")
        print()
        print("Instale com:")
        print("  pip install PyQt6-tools")
        print("  # ou")
        print("  sudo pacman -S qt6-tools  # Arch Linux")
        print("  sudo apt install qt6-tools-dev  # Ubuntu/Debian")
        sys.exit(1)
    
    print(f"🔧 Usando: {lrelease_cmd}")
    print()
    
    # Compila cada arquivo
    success = 0
    failed = 0
    
    for ts_file in ts_files:
        qm_file = ts_file.with_suffix(".qm")
        
        try:
            result = subprocess.run(
                [lrelease_cmd, str(ts_file), "-qm", str(qm_file)],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✅ {ts_file.name} -> {qm_file.name}")
                success += 1
            else:
                print(f"❌ {ts_file.name}: {result.stderr}")
                failed += 1
                
        except Exception as e:
            print(f"❌ {ts_file.name}: {e}")
            failed += 1
    
    print()
    print(f"📊 Resultado: {success} sucesso, {failed} falha(s)")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()