import sys
import time
import json
import select
from pathlib import Path
from typing import Dict, List, Optional, Any
from PyQt6.QtGui import QIcon, QGuiApplication

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox, QListWidget, QDoubleSpinBox,
    QGroupBox, QListWidgetItem, QMessageBox, QSplitter
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from evdev import InputDevice, list_devices, ecodes

# Usando pathlib para gestão moderna de caminhos
CONFIG_DIR = Path.home() / ".config" / "blaster"
ARQUIVO_CONFIG = CONFIG_DIR / "blaster_config.json"

# Definição inteligente do caminho do ícone (Prioridade para /opt, fallback para .config)
PATH_ICONE_OPT = Path("/opt/Blaster/blaster.svg")
PATH_ICONE_FALLBACK = CONFIG_DIR / "blaster.svg"
CAMINHO_ICONE_FINAL = PATH_ICONE_OPT if PATH_ICONE_OPT.exists() else PATH_ICONE_FALLBACK

ESTILO_DARK = """
 QWidget {
    background-color: #1E1E2E;
    color: #CDD6F4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    border: 1px solid #313244;
    border-radius: 14px;
    margin-top: 14px;
    font-weight: bold;
    background-color: #1B1B2A;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    color: #89B4FA;
}

QLineEdit, QDoubleSpinBox, QComboBox {
    background-color: #313244;
    border: 1px solid #45475A;
    border-radius: 10px;
    padding: 9px 10px;
    color: #CDD6F4;
}

QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #89B4FA;
}

QComboBox::drop-down {
    border-left: 1px solid #45475A;
    width: 24px;
}

QPushButton {
    background-color: #45475A;
    color: #CDD6F4;
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #585B70;
}

QPushButton:pressed {
    background-color: #313244;
}

QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 12px;
    padding: 6px;
    outline: 0;
}

QListWidget::item {
    padding: 10px;
    margin: 4px 2px;
    border-bottom: 1px solid #313244;
    border-radius: 10px;
}

QListWidget::item:selected {
    background-color: #313244;
    color: #89B4FA;
}

QScrollBar:vertical {
    background: #181825;
    width: 10px;
    margin: 12px 2px 12px 2px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background: #45475A;
    min-height: 30px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #585B70;
}

QLabel#subtitle {
    color: #9399B2;
}

QLabel#status_ok {
    color: #A6E3A1;
    font-weight: 700;
}

QLabel#status_bad {
    color: #F38BA8;
    font-weight: 700;
}

QLabel#combo_box {
    font-size: 14px;
    color: #CDD6F4;
    padding: 10px 12px;
    background: #181825;
    border-radius: 10px;
    border: 1px dashed #45475A;
}
QToolTip {
    background-color: #1E1E2E;
    color: #CDD6F4;
    border: 1px solid #45475A;
} 
"""

class GamepadListener(QThread):
    botao_pressionado = pyqtSignal(str)
    status_conexao = pyqtSignal(str)

    def __init__(self, device_path: Optional[str] = None):
        super().__init__()
        self.device_path = device_path
        self.rodando = True

    def alterar_dispositivo(self, path: Optional[str]) -> None:
        self.device_path = path

    def run(self) -> None:
        while self.rodando:
            if not self.device_path:
                self.status_conexao.emit("Nenhum controle selecionado")
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
                    r, _, _ = select.select([dev], [], [], 0.2)
                    if not r: continue

                    for event in dev.read():
                        if event.type == ecodes.EV_KEY and event.value == 1:
                            nome_botao = ecodes.keys.get(event.code, f"KEY_{event.code}")
                            if isinstance(nome_botao, list): nome_botao = nome_botao[0]
                            self.botao_pressionado.emit(str(nome_botao))

                        elif event.type == ecodes.EV_ABS:
                            # DPAD
                            if event.code == ecodes.ABS_HAT0X and event.value != 0:
                                self.botao_pressionado.emit("DPAD_RIGHT" if event.value == 1 else "DPAD_LEFT")
                            elif event.code == ecodes.ABS_HAT0Y and event.value != 0:
                                self.botao_pressionado.emit("DPAD_DOWN" if event.value == 1 else "DPAD_UP")
                            
                            # Triggers
                            elif event.code in (ecodes.ABS_Z, ecodes.ABS_GAS):
                                if event.value > 150 and not lt_pressionado:
                                    lt_pressionado = True
                                    self.botao_pressionado.emit("GATILHO_ESQUERDO")
                                elif event.value < 50:
                                    lt_pressionado = False

                            elif event.code in (ecodes.ABS_RZ, ecodes.ABS_BRAKE):
                                if event.value > 150 and not rt_pressionado:
                                    rt_pressionado = True
                                    self.botao_pressionado.emit("GATILHO_DIREITO")
                                elif event.value < 50:
                                    rt_pressionado = False

            except (OSError, FileNotFoundError):
                self.status_conexao.emit("Controle desconectado")
                self.device_path = None
                time.sleep(1)


class BlasterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.combo_atual: List[str] = []
        self.gravando: bool = False
        self.macro_editando_index: Optional[int] = None
        self.init_ui()
        self.iniciar_thread()
        self.atualizar_lista_controles()
        self.carregar_macros_na_lista_visual()
        self.verificar_e_instalar_autostart()

    def init_ui(self) -> None:
        self.setWindowTitle("Blaster Pro - Gamepad Macro Generator")
        
        # Carrega o ícone da janela usando o caminho dinâmico/robusto
        if CAMINHO_ICONE_FINAL.exists():
            self.setWindowIcon(QIcon(str(CAMINHO_ICONE_FINAL)))

        self.setMinimumSize(980, 680)
        self.resize(1100, 720)

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(16, 16, 16, 16)
        layout_principal.setSpacing(14)

        # Barra Superior
        barra_topo = QGroupBox("🎮 Conexão do Controle")
        layout_topo = QHBoxLayout(barra_topo)
        
        self.combo_controles = QComboBox(self)
        self.combo_controles.setMinimumWidth(360)
        self.combo_controles.currentIndexChanged.connect(self.ao_selecionar_controle)
        layout_topo.addWidget(self.combo_controles, 3)

        self.botao_atualizar = QPushButton("Atualizar lista", self)
        self.botao_atualizar.clicked.connect(self.atualizar_lista_controles)
        layout_topo.addWidget(self.botao_atualizar, 1)

        self.label_status = QLabel("Status: Aguardando...", self)
        self.label_status.setObjectName("status_bad")
        layout_topo.addWidget(self.label_status, 2)
        layout_principal.addWidget(barra_topo)

        # Corpo
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Painel Esquerdo
        painel_lista = QGroupBox("⌨️ Macros Mapeadas")
        layout_lista_painel = QVBoxLayout(painel_lista)

        self.input_busca = QLineEdit(self)
        self.input_busca.setPlaceholderText("Buscar macro...")
        self.input_busca.textChanged.connect(self.aplicar_filtro_lista)
        layout_lista_painel.addWidget(self.input_busca)

        self.lista_visual_macros = QListWidget(self)
        self.lista_visual_macros.itemClicked.connect(self.ao_clicar_para_editar)
        layout_lista_painel.addWidget(self.lista_visual_macros, 1)

        self.botao_deletar = QPushButton("Deletar macro selecionada", self)
        self.botao_deletar.setStyleSheet("background-color: #F38BA8; color: #11111B; font-weight: bold;")
        self.botao_deletar.clicked.connect(self.ao_deletar_macro)
        layout_lista_painel.addWidget(self.botao_deletar)

        # Painel Direito
        painel_editor = QGroupBox("⚙️ Configuração da Macro")
        layout_editor = QVBoxLayout(painel_editor)

        layout_editor.addWidget(QLabel("Nome da macro:", self))
        self.input_nome = QLineEdit(self)
        self.input_nome.setPlaceholderText("Ex: Aumentar volume")
        layout_editor.addWidget(self.input_nome)

        layout_editor.addWidget(QLabel("Combo:", self))
        self.botao_gravar = QPushButton("Gravar combo", self)
        self.botao_gravar.setStyleSheet("background-color: #A6E3A1; color: #11111B; font-weight: bold;")
        self.botao_gravar.clicked.connect(self.alternar_gravacao)
        layout_editor.addWidget(self.botao_gravar)

        self.label_combo_visual = QLabel("Combo atual: (clique em ‘Gravar combo’)", self)
        self.label_combo_visual.setObjectName("combo_box")
        layout_editor.addWidget(self.label_combo_visual)

        layout_editor.addWidget(QLabel("Cooldown (segundos):", self))
        self.input_cooldown = QDoubleSpinBox(self)
        self.input_cooldown.setRange(0.01, 5.0)
        self.input_cooldown.setSingleStep(0.05)
        self.input_cooldown.setValue(0.40)
        layout_editor.addWidget(self.input_cooldown)

        layout_editor.addWidget(QLabel("Comando do terminal:", self))
        self.input_comando = QLineEdit(self)
        layout_editor.addWidget(self.input_comando)

        layout_botoes_acao = QHBoxLayout()
        self.botao_salvar = QPushButton("Salvar macro", self)
        self.botao_salvar.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold; font-size: 14px;")
        self.botao_salvar.clicked.connect(self.ao_salvar_macro)
        layout_botoes_acao.addWidget(self.botao_salvar, stretch=3)

        self.botao_limpar_selecao = QPushButton("Cancelar edição", self)
        self.botao_limpar_selecao.setStyleSheet("background-color: #585B70; color: #CDD6F4;")
        self.botao_limpar_selecao.clicked.connect(self.resetar_modo_criacao)
        self.botao_limpar_selecao.setVisible(False)
        layout_botoes_acao.addWidget(self.botao_limpar_selecao, stretch=1)

        layout_editor.addLayout(layout_botoes_acao)

        splitter.addWidget(painel_lista)
        splitter.addWidget(painel_editor)
        splitter.setSizes([420, 560])
        layout_principal.addWidget(splitter, 1)

        self.label_aviso_daemon = QLabel("", self)
        self.label_aviso_daemon.setWordWrap(True)
        layout_principal.addWidget(self.label_aviso_daemon)

    def verificar_e_instalar_autostart(self) -> None:
        pasta_autostart = Path.home() / ".config" / "autostart"
        pasta_autostart.mkdir(parents=True, exist_ok=True)
        arquivo_desktop = pasta_autostart / "blaster_daemon.desktop"

        caminho_daemon = Path(__file__).resolve().parent / "daemon.py"

        conteudo_autostart = f"""[Desktop Entry]
Type=Application
Exec=python3 {caminho_daemon}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=Blaster Daemon
Comment=Motor de macros de controle para segundo plano
Icon={CAMINHO_ICONE_FINAL}
X-GNOME-Autostart-Delay=5
"""
        if not arquivo_desktop.exists():
            try:
                arquivo_desktop.write_text(conteudo_autostart, encoding="utf-8")
                self.label_aviso_daemon.setText("⚠️ Daemon adicionado à inicialização. Reinicie para rodar em segundo plano.")
                self.label_aviso_daemon.setStyleSheet("padding: 12px; background-color: #313244; border-radius: 10px; border-left: 4px solid #FAB387;")
            except Exception as e:
                self.label_aviso_daemon.setText(f"Erro ao criar autostart: {e}")
        else:
            self.label_aviso_daemon.setText("ℹ️ O Blaster Daemon já está configurado para iniciar com o sistema.")
            self.label_aviso_daemon.setStyleSheet("padding: 12px; background-color: #313244; border-radius: 10px; border-left: 4px solid #89B4FA;")

    def ler_configuracoes(self) -> Dict[str, Any]:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if ARQUIVO_CONFIG.exists():
            try:
                return json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"gamepad_path": None, "macros": []}

    def salvar_configuracoes(self, dados: Dict[str, Any]) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        ARQUIVO_CONFIG.write_text(json.dumps(dados, indent=4, ensure_ascii=False), encoding="utf-8")

    def formato_combo(self, combo: List[str]) -> str:
        return " + ".join(combo) if combo else "—"

    def carregar_macros_na_lista_visual(self) -> None:
        self.lista_visual_macros.clear()
        macros = self.ler_configuracoes().get("macros", [])
        filtro = self.input_busca.text().strip().lower()

        for idx, macro in enumerate(macros):
            nome = macro.get("nome", "Sem nome")
            combo = macro.get("combo", [])
            comando = macro.get("comando", "")
            
            if filtro and filtro not in f"{nome} {comando} {' '.join(combo)}".lower():
                continue

            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setText(f"{nome} ({macro.get('cooldown', 0.4):.2f}s)\n➔ {self.formato_combo(combo)}")
            item.setToolTip(f"Comando: {comando}")
            self.lista_visual_macros.addItem(item)

    def aplicar_filtro_lista(self) -> None:
        self.carregar_macros_na_lista_visual()

    def ao_clicar_para_editar(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        macros = self.ler_configuracoes().get("macros", [])

        if 0 <= idx < len(macros):
            macro = macros[idx]
            self.macro_editando_index = idx
            self.input_nome.setText(macro.get("nome", ""))
            self.input_comando.setText(macro.get("comando", ""))
            self.input_cooldown.setValue(macro.get("cooldown", 0.4))
            self.combo_atual = list(macro.get("combo", []))
            self.label_combo_visual.setText(f"Combo carregado: {self.formato_combo(self.combo_atual)}")
            
            self.botao_salvar.setText("Atualizar macro")
            self.botao_salvar.setStyleSheet("background-color: #FAB387; color: #11111B; font-weight: bold;")
            self.botao_limpar_selecao.setVisible(True)

    def resetar_modo_criacao(self) -> None:
        self.input_nome.clear()
        self.input_comando.clear()
        self.input_cooldown.setValue(0.40)
        self.combo_atual.clear()
        self.macro_editando_index = None
        self.gravando = False
        self.label_combo_visual.setText("Combo atual: (clique em ‘Gravar combo’)")
        self.lista_visual_macros.clearSelection()

        self.botao_salvar.setText("Salvar macro")
        self.botao_salvar.setStyleSheet("background-color: #89B4FA; color: #11111B; font-weight: bold;")
        self.botao_limpar_selecao.setVisible(False)
        self.botao_gravar.setText("Gravar combo")
        self.botao_gravar.setStyleSheet("background-color: #A6E3A1; color: #11111B; font-weight: bold;")

    def ao_salvar_macro(self) -> None:
        nome, comando = self.input_nome.text().strip(), self.input_comando.text().strip()
        
        if not nome or not self.combo_atual or not comando:
            QMessageBox.warning(self, "Aviso", "Preencha todos os campos antes de salvar.")
            return

        dados = self.ler_configuracoes()
        nova_macro = {
            "nome": nome, "combo": self.combo_atual, 
            "comando": comando, "cooldown": round(self.input_cooldown.value(), 2)
        }

        if self.macro_editando_index is not None:
            dados["macros"][self.macro_editando_index] = nova_macro
        else:
            dados.setdefault("macros", []).append(nova_macro)

        if hasattr(self, "thread_gamepad") and self.thread_gamepad.device_path:
            dados["gamepad_path"] = self.thread_gamepad.device_path

        self.salvar_configuracoes(dados)
        self.resetar_modo_criacao()
        self.carregar_macros_na_lista_visual()

    def ao_deletar_macro(self) -> None:
        item = self.lista_visual_macros.currentItem()
        if not item: return

        idx = item.data(Qt.ItemDataRole.UserRole)
        dados = self.ler_configuracoes()

        if 0 <= idx < len(dados.get("macros", [])):
            res = QMessageBox.question(self, "Confirmar", "Deletar esta macro?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.Yes:
                self.resetar_modo_criacao()
                dados["macros"].pop(idx)
                self.salvar_configuracoes(dados)
                self.carregar_macros_na_lista_visual()

    def iniciar_thread(self) -> None:
        self.thread_gamepad = GamepadListener()
        self.thread_gamepad.botao_pressionado.connect(self.receber_input_controle)
        self.thread_gamepad.status_conexao.connect(self.atualizar_status_conexao)
        self.thread_gamepad.start()

    def atualizar_lista_controles(self) -> None:
        self.combo_controles.blockSignals(True)
        self.combo_controles.clear()
        self.combo_controles.addItem("Selecione um dispositivo...", None)

        for path in list_devices():
            try:
                dev = InputDevice(path)
                caps = dev.capabilities().get(ecodes.EV_KEY, [])
                if ecodes.BTN_GAMEPAD in caps or "gamepad" in dev.name.lower():
                    self.combo_controles.addItem(f"{dev.name} ({path})", path)
            except Exception: pass

        self.combo_controles.blockSignals(False)

    def ao_selecionar_controle(self, index: int) -> None:
        if hasattr(self, "thread_gamepad"):
            self.thread_gamepad.alterar_dispositivo(self.combo_controles.itemData(index))

    def atualizar_status_conexao(self, texto: str) -> None:
        self.label_status.setText(f"Status: {texto}")
        self.label_status.setObjectName("status_ok" if "Escutando" in texto else "status_bad")
        self.label_status.style().unpolish(self.label_status)
        self.label_status.style().polish(self.label_status)

    def alternar_gravacao(self) -> None:
        self.gravando = not self.gravando
        if self.gravando:
            self.combo_atual.clear()
            self.label_combo_visual.setText("Combo: [gravando...]")
            self.botao_gravar.setText("Parar gravação")
            self.botao_gravar.setStyleSheet("background-color: #F38BA8; color: #11111B; font-weight: bold;")
        else:
            self.botao_gravar.setText("Gravar combo")
            self.botao_gravar.setStyleSheet("background-color: #A6E3A1; color: #11111B; font-weight: bold;")
            self.label_combo_visual.setText(f"Combo: {self.formato_combo(self.combo_atual)}" if self.combo_atual else "Combo atual: vazio")

    def receber_input_controle(self, nome_botao: str) -> None:
        if self.gravando and nome_botao not in self.combo_atual:
            self.combo_atual.append(nome_botao)
            self.label_combo_visual.setText(f"Combo: {self.formato_combo(self.combo_atual)}")

    def closeEvent(self, event) -> None:
        if hasattr(self, "thread_gamepad"):
            self.thread_gamepad.rodando = False
            self.thread_gamepad.wait(1500)
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Vincula o ID da janela exatamente ao arquivo 'blaster.desktop'
    app.setDesktopFileName("blaster") 
    
    app.setStyleSheet(ESTILO_DARK)
    
    # Aplica o ícone globalmente em toda a aplicação
    if CAMINHO_ICONE_FINAL.exists():
        app.setWindowIcon(QIcon(str(CAMINHO_ICONE_FINAL)))

    janela = BlasterApp()
    janela.show()
    sys.exit(app.exec())
