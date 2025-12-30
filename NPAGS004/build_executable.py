
#!/usr/bin/env python3
"""
Build script universal para NPAGS
Funciona em Linux e Windows
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path


def get_separator():
    """Retorna separador correto para --add-data"""
    return ';' if platform.system() == 'Windows' else ':'


def clean_build():
    """Limpa builds anteriores"""
    print("Limpando builds anteriores...")
    for folder in ['build', 'dist', '__pycache__']:
        if Path(folder).exists():
            shutil.rmtree(folder)
    
    for spec in Path('.').glob('*.spec'):
        spec.unlink()


def install_dependencies():
    """Instala PyInstaller se necessário"""
    print("Verificando PyInstaller...")
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} encontrado")
    except ImportError:
        print("Instalando PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def build_executable():
    """Build do executável"""
    print(f"\nBuilding para {platform.system()}...")
    
    sep = get_separator()
    system = platform.system()
    
    # Definição dos caminhos de recursos
    # Ajustado para refletir a estrutura src/npags/config
    config_src = Path("src/npags/config")
    data_src = Path("data")
    
    # Comando base
    cmd = [
        "pyinstaller",
        "--name=NPAGS",
        "--clean",
        "--noconfirm",
        "--windowed",
        "--paths=src",  # Importante: adiciona src ao path para encontrar o pacote 'npags'
    ]
    
    # Adiciona dados (Resources internos do executável)
    # Sintaxe: source_path{sep}dest_path_inside_exe
    if config_src.exists():
        cmd.append(f"--add-data={config_src}{sep}config")
    else:
        print(f"AVISO: Pasta de config não encontrada em {config_src}")

    if data_src.exists():
        cmd.append(f"--add-data={data_src}{sep}data")
    
    # Hidden imports
    hidden_imports = [
        "numpy",
        "matplotlib",
        "matplotlib.backends.backend_tkagg",
        "customtkinter",
        "yaml",
        "PIL",
        "PIL._tkinter_finder",
        "npags.core",
        "npags.gui",
        # Adicionados explicitamente os novos módulos para garantir detecção
        "npags.gui.styles",
        "npags.gui.utils",
        "npags.gui.canvas_items",
        "npags.gui.history_dialog",
        "npags.radio",
        "npags.decoders",
    ]
    
    for imp in hidden_imports:
        cmd.append(f"--hidden-import={imp}")
    
    # Ícone (se existir)
    icon_path = Path("assets/icon.ico")
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")
    
    # Arquivo principal
    cmd.append("src/npags/gui/main_window.py")
    
    # Executa build
    print(f"\nComando: {' '.join(str(c) for c in cmd)}\n")
    subprocess.run(cmd, check=True)
    
    # Retorna caminho do diretório dist
    dist_dir = Path("dist/NPAGS")
    return dist_dir


def create_portable_package(dist_dir):
    """Cria pacote portável com README"""
    print("\nCriando pacote portável...")
    
    system = platform.system()
    pkg_name = f"NPAGS-{system}-portable"
    pkg_dir = Path(pkg_name)
    
    # Remove pacote anterior se existir
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    
    # Cria estrutura
    pkg_dir.mkdir(exist_ok=True)
    
    # Copia todo o conteúdo do dist
    if dist_dir.exists():
        # Copia todos os arquivos do dist/NPAGS para o pacote
        for item in dist_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, pkg_dir / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, pkg_dir / item.name)
    
    # Torna executável no Linux
    exe_path = pkg_dir / "NPAGS"
    if system == "Linux" and exe_path.exists():
        os.chmod(exe_path, 0o755)
    
    # Copia recursos adicionais (Para ficarem editáveis fora do EXE)
    # Dicionário mapeando Origem -> Nome Destino
    external_resources = {
        Path("src/npags/config"): "config",
        Path("data"): "data"
    }

    for src_path, dest_name in external_resources.items():
        if src_path.exists():
            dst = pkg_dir / dest_name
            if dst.exists():
                shutil.rmtree(dst)
            print(f"Copiando recurso externo: {src_path} -> {dst}")
            shutil.copytree(src_path, dst)
        else:
            print(f"Aviso: Recurso não encontrado para pacote: {src_path}")
    
    # Cria README
    readme_content = f"""
NPAGS Ground Station v1.0.0
============================

## Executar

{"Duplo clique em NPAGS.exe" if system == "Windows" else "./NPAGS"}

## Requisitos de Sistema ({system})

"""
    
    if system == "Windows":
        readme_content += """
### Windows:
- Windows 10 ou superior
- Para usar modo Radio SDR:
  - Zadig (drivers USB): https://zadig.akeo.ie/
  - GNU Radio (opcional): https://wiki.gnuradio.org/index.php/WindowsInstall
  
### Modo UDP (não precisa SDR):
Funciona sem instalação adicional.

"""
    else:
        readme_content += """
### Linux:
- Para usar modo Radio SDR, instale:
  
  # Arch/Manjaro
  sudo pacman -S gnuradio gr-osmosdr rtl-sdr
  
  # Ubuntu/Debian
  sudo apt install gnuradio gr-osmosdr rtl-sdr
  
  # Fedora
  sudo dnf install gnuradio gr-osmosdr rtl-sdr

### Modo UDP (não precisa SDR):
Funciona sem instalação adicional.

### Executar:

cd NPAGS-Linux-portable
./NPAGS

"""
    
    readme_content += """
## Estrutura

NPAGS/
├── NPAGS          # Executável principal
├── _internal/     # Bibliotecas empacotadas
├── config/        # Decoders YAML (Editável)
│   └── decoder_schemas/
└── data/          # Logs de telemetria
    └── logs/

## Uso

1. Execute o programa
2. Escolha o modo (Radio SDR ou Rede UDP)
3. Selecione o decoder
4. Clique em CONECTAR SISTEMA

## Suporte

GitHub: https://github.com/seu-usuario/npags
Documentação: docs/
"""
    
    (pkg_dir / "README.txt").write_text(readme_content, encoding='utf-8')
    
    # Cria script de execução para Linux
    if system == "Linux":
        launch_script = pkg_dir / "run.sh"
        launch_script.write_text("""#!/bin/bash
cd "$(dirname "$0")"
./NPAGS
""", encoding='utf-8')
        os.chmod(launch_script, 0o755)
    
    # Compacta
    print(f"\nCompactando pacote...")
    if system == "Windows":
        # ZIP para Windows
        archive_name = shutil.make_archive(pkg_name, 'zip', '.', pkg_name)
        print(f"\nPacote criado: {archive_name}")
    else:
        # tar.gz para Linux
        archive_name = shutil.make_archive(pkg_name, 'gztar', '.', pkg_name)
        print(f"\nPacote criado: {archive_name}")
    
    return pkg_name, archive_name


def main():
    print("="*60)
    print("NPAGS Build Script")
    print(f"Sistema: {platform.system()} {platform.machine()}")
    print("="*60)
    
    try:
        # 1. Limpa builds anteriores
        clean_build()
        
        # 2. Instala dependências
        install_dependencies()
        
        # 3. Build
        dist_dir = build_executable()
        
        # 4. Verifica resultado
        exe_path = dist_dir / ("NPAGS.exe" if platform.system() == "Windows" else "NPAGS")
        
        if not exe_path.exists():
            print(f"\nERRO: Executável não foi criado em {exe_path}")
            return 1
        
        print(f"\n✓ Executável criado: {exe_path}")
        exe_size = exe_path.stat().st_size / 1024 / 1024
        print(f"  Tamanho: {exe_size:.1f} MB")
        
        # 5. Cria pacote portável
        pkg_name, archive_name = create_portable_package(dist_dir)
        
        archive_size = Path(archive_name).stat().st_size / 1024 / 1024
        
        print("\n" + "="*60)
        print("BUILD CONCLUÍDO COM SUCESSO!")
        print("="*60)
        print(f"\nDiretório build: {dist_dir}")
        print(f"Pacote portável: {pkg_name}/")
        print(f"Arquivo compactado: {archive_name} ({archive_size:.1f} MB)")
        print("\nDistribua o arquivo compactado para os usuários.")
        print(f"\nTestar localmente:")
        if platform.system() == "Windows":
            print(f"  cd {pkg_name}")
            print(f"  NPAGS.exe")
        else:
            print(f"  cd {pkg_name}")
            print(f"  ./NPAGS")
        
        return 0
    
    except Exception as e:
        print(f"\nERRO: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
