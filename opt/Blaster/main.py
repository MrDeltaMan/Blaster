import sys
import time
import json
import os
import select
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, QListWidget, QDoubleSpinBox
from PyQt6.QtCore import QThread, pyqtSignal
from evdev import InputDevice, list_devices, ecodes

ARQUIVO_CONFIG = os.path.expanduser("~/.config/blaster/blaster_config.json")

class GamepadListener(QThread):
    botao_pressionado = pyqtSignal(str)
    status_conexao = pyqtSignal(str)

    def __init__(self, device_path=None):
        super().__init__()
        self.device_path = device_path
        self.rodando = True

    def alterar_dispositivo(self, path):
        self.device_path = path

    def run(self):
        while self.rodando:
            if not self.device_path:
                self.status_conexao.emit("Nenhum controle selecionado")
                # Dorme fracionado para responder rápido ao fechamento do app
                for _ in range(10):
                    if not self.rodando: return
                    time.sleep(0.1)
                continue

            try:
                dev = InputDevice(self.device_path)
                self.status_conexao.emit(f"Escutando: {dev.name}")
                
                lt_pressionado = False
                rt_pressionado = False
                
                while self.rodando and self.device_path == dev.path:
                    r, w, x = select.select([dev], [], [], 0.2)
                    if not r:
                        continue

                    for event in dev.read():
                        if event.type == 1 and event.value == 1:
                            nome_botao = ecodes.keys.get(event.code, f"KEY_{event.code}")
                            if not isinstance(nome_botao, str): nome_botao = nome_botao[0]
                            self.botao_pressionado.emit(str(nome_botao))
                        
                        elif event.type == 3:
                            if event.code == 16 and event.value != 0:
                                self.botao_pressionado.emit("DPAD_RIGHT" if event.value == 1 else "DPAD_LEFT")
                            elif event.code == 17 and event.value != 0:
                                self.botao_pressionado.emit("DPAD_DOWN" if event.value == 1 else "DPAD_UP")
                            
                            elif event.code in [2, 10]:
                                if event.value > 150 and not lt_pressionado:
                                    lt_pressionado = True
                                    self.botao_pressionado.emit("GATILHO_ESQUERDO")
                                elif event.value < 50: 
                                    lt_pressionado = False

                            elif event.code in [5, 9]:
                                if event.value > 150 and not rt_pressionado:
                                    rt_pressionado = True
                                    self.botao_pressionado.emit("GATILHO_DIREITO")
                                elif event.value < 50: 
                                    rt_pressionado = False
                                        
            except (OSError, FileNotFoundError):
                self.status_conexao.emit("Controle desconectado!")
                self.device_path = None
                time.sleep(1)


class BlasterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.combo_atual = []
        self.gravando = False
        self.macro_editando_index = None
        self.init_ui()
        self.iniciar_thread()
        self.atualizar_lista_controles()
        self.carregar_macros_na_lista_visual()
        self.verificar_e_instalar_autostart()

    def init_ui(self):
        self.setWindowTitle('Blaster - Gamepad Macro Generator')
        self.setGeometry(300, 300, 800, 560)
        layout_principal = QHBoxLayout()
        coluna_esquerda = QVBoxLayout()

        coluna_esquerda.addWidget(QLabel('1. Selecione seu Controle:', self))
        self.combo_controles = QComboBox(self)
        self.combo_controles.currentIndexChanged.connect(self.ao_selecionar_controle)
        coluna_esquerda.addWidget(self.combo_controles)

        self.botao_atualizar = QPushButton('Atualizar Lista de Controles', self)
        self.botao_atualizar.clicked.connect(self.atualizar_lista_controles)
        coluna_esquerda.addWidget(self.botao_atualizar)

        self.label_status = QLabel('Status: Aguardando...', self)
        self.label_status.setStyleSheet("font-weight: bold; color: gray; margin-bottom: 5px;")
        coluna_esquerda.addWidget(self.label_status)

        coluna_esquerda.addWidget(QLabel('2. Identificador / Nome da Macro:', self))
        self.input_nome = QLineEdit(self)
        self.input_nome.setPlaceholderText('Ex: Aumentar Volume, Abrir Firefox')
        coluna_esquerda.addWidget(self.input_nome)

        coluna_esquerda.addWidget(QLabel('3. Grave seu Combo de Botões:', self))
        self.botao_gravar = QPushButton('Iniciar Gravação do Combo')
        self.botao_gravar.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.botao_gravar.clicked.connect(self.alternar_gravacao)
        coluna_esquerda.addWidget(self.botao_gravar)

        self.label_combo_visual = QLabel('Combo atual: (Aperte em Iniciar...)', self)
        self.label_combo_visual.setStyleSheet("font-size: 13px; color: blue; padding: 5px; background: #eef;")
        coluna_esquerda.addWidget(self.label_combo_visual)

        coluna_esquerda.addWidget(QLabel('4. Tempo de Espera / Cooldown (segundos):', self))
        self.input_cooldown = QDoubleSpinBox(self)
        self.input_cooldown.setRange(0.01, 5.0)
        self.input_cooldown.setSingleStep(0.05)
        self.input_cooldown.setValue(0.40)
        coluna_esquerda.addWidget(self.input_cooldown)

        coluna_esquerda.addWidget(QLabel('5. Comando do Terminal:', self))
        self.input_comando = QLineEdit(self)
        self.input_comando.setPlaceholderText('Ex: amixer -D pulse sset Master 5%+ ')
        coluna_esquerda.addWidget(self.input_comando)

        layout_botoes_acao = QHBoxLayout()
        
        self.botao_salvar = QPushButton('Salvar Macro', self)
        self.botao_salvar.setStyleSheet("font-weight: bold; min-height: 35px; background-color: #1976D2; color: white;")
        self.botao_salvar.clicked.connect(self.ao_salvar_macro)
        layout_botoes_acao.addWidget(self.botao_salvar, stretch=3)

        self.botao_limpar_selecao = QPushButton('Nova Macro (Limpar)', self)
        self.botao_limpar_selecao.setStyleSheet("font-weight: bold; min-height: 35px; background-color: #757575; color: white;")
        self.botao_limpar_selecao.clicked.connect(self.resetar_modo_criacao)
        self.botao_limpar_selecao.setVisible(False)
        layout_botoes_acao.addWidget(self.botao_limpar_selecao, stretch=1)

        coluna_esquerda.addLayout(layout_botoes_acao)

        coluna_direita = QVBoxLayout()
        coluna_direita.addWidget(QLabel('Macros Mapeadas (Clique para Editar):', self))
        self.lista_visual_macros = QListWidget(self)
        self.lista_visual_macros.itemClicked.connect(self.ao_clicar_para_editar)
        coluna_direita.addWidget(self.lista_visual_macros)

        self.botao_deletar = QPushButton('Deletar Macro Selecionada', self)
        self.botao_deletar.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.botao_deletar.clicked.connect(self.ao_deletar_macro)
        coluna_direita.addWidget(self.botao_deletar)

        self.label_aviso_daemon = QLabel('', self)
        self.label_aviso_daemon.setWordWrap(True)
        coluna_direita.addWidget(self.label_aviso_daemon)

        layout_principal.addLayout(coluna_esquerda, stretch=4)
        layout_principal.addLayout(coluna_direita, stretch=3)
        self.setLayout(layout_principal)

    def verificar_e_instalar_autostart(self):
        pasta_autostart = os.path.expanduser("~/.config/autostart")
        arquivo_desktop = os.path.join(pasta_autostart, "blaster_daemon.desktop")
        os.makedirs(pasta_autostart, exist_ok=True)
        
        # Pega o diretório dinâmico onde este script está rodando
        base_dir = os.path.dirname(os.path.abspath(__file__))
        caminho_daemon = os.path.join(base_dir, "daemon.py")
        
        conteudo_autostart = f"""[Desktop Entry]
Type=Application
Exec=python3 {caminho_daemon}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Blaster Daemon
Comment=Motor de macros de controle para segundo plano
X-GNOME-Autostart-Delay=5
"""
        if not os.path.exists(arquivo_desktop):
            try:
                with open(arquivo_desktop, "w") as f: 
                    f.write(conteudo_autostart)
                self.label_aviso_daemon.setText("⚠️ O Daemon foi adicionado à inicialização! Reinicie o sistema para que as macros funcionem em segundo plano.")
                self.label_aviso_daemon.setStyleSheet("font-weight: bold; color: #d32f2f; margin-top: 5px;")
            except Exception as e:
                self.label_aviso_daemon.setText(f"Erro ao criar autostart: {e}")
        else:
            self.label_aviso_daemon.setText("ℹ️ O Blaster Daemon já está configurado para iniciar com o sistema.")
            self.label_aviso_daemon.setStyleSheet("color: #0d47a1; margin-top: 5px;")

    def ler_configuracoes(self):
        os.makedirs(os.path.dirname(ARQUIVO_CONFIG), exist_ok=True)
        if os.path.exists(ARQUIVO_CONFIG):
            try:
                with open(ARQUIVO_CONFIG, "r") as f: 
                    return json.load(f)
            except Exception: 
                pass
        return {"gamepad_path": None, "macros": []}

    def carregar_macros_na_lista_visual(self):
        self.lista_visual_macros.clear()
        dados = self.ler_configuracoes()
        for macro in dados.get("macros", []):
            nome = macro.get("nome", "Sem Nome")
            combo_txt = " + ".join(macro.get("combo", []))
            cooldown = macro.get("cooldown", 0.4)
            self.lista_visual_macros.addItem(f"{nome} ({cooldown}s)\n➔ {combo_txt}")

    def ao_clicar_para_editar(self, item):
        index = self.lista_visual_macros.row(item)
        dados = self.ler_configuracoes()
        macros = dados.get("macros", [])
        
        if 0 <= index < len(macros):
            macro = macros[index]
            self.macro_editando_index = index
            self.input_nome.setText(macro.get("nome", ""))
            self.input_comando.setText(macro.get("comando", ""))
            self.input_cooldown.setValue(macro.get("cooldown", 0.4))
            self.combo_atual = macro.get("combo", [])
            self.label_combo_visual.setText(f"Combo carregado: {' + '.join(self.combo_atual)}")
            
            self.botao_salvar.setText("Atualizar Macro Selecionada")
            self.botao_salvar.setStyleSheet("font-weight: bold; min-height: 35px; background-color: #E65100; color: white;")
            self.botao_limpar_selecao.setVisible(True)

    def resetar_modo_criacao(self):
        self.input_nome.clear()
        self.input_comando.clear()
        self.input_cooldown.setValue(0.40)
        self.combo_atual = []
        self.macro_editando_index = None
        self.label_combo_visual.setText("Combo atual: (Aperte em Iniciar...)")
        self.lista_visual_macros.clearSelection()
        
        self.botao_salvar.setText("Salvar Macro")
        self.botao_salvar.setStyleSheet("font-weight: bold; min-height: 35px; background-color: #1976D2; color: white;")
        self.botao_limpar_selecao.setVisible(False)

    def ao_salvar_macro(self):
        nome = self.input_nome.text().strip()
        comando = self.input_comando.text().strip()
        cooldown = round(self.input_cooldown.value(), 2)
        if not nome or not self.combo_atual or not comando: return

        dados_config = self.ler_configuracoes()
        nova_macro = {"nome": nome, "combo": self.combo_atual, "comando": comando, "cooldown": cooldown}

        if self.macro_editando_index is not None and self.macro_editando_index < len(dados_config["macros"]):
            dados_config["macros"][self.macro_editando_index] = nova_macro
        else:
            dados_config["macros"].append(nova_macro)

        if self.thread_gamepad.device_path:
            dados_config["gamepad_path"] = self.thread_gamepad.device_path
            
        with open(ARQUIVO_CONFIG, "w") as f: 
            json.dump(dados_config, f, indent=4)

        self.resetar_modo_criacao()
        self.carregar_macros_na_lista_visual()

    def ao_deletar_macro(self):
        item_selecionado = self.lista_visual_macros.currentRow()
        if item_selecionado == -1: return
        dados_config = self.ler_configuracoes()
        if 0 <= item_selecionado < len(dados_config["macros"]):
            dados_config["macros"].pop(item_selecionado)
            with open(ARQUIVO_CONFIG, "w") as f: 
                json.dump(dados_config, f, indent=4)
            
            self.resetar_modo_criacao()
            self.carregar_macros_na_lista_visual()

    def iniciar_thread(self):
        self.thread_gamepad = GamepadListener()
        self.thread_gamepad.botao_pressionado.connect(self.receber_input_controle)
        self.thread_gamepad.status_conexao.connect(self.atualizar_status_conexao)
        self.thread_gamepad.start()

    def atualizar_lista_controles(self):
        self.combo_controles.clear()
        self.combo_controles.addItem("Selecione um dispositivo...", None)
        for path in list_devices():
            try:
                dev = InputDevice(path)
                if 304 in dev.capabilities().get(1, []) or "gamepad" in dev.name.lower() or "controller" in dev.name.lower():
                    self.combo_controles.addItem(f"{dev.name} ({path})", path)
            except Exception: 
                continue

    def ao_selecionar_controle(self, index):
        path = self.combo_controles.itemData(index)
        self.thread_gamepad.alterar_dispositivo(path)

    def atualizar_status_conexao(self, texto):
        self.label_status.setText(f"Status: {texto}")
        cor = "green" if "Escutando" in texto else "red"
        self.label_status.setStyleSheet(f"font-weight: bold; color: {cor};")

    def alternar_gravacao(self):
        if not self.gravando:
            self.gravando = True
            self.combo_atual = []
            self.label_combo_visual.setText("Combo: [Gravando...]")
            self.botao_gravar.setText("Parar Gravação")
            self.botao_gravar.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        else:
            self.gravando = False
            self.botao_gravar.setText("Iniciar Gravação do Combo")
            self.botao_gravar.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")

    def receber_input_controle(self, nome_botao):
        if self.gravando:
            if nome_botao not in self.combo_atual:
                self.combo_atual.append(nome_botao)
                self.label_combo_visual.setText(f"Combo: {' + '.join(self.combo_atual)}")

    def closeEvent(self, event):
        self.thread_gamepad.rodando = False
        self.thread_gamepad.wait(1500) # Aguarda até 1.5s para a thread encerrar graciosamente
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    janela = BlasterApp()
    janela.show()
    sys.exit(app.exec())
