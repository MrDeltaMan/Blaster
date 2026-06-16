import time
import json
import os
import sys
import subprocess
import select
import logging
from pathlib import Path
from evdev import InputDevice, list_devices, ecodes

# Configuração de Paths usando pathlib
CONFIG_DIR = Path.home() / ".config" / "blaster"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

ARQUIVO_CONFIG = CONFIG_DIR / "blaster_config.json"
ARQUIVO_LAST_DEVICE = CONFIG_DIR / ".last_device_name"
ARQUIVO_LOG = CONFIG_DIR / "daemon.log"

# Setup de Logging Duplo
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

if not logger.handlers:
    file_handler = logging.FileHandler(str(ARQUIVO_LOG), encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

_ABS_GAS   = getattr(ecodes, "ABS_GAS",   -1)
_ABS_BRAKE = getattr(ecodes, "ABS_BRAKE", -1)

def e_um_gamepad(dev: InputDevice) -> bool:
    try:
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        botoes_controle = {
            ecodes.BTN_GAMEPAD, ecodes.BTN_SOUTH, ecodes.BTN_A, 
            ecodes.BTN_1, ecodes.BTN_TRIGGER, ecodes.BTN_MODE
        }
        if any(btn in caps for btn in botoes_controle):
            return True
        if "gamepad" in dev.name.lower() or "controller" in dev.name.lower() or "joystick" in dev.name.lower():
            return True
    except Exception:
        pass
    return False

def obter_ambiente_grafico_blindado() -> dict:
    env = os.environ.copy()
    if "WAYLAND_DISPLAY" not in env and "DISPLAY" not in env:
        try:
            resultado = subprocess.check_output(["systemctl", "--user", "show-environment"], text=True)
            for linha in resultado.splitlines():
                if "=" in linha:
                    chave, valor = linha.split("=", 1)
                    if chave in ["WAYLAND_DISPLAY", "DISPLAY", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"]:
                        env[chave] = valor
        except Exception as e:
            logger.error(f"Erro ao recuperar variáveis do systemd: {e}")
    return env

def ler_configuracoes() -> dict:
    if ARQUIVO_CONFIG.exists():
        try:
            return json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON: {e}")
    return {}

def resolver_caminho_real(path_salvo: str) -> str:
    if path_salvo and os.path.exists(path_salvo):
        if os.path.islink(path_salvo):
            return os.path.realpath(path_salvo)
        return path_salvo
    return ""

def encontrar_path_por_nome(nome_alvo: str):
    if not nome_alvo:
        return None
    
    # 1. Varre links de udev persistentes primeiro para evitar conflitos de barramento
    pastas_estaveis = [Path("/dev/input/by-id"), Path("/dev/input/by-path")]
    for pasta in pastas_estaveis:
        if pasta.exists():
            for p in pasta.iterdir():
                try:
                    dev = InputDevice(str(p))
                    if dev.name == nome_alvo and e_um_gamepad(dev):
                        return str(p)
                except OSError:
                    continue

    # 2. Fallback de varredura clássica
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if dev.name == nome_alvo and e_um_gamepad(dev):
                return path
        except OSError:
            continue
    return None

def motor_principal():
    logger.info("Blaster Daemon iniciado com monitoramento duplo de saída.")

    ultimo_mtime_config = 0.0
    config = {}
    catraca_bloqueada = False
    avisou_espera = False

    while True:  # LOOP EXTERNO: ESTADO PERMANENTE DE RECONEXÃO AGRESSIVA
        try:
            try:
                mtime_atual = ARQUIVO_CONFIG.stat().st_mtime
            except FileNotFoundError:
                mtime_atual = 0.0

            if mtime_atual != ultimo_mtime_config:
                config = ler_configuracoes()
                ultimo_mtime_config = mtime_atual

            macros = config.get("macros", [])
            device_path_salvo = config.get("gamepad_path")

            if not macros:
                time.sleep(5)
                continue

            path_alvo = ""

            # Passo 1: Tenta abrir o path salvo nas configurações
            if device_path_salvo:
                path_real = resolver_caminho_real(device_path_salvo)
                if path_real:
                    try:
                        dev_teste = InputDevice(path_real)
                        if e_um_gamepad(dev_teste):
                            path_alvo = device_path_salvo
                            ARQUIVO_LAST_DEVICE.write_text(dev_teste.name, encoding="utf-8")
                    except OSError:
                        pass

            # Passo 2: Se o path fixo falhar, tenta relocalizar pelo histórico do nome do controle
            if not path_alvo and ARQUIVO_LAST_DEVICE.exists():
                nome_controle = ARQUIVO_LAST_DEVICE.read_text(encoding="utf-8").strip()
                path_alvo = encontrar_path_por_nome(nome_controle)

            if not path_alvo:
                if not avisou_espera:
                    logger.warning("Nenhum controle mapeado ou encontrado no histórico recente. Aguardando conexão física...")
                    avisou_espera = True
                time.sleep(4)
                continue

            avisou_espera = False
            path_operacional = resolver_caminho_real(path_alvo)
            dev = InputDevice(path_operacional)
            logger.info(f"Conectado com sucesso a: {dev.name} via {path_alvo}")

            botoes_pressionados = set()
            ultimo_disparo = {}
            proxima_checagem_watchdog = time.time() + 3.0

            while True:  # LOOP INTERNO: LEITURA DE EVENTOS ATIVOS DO HARDWARE
                agora = time.time()

                # WATCHDOG ATIVO: Força a validação física caso o socket evdev silencie sem disparar erro
                if agora > proxima_checagem_watchdog:
                    if not os.path.exists(path_operacional):
                        logger.warning("Watchdog detectou que o arquivo do dispositivo sumiu fisicamente do Linux.")
                        break  # Quebra o loop interno para re-mapear o controle no barramento
                    proxima_checagem_watchdog = agora + 3.0

                r, _, _ = select.select([dev], [], [], 0.02)

                try:
                    mtime_verificacao = ARQUIVO_CONFIG.stat().st_mtime
                    if mtime_verificacao != ultimo_mtime_config:
                        logger.info("Configuração atualizada detectada. Recarregando macros.")
                        config = ler_configuracoes()
                        macros = config.get("macros", [])
                        ultimo_mtime_config = mtime_verificacao
                        if config.get("gamepad_path") != path_alvo:
                            logger.info("Nova alteração de hardware feita na UI. Mudando escuta...")
                            break
                except FileNotFoundError:
                    pass

                if r:
                    for event in dev.read():
                        if event.type == ecodes.EV_SYN and event.code == ecodes.SYN_DROPPED:
                            logger.warning("Estouro de buffer detectado (SYN_DROPPED). Limpando chaves fantasmas.")
                            botoes_pressionados.clear()
                            continue

                        mudou_estado = False

                        if event.type == ecodes.EV_KEY:
                            nome_botao = ecodes.keys.get(event.code, f"KEY_{event.code}")
                            if isinstance(nome_botao, list): nome_botao = nome_botao[0]
                            nome_botao = str(nome_botao)

                            if event.value == 1:
                                botoes_pressionados.add(nome_botao)
                                mudou_estado = True
                            elif event.value == 0:
                                botoes_pressionados.discard(nome_botao)
                                mudou_estado = True

                        elif event.type == ecodes.EV_ABS:
                            if event.code == ecodes.ABS_HAT0X:
                                botoes_pressionados.difference_update({"DPAD_LEFT", "DPAD_RIGHT"})
                                if event.value == 1: botoes_pressionados.add("DPAD_RIGHT")
                                elif event.value == -1: botoes_pressionados.add("DPAD_LEFT")
                                mudou_estado = True
                            elif event.code == ecodes.ABS_HAT0Y:
                                botoes_pressionados.difference_update({"DPAD_UP", "DPAD_DOWN"})
                                if event.value == 1: botoes_pressionados.add("DPAD_DOWN")
                                elif event.value == -1: botoes_pressionados.add("DPAD_UP")
                                mudou_estado = True
                            elif event.code in (ecodes.ABS_Z, _ABS_GAS):
                                if event.value > 150: botoes_pressionados.add("GATILHO_ESQUERDO")
                                else: botoes_pressionados.discard("GATILHO_ESQUERDO")
                                mudou_estado = True
                            elif event.code in (ecodes.ABS_RZ, _ABS_BRAKE):
                                if event.value > 150: botoes_pressionados.add("GATILHO_DIREITO")
                                else: botoes_pressionados.discard("GATILHO_DIREITO")
                                mudou_estado = True

                        if mudou_estado and botoes_pressionados:
                            for macro in macros:
                                combo = set(macro["combo"])
                                if not combo.issubset(botoes_pressionados):
                                    continue

                                comando = macro["comando"]
                                cooldown = macro.get("cooldown", 0.4)

                                if agora - ultimo_disparo.get(comando, 0) <= cooldown:
                                    continue

                                env_blindado = obter_ambiente_grafico_blindado()

                                if comando == "blaster://toggle_catraca":
                                    catraca_bloqueada = not catraca_bloqueada
                                    msg = "Macros CONGELADAS 🔒" if catraca_bloqueada else "Macros ATIVADAS 🔓"
                                    logger.info(f"Catraca acionada: {msg}")
                                    subprocess.Popen(
                                        ["notify-send", "-a", "Blaster", "Blaster - Catraca", msg],
                                        env=env_blindado
                                    )
                                    ultimo_disparo[comando] = agora
                                    break

                                if catraca_bloqueada:
                                    continue

                                logger.info(f"Executando macro: '{comando}'")
                                subprocess.Popen(
                                    comando, shell=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    env=env_blindado
                                )
                                ultimo_disparo[comando] = agora

        except (OSError, FileNotFoundError, Exception) as e:
            logger.warning(f"Controle desconectado da sessão de monitoramento: {e}. Reiniciando barramento em 2s...")
            time.sleep(2)

if __name__ == "__main__":
    try:
        motor_principal()
    except KeyboardInterrupt:
        logger.info("Daemon encerrado manualmente.")
