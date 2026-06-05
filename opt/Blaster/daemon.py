import time
import json
import os
import subprocess
import select
from evdev import InputDevice, list_devices, ecodes

ARQUIVO_CONFIG = os.path.expanduser("~/.config/blaster/blaster_config.json")
ARQUIVO_CACHE_NAME = os.path.expanduser("~/.config/blaster/.last_device_name")

# Variáveis globais para cache de leitura do disco
_ultima_leitura_mtime = 0
_config_em_cache = None

def ler_configuracoes_otimizado():
    """
    Lê o JSON apenas se o arquivo foi modificado.
    Evita gargalos massivos de I/O de disco a cada milissegundo.
    """
    global _ultima_leitura_mtime, _config_em_cache
    
    if not os.path.exists(ARQUIVO_CONFIG):
        return None
        
    try:
        mtime_atual = os.path.getmtime(ARQUIVO_CONFIG)
        if mtime_atual > _ultima_leitura_mtime or _config_em_cache is None:
            with open(ARQUIVO_CONFIG, "r") as f: 
                _config_em_cache = json.load(f)
            _ultima_leitura_mtime = mtime_atual
    except Exception as e:
        print(f"[Daemon] Erro ao ler configurações: {e}")
        
    return _config_em_cache

def encontrar_path_por_nome(nome_alvo):
    for path in list_devices():
        try:
            dev = InputDevice(path)
            if dev.name == nome_alvo: 
                return path
        except Exception: 
            continue
    return None

def motor_principal():
    print("[Blaster Daemon] Iniciando motor de segundo plano...")
    
    while True:
        config = ler_configuracoes_otimizado()
        if not config:
            time.sleep(5)
            continue

        macros = config.get("macros", [])
        device_path_salvo = config.get("gamepad_path")

        if not macros:
            time.sleep(5)
            continue

        nome_controle = None
        if device_path_salvo:
            try:
                nome_controle = InputDevice(device_path_salvo).name
                with open(ARQUIVO_CACHE_NAME, "w") as f:
                    f.write(nome_controle)
            except Exception:
                if os.path.exists(ARQUIVO_CACHE_NAME):
                    with open(ARQUIVO_CACHE_NAME, "r") as f:
                        nome_controle = f.read().strip()

        if not nome_controle:
            time.sleep(5)
            continue

        path_atual = encontrar_path_por_nome(nome_controle)
        if not path_atual:
            time.sleep(3)
            continue

        try:
            dev = InputDevice(path_atual)
            print(f"[Daemon] Conectado com sucesso a: {dev.name}")
            
            botoes_pressionados = set()
            ultimo_disparo = {}

            while True:
                # Timeout de 0.05s é um bom balanço entre responsividade e ciclo de CPU
                r, w, x = select.select([dev], [], [], 0.05)
                
                # Atualiza as macros em tempo real SEM estressar o disco (usa cache inteligente)
                config_atualizada = ler_configuracoes_otimizado()
                if config_atualizada:
                    macros = config_atualizada.get("macros", macros)

                if r:
                    for event in dev.read():
                        mudou_estado = False

                        if event.type == 1:
                            nome_botao = ecodes.keys.get(event.code, f"KEY_{event.code}")
                            if not isinstance(nome_botao, str): nome_botao = nome_botao[0]
                            nome_botao = str(nome_botao)
                            
                            if event.value == 1: botoes_pressionados.add(nome_botao)
                            elif event.value == 0: botoes_pressionados.discard(nome_botao)
                            mudou_estado = True

                        elif event.type == 3:
                            if event.code == 16:
                                botoes_pressionados.discard("DPAD_LEFT")
                                botoes_pressionados.discard("DPAD_RIGHT")
                                if event.value == 1: botoes_pressionados.add("DPAD_RIGHT")
                                elif event.value == -1: botoes_pressionados.add("DPAD_LEFT")
                                mudou_estado = True
                            elif event.code == 17:
                                botoes_pressionados.discard("DPAD_UP")
                                botoes_pressionados.discard("DPAD_DOWN")
                                if event.value == 1: botoes_pressionados.add("DPAD_DOWN")
                                elif event.value == -1: botoes_pressionados.add("DPAD_UP")
                                mudou_estado = True
                            
                            elif event.code in [2, 10]:
                                if event.value > 150: botoes_pressionados.add("GATILHO_ESQUERDO")
                                else: botoes_pressionados.discard("GATILHO_ESQUERDO")
                                mudou_estado = True

                            elif event.code in [5, 9]:
                                if event.value > 150: botoes_pressionados.add("GATILHO_DIREITO")
                                else: botoes_pressionados.discard("GATILHO_DIREITO")
                                mudou_estado = True

                        if mudou_estado and botoes_pressionados:
                            agora = time.time()
                            for macro in macros:
                                # Verifica se todos os botões da macro estão sendo pressionados atualmente
                                if all(b in botoes_pressionados for b in macro.get("combo", [])):
                                    comando = macro.get("comando")
                                    cooldown = macro.get("cooldown", 0.4)
                                    
                                    if agora - ultimo_disparo.get(comando, 0) > cooldown:
                                        print(f"[Daemon] Executando rajada: {comando}")
                                        ambiente_usuario = os.environ.copy()
                                        ambiente_usuario["DISPLAY"] = ":0"
                                        
                                        subprocess.Popen(
                                            comando, 
                                            shell=True, 
                                            stdout=subprocess.DEVNULL, 
                                            stderr=subprocess.DEVNULL,
                                            env=ambiente_usuario
                                        )
                                        ultimo_disparo[comando] = agora

        except (OSError, FileNotFoundError):
            print("[Daemon] Conexão perdida. Tentando reconectar...")
            time.sleep(2)

if __name__ == "__main__":
    try: 
        motor_principal()
    except KeyboardInterrupt: 
        print("\n[Daemon] Desligando.")
