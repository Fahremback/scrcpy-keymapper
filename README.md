# 🎮 Scrcpy Keymapper

Fork do [scrcpy](https://github.com/Genymobile/scrcpy) com **keymapper integrado** para jogar jogos Android no PC com teclado e mouse — estilo GameLoop/BlueStacks.

## ✨ Features

### 🕹️ Engine de Mapeamento (C)
O keymapper roda **direto no código C do scrcpy**, sem latência adicional:

| Tipo | Descrição | Exemplo no `keymap.cfg` |
|------|-----------|------------------------|
| **KEY** | Tecla → Toque na tela | `KEY w 0.500 0.300` |
| **MOUSE** | Clique mouse → Toque | `MOUSE left 0.500 0.500` |
| **AIM** | Âncora da mira FPS (mouse lock) | `AIM aim 0.700 0.500` |
| **DPAD** | Joystick virtual WASD | `DPAD wasd 0.200 0.700 0.08` |
| **SCROLL** | Roda do mouse → Swipe | `SCROLL scroll 0.500 0.500` |
| **MACRO** | Sequência de taps com delay | `MACRO 5 0.5 0.5 0.1,0.2,100;0.3,0.4,200` |

### 🖥️ Launcher (`scrcpy_launcher.py`)
Interface de inicialização que:
- **Detecta automaticamente** dispositivos ADB conectados
- **Pareia novos dispositivos** via IP ou código de pareamento
- **Configura** resolução, FPS, bitrate, codec, áudio, e mais
- **Salva preferências** em JSON para reutilização
- **Lança tudo** (scrcpy + painel de controle) com um clique

### 🎛️ Painel de Controle (`scrcpy_gui.py`)
Sidebar flutuante com:
- Toggle de **Modo Edição** (F12) — arrastar botões na tela
- Toggle de **Overlay** (F11) — mostrar/ocultar botões
- Toggle de **Modo FPS** (F10) — travar mouse na tela
- **Opacidade** ajustável
- **Lista de mapeamentos** com edição em tempo real
- Suporte a todos os 6 tipos de binding

### ⚡ IPC Assíncrono
Comunicação entre Python e C via `SDL_AddTimer(100ms)` + `sc_post_to_main_thread`:
- **Sem lag** mesmo com tela estática
- **Debounce** de 200ms para inputs rápidos
- Monitoramento de `keymap.cfg` (auto-reload) e `keymap.cmd` (comandos)

## 📁 Estrutura do Projeto

```
├── scrcpy_launcher.py          # Launcher com UI de conexão + config
├── scrcpy_gui.py               # Painel de controle lateral
├── icon.png                    # Ícone do app
└── scrcpy-master/
    └── app/src/
        ├── keymapper.h         # Header com tipos e structs
        ├── keymapper.c         # Engine de mapeamento (C)
        ├── input_manager.c     # Integração com input do scrcpy
        └── screen.c            # Integração com render do scrcpy
```

## 🚀 Como Usar

### Pré-requisitos
- Windows 10/11
- Python 3.10+ com `tkinter`
- ADB no PATH ou na pasta do projeto
- Dispositivo Android com **Depuração USB/Wireless** ativada

### Instalação
1. Baixe a [release do scrcpy](https://github.com/Genymobile/scrcpy/releases) e extraia
2. Clone este repositório na mesma pasta:
   ```bash
   git clone https://github.com/Fahrembac/scrcpy-keymapper.git
   ```
3. Copie os arquivos do clone para a pasta do scrcpy

### Execução
```bash
python scrcpy_launcher.py
```

### Compilação do C (opcional)
Requer MSYS2 com MinGW64:
```bash
cd scrcpy-master
meson setup build-win64 --cross-file=...
ninja -C build-win64
cp build-win64/app/scrcpy.exe ../scrcpy.exe
```

## ⌨️ Atalhos

| Tecla | Função |
|-------|--------|
| **F10** | Modo FPS (mouse lock) |
| **F11** | Mostrar/Ocultar overlay |
| **F12** | Modo edição |
| **PgUp/PgDn** | Ajustar opacidade |
| **DEL** | Remover binding selecionado |
| **INS** | Adicionar binding |

## 📝 Formato do `keymap.cfg`

```ini
# Scrcpy Keymapper Config
# Types: KEY, MOUSE, AIM, DPAD, SCROLL, MACRO
KEY w 0.500 0.300
KEY a 0.200 0.500
KEY space 0.500 0.900
MOUSE left 0.500 0.500
AIM aim 0.700 0.500
DPAD wasd 0.200 0.700 0.080
SCROLL scroll 0.500 0.500
MACRO 5 0.500 0.500 0.100,0.200,100;0.300,0.400,200
```

## 📜 Licença

Baseado no [scrcpy](https://github.com/Genymobile/scrcpy) — Apache-2.0.
Modificações do keymapper são de uso livre.
