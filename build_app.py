#!/usr/bin/env python3
"""
Script de Build para NPA Ground Station.
Gera executáveis standalone para Linux e Windows usando PyInstaller.

Uso:
    python build_app.py          # Build padrão (one-folder)
    python build_app.py --onefile # Executável único
    python build_app.py --clean   # Limpa builds anteriores
"""

import os
import sys
import shutil
import platform
import subprocess
from pathlib import Path


# === CONFIGURAÇÃO ===
APP_NAME = "NPA-GroundStation"
APP_VERSION = "5.6.0"
MAIN_SCRIPT = "src/npags/gui/main_window.py"
ICON_LINUX = "src/npags/gui/assets/logo.png"
ICON_WINDOWS = "src/npags/gui/assets/logo.ico"
VENV_DIR = ".venv-build"


def get_platform() -> str:
    """Retorna 'linux' ou 'windows'."""
    system = platform.system().lower()
    if system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    else:
        print(f"⚠️  Sistema '{system}' não testado, tentando como Linux...")
        return "linux"


def get_venv_python() -> Path:
    """Retorna o caminho do Python no venv."""
    plat = get_platform()
    venv_path = Path(VENV_DIR)
    if plat == "windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def get_venv_pip() -> Path:
    """Retorna o caminho do pip no venv."""
    plat = get_platform()
    venv_path = Path(VENV_DIR)
    if plat == "windows":
        return venv_path / "Scripts" / "pip.exe"
    return venv_path / "bin" / "pip"


def setup_venv() -> bool:
    """Cria e configura o virtual environment para build."""
    venv_path = Path(VENV_DIR)
    venv_python = get_venv_python()
    
    if venv_python.exists():
        print(f"✅ Virtual environment já existe: {venv_path}")
        return True
    
    print(f"📦 Criando virtual environment em {venv_path}...")
    
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            check=True
        )
        print("✅ Virtual environment criado!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Falha ao criar venv: {e}")
        return False


def clean_build_dirs():
    """Remove diretórios de build anteriores."""
    dirs_to_clean = ["build", "dist", "__pycache__"]
    files_to_clean = [f"{APP_NAME}.spec", "*.spec"]
    
    print("🧹 Limpando builds anteriores...")
    
    for d in dirs_to_clean:
        path = Path(d)
        if path.exists():
            shutil.rmtree(path)
            print(f"   Removido: {d}/")
    
    for pattern in files_to_clean:
        for f in Path(".").glob(pattern):
            f.unlink()
            print(f"   Removido: {f}")
    
    # Limpa __pycache__ recursivamente
    for pycache in Path(".").rglob("__pycache__"):
        shutil.rmtree(pycache)
    
    print("✅ Limpeza concluída!\n")


def check_dependencies(use_venv: bool = True):
    """Verifica e instala dependências de build."""
    print("📦 Verificando dependências de build...")
    
    if use_venv:
        venv_pip = str(get_venv_pip())
        venv_python = str(get_venv_python())
        pip_cmd = [venv_pip]
        python_cmd = [venv_python]
    else:
        pip_cmd = [sys.executable, "-m", "pip"]
        python_cmd = [sys.executable]
    
    # Atualiza pip
    print("   Atualizando pip...")
    subprocess.run(
        [*pip_cmd, "install", "--upgrade", "pip"],
        check=True,
        capture_output=True
    )
    
    # Instala o projeto com dependências de build
    print("   Instalando projeto e dependências...")
    result = subprocess.run(
        [*pip_cmd, "install", "-e", ".[build,reports]"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"   Saída: {result.stdout}")
        print(f"   Erro: {result.stderr}")
        # Tenta instalar sem extras
        print("   Tentando instalação básica...")
        subprocess.run(
            [*pip_cmd, "install", "-e", "."],
            check=True
        )
        subprocess.run(
            [*pip_cmd, "install", "pyinstaller", "pillow"],
            check=True
        )
    
    # Verifica PyInstaller
    result = subprocess.run(
        [*python_cmd, "-c", "import PyInstaller; print(PyInstaller.__version__)"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"   PyInstaller {result.stdout.strip()} ✓")
    else:
        print("❌ Falha ao verificar PyInstaller")
        sys.exit(1)
    
    # Verifica Pillow
    result = subprocess.run(
        [*python_cmd, "-c", "from PIL import Image; print('OK')"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print("   Pillow ✓")
    else:
        print("⚠️  Pillow não disponível (ícone .ico não será gerado)")
    
    print()


def create_windows_icon(use_venv: bool = True):
    """Converte PNG para ICO se necessário (Windows)."""
    png_path = Path(ICON_LINUX)
    ico_path = Path(ICON_WINDOWS)
    
    if ico_path.exists():
        return ico_path
    
    if not png_path.exists():
        print("⚠️  Ícone PNG não encontrado, build sem ícone.")
        return None
    
    if use_venv:
        python_cmd = str(get_venv_python())
    else:
        python_cmd = sys.executable
    
    try:
        print("🎨 Convertendo ícone PNG → ICO...")
        script = f'''
from PIL import Image
img = Image.open("{png_path}")
img.save("{ico_path}", format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
print("OK")
'''
        result = subprocess.run(
            [python_cmd, "-c", script],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(f"   Criado: {ico_path}")
            return ico_path
        else:
            print(f"⚠️  Falha ao converter ícone: {result.stderr}")
            return None
    except Exception as e:
        print(f"⚠️  Falha ao converter ícone: {e}")
        return None


def get_data_files() -> list[tuple[str, str]]:
    """Retorna lista de arquivos de dados para incluir."""
    data_files = []
    
    # Schemas de decoder (YAML)
    schemas_dir = Path("src/npags/config/decoder_schemas")
    if schemas_dir.exists():
        data_files.append((str(schemas_dir), "npags/config/decoder_schemas"))
    
    # Assets da GUI (imagens, icones)
    assets_dir = Path("src/npags/gui/assets")
    if assets_dir.exists():
        data_files.append((str(assets_dir), "npags/gui/assets"))
    
    # Traducoes (i18n)
    translations_dir = Path("src/npags/gui/translations")
    if translations_dir.exists():
        data_files.append((str(translations_dir), "npags/gui/translations"))
    
    # Diretorio de dados (logs)
    data_dir = Path("data/logs")
    if data_dir.exists():
        data_files.append((str(data_dir), "data/logs"))
    
    return data_files


def get_hidden_imports() -> list[str]:
    """Retorna lista de imports ocultos necessários."""
    return [
        # Core
        "npags",
        "npags.core",
        "npags.core.decoder_engine",
        "npags.core.multi_decoder",
        "npags.core.field_types",
        "npags.core.schema_validator",
        "npags.core.logger",
        "npags.core.telemetry_formatter",
        "npags.core.exceptions",
        
        # GUI
        "npags.gui",
        "npags.gui.main_window",
        "npags.gui.styles",
        "npags.gui.utils",
        "npags.gui.canvas_items",
        "npags.gui.views",
        "npags.gui.views.station_view",
        "npags.gui.views.dashboard_view",
        "npags.gui.views.editor_view",
        "npags.gui.widgets",
        "npags.gui.widgets.plot_widget",
        "npags.gui.widgets.map_widget",
        "npags.gui.widgets.kpi_widgets",
        "npags.gui.widgets.alerts_widget",
        "npags.gui.dialogs",
        "npags.gui.dialogs.export_dialog",
        "npags.gui.dialogs.history_dialog",
        "npags.gui.dialogs.alerts_config_dialog",
        "npags.gui.dialogs.report_dialog",
        "npags.gui.components",
        "npags.gui.components.log_textbox",
        "npags.gui.components.sidebar_params",
        
        # Decoders
        "npags.decoders",
        "npags.decoders.loader",
        
        # Radio
        "npags.radio",
        "npags.radio.udp_receiver",
        "npags.radio.backend",
        
        # Reports
        "npags.reports",
        "npags.reports.generator",
        
        # Dependências externas
        "yaml",
        "numpy",
        "cerberus",
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pyqtgraph",
        
        # Opcionais (reports)
        "reportlab",
        "reportlab.lib",
        "reportlab.lib.colors",
        "reportlab.lib.pagesizes",
        "reportlab.lib.styles",
        "reportlab.lib.units",
        "reportlab.platypus",
        "matplotlib",
        "matplotlib.pyplot",
        "matplotlib.dates",
        
        # PyQt6 plugins e backends
        "PyQt6.sip",
        "PyQt6.QtPrintSupport",
        "PyQt6.QtSvg",
        "PyQt6.QtOpenGL",
    ]


def build_pyinstaller(onefile: bool = False, use_venv: bool = True):
    """Executa o PyInstaller com as configurações corretas."""
    plat = get_platform()
    separator = ";" if plat == "windows" else ":"
    
    print(f"🔨 Iniciando build para {plat.upper()}...")
    print(f"   Modo: {'Arquivo único' if onefile else 'Pasta'}")
    print()
    
    # Usa Python do venv ou do sistema
    if use_venv:
        python_exe = str(get_venv_python())
    else:
        python_exe = sys.executable
    
    # Comando base
    cmd = [
        python_exe, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
    ]
    
    # Modo onefile ou onedir
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")
    
    # Ícone
    if plat == "windows":
        icon = create_windows_icon(use_venv)
        if icon:
            cmd.extend(["--icon", str(icon)])
    else:
        icon_path = Path(ICON_LINUX)
        if icon_path.exists():
            cmd.extend(["--icon", str(icon_path)])
    
    # Adiciona path do src
    cmd.extend(["--paths", "src"])
    
    # Arquivos de dados
    for src, dest in get_data_files():
        cmd.extend(["--add-data", f"{src}{separator}{dest}"])
    
    # Hidden imports
    for imp in get_hidden_imports():
        cmd.extend(["--hidden-import", imp])
    
    # Exclusões (reduz tamanho)
    excludes = [
        "tkinter",
        "unittest",
        "test",
        "tests",
        "setuptools",
        "pip",
        "wheel",
    ]
    for exc in excludes:
        cmd.extend(["--exclude-module", exc])
    
    # Coleta automática de PyQt6
    cmd.extend(["--collect-all", "PyQt6"])
    
    # Script principal
    cmd.append(MAIN_SCRIPT)
    
    # Executa
    print("📋 Comando PyInstaller:")
    print(f"   {' '.join(cmd[:10])}...")
    print()
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print()
        print("=" * 60)
        print("✅ BUILD CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        
        dist_path = Path("dist") / APP_NAME
        if onefile:
            if plat == "windows":
                exe_path = Path("dist") / f"{APP_NAME}.exe"
            else:
                exe_path = Path("dist") / APP_NAME
            print(f"\n📁 Executável: {exe_path}")
        else:
            print(f"\n📁 Pasta de distribuição: {dist_path}/")
            if plat == "windows":
                print(f"   Executável: {dist_path}/{APP_NAME}.exe")
            else:
                print(f"   Executável: {dist_path}/{APP_NAME}")
        
        print("\n📝 Próximos passos:")
        if onefile:
            print("   1. Copie o executável para o sistema de destino")
            print("   2. Crie uma pasta 'data/logs' ao lado do executável")
        else:
            print(f"   1. Copie a pasta '{dist_path}' para o sistema de destino")
            print("   2. Execute o programa diretamente")
        
        return True
    else:
        print()
        print("❌ FALHA NO BUILD!")
        print("   Verifique os erros acima.")
        return False


def create_launcher_scripts():
    """Cria scripts de lançamento para facilitar execução."""
    dist_path = Path("dist") / APP_NAME
    
    if not dist_path.exists():
        return
    
    # Linux launcher
    linux_launcher = dist_path / "run.sh"
    linux_launcher.write_text(f"""#!/bin/bash
# NPA Ground Station Launcher
cd "$(dirname "$0")"

# Configura o caminho dos plugins Qt
export QT_PLUGIN_PATH="$(pwd)/_internal/PyQt6/Qt6/plugins:$QT_PLUGIN_PATH"

# Tenta usar xcb (X11) se wayland falhar
if [ -z "$QT_QPA_PLATFORM" ]; then
    if [ -n "$WAYLAND_DISPLAY" ]; then
        export QT_QPA_PLATFORM=wayland
    elif [ -n "$DISPLAY" ]; then
        export QT_QPA_PLATFORM=xcb
    fi
fi

./{APP_NAME} "$@"
""")
    linux_launcher.chmod(0o755)
    
    # Windows launcher
    windows_launcher = dist_path / "run.bat"
    windows_launcher.write_text(f"""@echo off
REM NPA Ground Station Launcher
cd /d "%~dp0"
start "" "{APP_NAME}.exe" %*
""")
    
    print(f"\n📜 Scripts de lançamento criados:")
    print(f"   Linux:   {linux_launcher}")
    print(f"   Windows: {windows_launcher}")


def copy_documentation():
    """Copia documentação completa para o pacote distribuído."""
    dist_path = Path("dist") / APP_NAME
    
    if not dist_path.exists():
        return
    
    # Copia o manual do usuário
    manual_src = Path("docs/MANUAL_USUARIO.md")
    if manual_src.exists():
        shutil.copy(manual_src, dist_path / "MANUAL_USUARIO.md")
        print(f"📄 Manual copiado: {dist_path}/MANUAL_USUARIO.md")
    
    # Copia pasta de imagens
    images_src = Path("docs/images")
    images_dst = dist_path / "images"
    if images_src.exists():
        if images_dst.exists():
            shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)
        print(f"📁 Imagens copiadas: {dist_path}/images/")
    
    # Copia README simplificado
    readme_src = Path("docs/README_DISTRIBUICAO.md")
    if readme_src.exists():
        shutil.copy(readme_src, dist_path / "README.md")
        print(f"📄 README copiado: {dist_path}/README.md")


def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Build NPA Ground Station para distribuição",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python build_app.py              # Build padrão (pasta)
  python build_app.py --onefile    # Executável único
  python build_app.py --clean      # Apenas limpa builds
  python build_app.py --clean --onefile  # Limpa e builda
  python build_app.py --no-venv    # Usa Python do sistema
        """
    )
    
    parser.add_argument(
        "--onefile", "-o",
        action="store_true",
        help="Gera executável único (mais lento para iniciar)"
    )
    
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="Limpa builds anteriores antes de compilar"
    )
    
    parser.add_argument(
        "--clean-only",
        action="store_true",
        help="Apenas limpa, não compila"
    )
    
    parser.add_argument(
        "--no-venv",
        action="store_true",
        help="Não usa virtual environment (requer dependências instaladas)"
    )
    
    args = parser.parse_args()
    
    print()
    print("=" * 60)
    print(f"  NPA Ground Station - Build System v{APP_VERSION}")
    print(f"  Plataforma: {platform.system()} {platform.machine()}")
    print("=" * 60)
    print()
    
    # Muda para o diretório do projeto
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Limpa se solicitado
    if args.clean or args.clean_only:
        clean_build_dirs()
    
    if args.clean_only:
        print("✅ Limpeza concluída. Use sem --clean-only para compilar.")
        return 0
    
    use_venv = not args.no_venv
    
    # Configura venv se necessário
    if use_venv:
        if not setup_venv():
            print("❌ Falha ao configurar virtual environment.")
            print("   Tente: python build_app.py --no-venv")
            return 1
    
    # Verifica dependências
    check_dependencies(use_venv=use_venv)
    
    # Executa build
    success = build_pyinstaller(onefile=args.onefile, use_venv=use_venv)
    
    if success and not args.onefile:
        create_launcher_scripts()
        copy_documentation()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())