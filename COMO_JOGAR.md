# 🃏 Guia Rápido: Como Jogar o Texas Hold'em (Poker-TCC)

Este mini guia orienta qualquer usuário ou desenvolvedor a executar e jogar o simulador de Texas Hold'em contra a máquina, seja pela **interface gráfica na web (navegador)** ou pelo **terminal (console back-end)**.

---

## 🚀 1. Modos de Jogo

Você tem duas formas de jogar:

| Modo | Comando de Execução | Descrição |
| :--- | :--- | :--- |
| **🌐 Mesa Gráfica Web** *(Recomendado)* | `python scripts/play_poker_web.py` | Abre uma página interativa no navegador com mesa de feltro verde, distribuição de cartas, fichas e controles visuais. |
| **💻 Console Back-end (CLI)** | `python scripts/play_poker.py` | Roda diretamente no terminal com telemetria detalhada, naipes coloridos e prompts numéricos. |

---

## 🌐 2. Como Jogar na Interface Web (Navegador)

### Passo a Passo:
1. Abra o terminal na raiz do projeto e execute:
   ```bash
   python scripts/play_poker_web.py
   ```
2. O servidor iniciará e abrirá automaticamente a página no seu navegador padrão no endereço:
   👉 **`http://127.0.0.1:5000`**

### Recursos da Mesa Virtual:
- **Escolha de Jogadores (2 a 9):** No modal inicial ou clicando em **"⚙️ Configurar Mesa"**, escolha quantos participantes estarão na mesa (ex: *2 para Heads-up 1v1*, *6 para 6-Max*, ou até *9 para mesa cheia*).
- **Seu Lugar na Mesa:** Você (*Humano*) fica sempre posicionado na cabeceira inferior central da mesa, com visão em primeira pessoa das suas cartas abertas.
- **Máquinas/Bots:** Ficam distribuídos ao redor da mesa com cartas viradas para baixo e perfis táticos identificados (*Agressivo*, *Conservador* ou *Equilibrado*).
- **Controles de Ação:** Quando for sua vez (sinalizada por um anel dourado pulsante), os botões da barra inferior se habilitam:
  - **FOLD (Desistir):** Larga a mão.
  - **CHECK (Passar) / CALL (Pagar):** Passa a vez sem apostar ou cobre a aposta atual.
  - **BET / RAISE:** Permite apostar ou aumentar usando o controle deslizante ou os atalhos rápidos (`Mín`, `1/2 Pote`, `Pote`, `All-in`).
  - **ALL-IN:** Empurra todas as suas fichas para o pote.
- **Showdown:** No final da rodada, todas as cartas dos adversários são viradas para cima e a combinação vencedora é anunciada em português.
- **Velocidade:** Alterne a velocidade das jogadas dos bots entre *Normal*, *Rápido* ou *Instantâneo* no botão do topo.

---

## 💻 3. Como Jogar no Terminal (Modo Console)

Se preferir jogar sem abrir o navegador, execute:

```bash
python scripts/play_poker.py
```

1. O jogo perguntará:
   ```text
   Quantos jogadores na mesa (2 a 9)? [Padrão: 4]:
   ```
2. Digite a quantidade desejada (ex: `4`) e pressione `Enter`.
3. A cada rodada, o terminal renderizará o estado do bordo, os potes, seus adversários e um menu de ações numeradas:
   ```text
   SUA VEZ DE AGIR! Escolha uma opção:
     [1] Desistir (FOLD)
     [2] Pagar aposta (20 fichas) (CALL)
     [3] Aumentar (RAISE) [Mín: 40, Máx: 1000]
   Digite sua opção (1-3): 
   ```
4. Digite o número da sua escolha e confirme.

---

## ⚙️ 4. Parâmetros e Opções Avançadas

Você pode passar parâmetros diretamente na linha de comando:

```bash
# Iniciar a mesa web com 6 jogadores e 2000 fichas:
python scripts/play_poker_web.py --players 6 --stack 2000

# Executar a mesa no terminal com blinds personalizados (SB: 25, BB: 50):
python scripts/play_poker.py --players 3 --sb 25 --bb 50

# Execução automática simulada (útil para testes sem intervenção humana):
python scripts/play_poker.py --players 4 --hands 5 --auto
```

---

## 🧪 5. Verificação e Testes

Para garantir que todo o motor de regras, avaliador de mãos e servidores estão íntegros:

```bash
# Execução da suíte completa de 41 testes unitários:
pytest -v

# Validação de formatação e padrões Clean Code (Flake8 e Black):
flake8 src/ tests/ scripts/
black --check src/ tests/ scripts/
```
