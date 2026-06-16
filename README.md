# Blaster - Gamepad Macro Generator (Beta 0.2)

O **Blaster** é um protótipo conceitual e aberto de um motor de macros em segundo plano para gamepads e controles de videogame. Ele foi desenvolvido no Linux Mint, mas funciona perfeitamente em qualquer distribuição baseada em Debian/Ubuntu. 

Este projeto foi construído para servir de norte para quem deseja automatizar comandos do sistema operacional usando os botões do controle.

---

## 🎮 Como Funciona

Ao abrir o programa pela primeira vez, o motor (daemon) não funcionará em segundo plano corretamente. É necessário que, após a primeira execução do programa, o usuário **reinicie o sistema**. Após a reinicialização, aparecerá a seguinte mensagem na janela do gerenciador: **"O Blaster Daemon já está configurado para iniciar com o sistema"**. 

Ao abrir o programa e conectar o controle no seu computador, selecione o seu dispositivo em *"Selecione um dispositivo..."*. Caso ele não apareça de imediato, clique em *"Atualizar lista"*. Se tudo der certo, o programa mostrará em verde: **"Status: Escutando: [nome do seu controle]"**. Caso contrário, ele mostrará em vermelho: **"Status: Nenhum controle selecionado"**.

### Painel Esquerdo (Gerenciamento)
No lado **esquerdo** do gerenciador, você tem todas as suas macros criadas. Ali você pode:
* Buscar uma macro pelo nome.
* Clicar em uma macro existente para editá-la.
* Deletar a macro selecionada.

### Painel Direito (Editor)
No lado **direito** do gerenciador, ficam as configurações da macro. Sem nenhuma macro selecionada na lista esquerda, você estará criando uma macro nova. Nesse setor você pode:
* Nomear ou editar o nome da macro.
* Gravar um combo de botões.
* Definir o cooldown (tempo de espera entre execuções).
* Definir o comando do terminal.

> 💡 **Como gravar o combo:** Ao clicar em **"Gravar Combo"** (o botão verde) e tendo o gamepad selecionado, o Blaster passa a ler todos os botões que você apertar em sequência. Para encerrar a leitura, basta clicar em **"Parar Gravação"** (o botão vermelho).

Com o combo definido, basta relacioná-lo a qualquer comando do terminal do seu Linux!

---

## 📺 Exemplo de Uso

Vamos imaginar um cenário: você está sentado no sofá com seu computador ligado na TV e quer abrir o *Pegasus Frontend* para acessar seus jogos sem precisar levantar para usar o teclado ou o mouse. No Blaster, você define previamente:
* **Nome da Macro:** "Abrir o Pegasus"
* **Combo:** `Select` + `RB` + `B` (ou `Select` + `R1` + `Círculo`) — *Recomendamos fortemente combos de 3 botões para evitar disparos acidentais.*
* **Comando do terminal:** `flatpak run org.pegasus_frontend.Pegasus`

Após definir os campos, você pode salvar a macro nova (botão azul) ou, se estiver editando, clicar em "Atualizar macro" (botão laranja). Caso desista da alteração, basta clicar em "Cancelar edição" para retornar ao modo de criação.

Você pode então fechar o gerenciador. O daemon mantém a leitura das macros em segundo plano de forma extremamente leve, dinâmica e permanente. Isso significa que o daemon sempre detectará suas edições feitas no gerenciador e iniciará sozinho sempre que você ligar o computador. Você configura suas macros uma vez, fecha o Blaster e elas ficam rodando para sempre com aquele gamepad!

---

## 🚀 Como Instalar

O modo mais fácil e direto de testar o Blaster em distros baseadas em Debian/Ubuntu:

1. Vá até a aba [Releases](https://github.com/MrDeltaMan/Blaster/releases) do projeto.
2. Baixe o pacote `.deb` mais recente.
3. Instale dando dois cliques no arquivo (pela interface gráfica) ou utilize o terminal executando:
   ```bash
   sudo apt install ./blaster-macro-manager_*.deb

---

## 🛠️ Código Aberto e Modificações

Por ser um protótipo Beta, após instalado via `.deb`, os códigos ficam com permissão total de edição na pasta `/opt/Blaster/`. Sinta-se totalmente livre para criar Forks, fazer modificações, enviar melhorias ou abrir Issues com sugestões!

