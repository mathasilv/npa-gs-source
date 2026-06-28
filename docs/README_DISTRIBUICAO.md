# NPA Ground Station v5.6

## Execução pelo Código Fonte (Recomendado)

```bash
# Clone o repositório
git clone https://github.com/npa-ufg/npags.git
cd npags

# Crie um ambiente virtual e instale
python -m venv venv
source venv/bin/activate
pip install -e .

# Execute
npags-gui
```

## Compilando um Executável Standalone

Caso prefira um executável único, compile localmente com PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed \
  --name NPA-GroundStation \
  --add-data "src/npags/config/decoder_schemas:npags/config/decoder_schemas" \
  --add-data "src/npags/gui/assets:npags/gui/assets" \
  --hidden-import "npags" \
  --collect-all "PyQt6" \
  --paths src \
  src/npags/gui/main_window.py
```

O binário será gerado em `dist/NPA-GroundStation`.

## Estrutura de Diretórios

```
npags/
├── src/npags/
│   ├── core/                 # Motor de decodificação
│   ├── gui/                  # Interface gráfica (Qt6)
│   ├── radio/                # Módulos SDR / UDP
│   ├── decoders/             # Gerenciamento de decoders
│   ├── reports/              # Geração de relatórios
│   └── config/
│       └── decoder_schemas/  # Schemas bundled (somente leitura)
├── tools/                    # Ferramentas CLI
├── docs/                     # Documentação
└── README.md                 # Manual completo

# Diretórios de dados do usuário (criados automaticamente):
# Linux:   ~/.local/share/npags/
# Windows: %APPDATA%/npags/
#
# ├── logs/                   # Logs de telemetria
# └── decoders/               # Decoders YAML do usuário (persistente)
```

## Requisitos

- Python 3.10 ou superior
- 4GB RAM (8GB recomendado)
- Hardware opcional: RTL-SDR, HackRF ou Airspy

## Modo SDR (Opcional)

Para recepção via rádio SDR:

### Linux
```bash
# Ubuntu/Debian
sudo apt install gnuradio gr-osmosdr

# Arch Linux
sudo pacman -S gnuradio python-gnuradio gr-osmosdr
```

## Primeiros Passos

1. Execute o programa (`npags-gui` ou executável compilado)
2. Selecione modo: **SDR Radio** ou **UDP Network**
3. Configure os parâmetros
4. Selecione um **decoder**
5. Clique em **INICIAR**
6. Clique em **DASHBOARD** para visualizar dados

## Suporte

- Manual completo: `MANUAL_USUARIO.md`
- Repositório: https://github.com/npa-ufg/npags
- Issues: https://github.com/npa-ufg/npags/issues

---

**NPA-UFG** | Ground Station System v5.6
