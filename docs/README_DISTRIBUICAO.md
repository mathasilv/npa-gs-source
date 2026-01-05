# NPA Ground Station v5.6

## Execução Rápida

### Windows
```
Duplo clique em NPA-GroundStation.exe
ou
Execute run.bat
```

### Linux
```bash
./NPA-GroundStation
# ou
./run.sh
```

## Estrutura de Arquivos

```
NPA-GroundStation/
├── NPA-GroundStation       # Executável (Linux)
├── NPA-GroundStation.exe   # Executável (Windows)
├── run.sh / run.bat        # Scripts de lançamento
├── MANUAL_USUARIO.md       # Manual completo
├── config/
│   └── decoder_schemas/    # Configurações de decoders (editável)
└── data/
    └── logs/               # Logs de telemetria
```

## Requisitos

### Windows
- Windows 10 ou superior (64-bit)
- 4GB RAM (8GB recomendado)

### Linux  
- Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch Linux
- 4GB RAM (8GB recomendado)

## Modo SDR (Opcional)

Para recepção via rádio SDR:

### Windows
1. Instale [Zadig](https://zadig.akeo.ie/) para drivers USB
2. Conecte o SDR e instale driver WinUSB

### Linux
```bash
# Ubuntu/Debian
sudo apt install rtl-sdr

# Arch Linux
sudo pacman -S rtl-sdr

# Fedora
sudo dnf install rtl-sdr
```

## Primeiros Passos

1. Execute o programa
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
