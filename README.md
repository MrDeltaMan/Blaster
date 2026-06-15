# Blaster - Gamepad Macro Generator (Beta 0.2)

O **Blaster** é um protótipo conceitual e aberto de um motor de macros em segundo plano para gamepads e controles de videogame no Linux Mint. 

Este projeto foi construído para servir de norte para quem deseja automatizar comandos do sistema operacional usando botões do controle.

## 🚀 Como testar este protótipo

Para clonar e testar o código ou gerar o seu próprio instalador `.deb`:

1. Instale as dependências necessárias no sistema:
   ```bash
   sudo apt install python3 python3-evdev python3-pyqt6

2. Para gerar o pacote instalável a partir desta pasta:
   ```bash
    dpkg-deb --build .

🛠️ Código Aberto

Por ser um protótipo Beta, após instalado via .deb, os códigos ficam com permissão total em /opt/Blaster/. Sinta-se livre para abrir Issues com sugestões ou enviar melhorias!


