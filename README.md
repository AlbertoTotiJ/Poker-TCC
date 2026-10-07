# Detecção e Análise de Blefes em Agentes Autônomos de Texas Hold'em

Repositório central de desenvolvimento do Trabalho de Conclusão de Curso (TCC). O projeto consiste em um ambiente fechado de simulação de poker na modalidade *Texas Hold'em*, com agentes autônomos baseados em Inteligência Artificial, instrumentação para observabilidade de ações e pipeline estatístico/preditivo para identificação e análise de blefes.

---

## 1. Visão Geral do Projeto

O objetivo principal deste trabalho é construir um ecossistema experimental para simular partidas de Texas Hold'em entre agentes inteligentes e quantificar/detectar padrões de blefe a partir de dados observáveis da partida.

### 1.1 Objetivos Principais
1. **Ambiente Fechado de Simulação:** Implementar a mecânica oficial do Texas Hold'em (rodadas pré-flop, flop, turn e river, gestão de potes, blinds, side pots e showdown).
2. **Agentes Autônomos de IA:** Desenvolver agentes com perfis estratégicos variados (e.g., conservador/tight, agressivo/loose, baseados em heurística ou aprendizado por reforço).
3. **Mecanismo de Telemetria e Observação:** Registrar de forma estruturada as trajetórias completas do jogo (histórico de apostas, tamanho de raises, posições na mesa, cartas comunitárias e cartas privadas reveladas pós-showdown).
4. **Módulo de Análise e Detecção de Blefe:** Extrair métricas comportamentais (frequência de agressão, disparidade entre valor real da mão e padrão de aposta, timing e sizing) e treinar modelos para classificação ou detecção precoce de blefes.
5. **Todas as respostas dos agentes será em PORTUGUÊS.**

---

## 2. Diretrizes Estritas de Codificação (Clean Code)

A manutenção, legibilidade e rigor técnico do código são pilares fundamentais deste projeto. Todas as contribuições devem aderir estritamente às normas abaixo.

### 2.1 Política de Comentários
* **Proibidos comentários triviais e óbvios:** Não explique *o que* a linha de código faz quando a própria sintaxe já torna isso claro.
* **Permitidos apenas comentários de contexto/motivação:** Comentários só devem existir para justificar decisões não triviais (e.g., uma escolha matemática específica, contorno de limitação de regras de poker ou suposições de teoria dos jogos).
* **Código autodocumentável:** A intenção deve ser comunicada por nomes descritivos de funções, métodos e variáveis, nunca por comentários adjacentes.

### 2.2 Estrutura e Modularidade
* **Princípio da Responsabilidade Única (SRP):** Cada função, método ou classe deve resolver exatamente um problema bem delimitado.
* **Funções pequenas e sem efeitos colaterais ocultos:** Prefira funções puras sempre que possível, facilitando a testabilidade.
* **Tipagem Estrita (Type Annotations):** Toda assinatura de função e método deve incluir tipos explícitos para parâmetros e retorno (`typing`).
* **Docstrings:** Use docstrings concisas (padrão Google ou PEP 257) focadas no contrato da função (entradas, saídas e possíveis exceções levantadas), sem redundâncias.

---

## 3. Arquitetura Modular do Repositório

O projeto é organizado em módulos desacoplados para garantir isolamento entre as regras do jogo, a lógica dos agentes e o motor de telemetria/análise:

```text
├── src/
│   ├── engine/             # Regras fundamentais do Texas Hold'em
│   │   ├── deck.py         # Baralho de 52 cartas, naipes, ranques e embaralhamento
│   │   ├── dealer.py       # Dealer oficial, distribuição de hole cards e bordo com queimas
│   │   ├── hand_eval.py    # Avaliador de força e combinações de mãos de 7 cartas
│   │   ├── player.py       # Entidade de jogador, stacks, all-in e volume apostado
│   │   ├── pot.py          # Gestão do pote principal e potes paralelos (side pots)
│   │   └── table.py        # Estado da mesa, posições (dealer, blinds) e transições
│   │
│   ├── agents/             # Implementação dos jogadores autônomos
│   │   ├── base.py         # Interface abstrata padrão para agentes
│   │   ├── heuristic.py    # Agentes baseados em regras/heurísticas de probabilidade
│   │   └── rl/             # Agentes baseados em aprendizado por reforço / Teoria dos Jogos
│   │
│   ├── telemetry/          # Mecanismos de observação e persistência
│   │   ├── tracker.py      # Captura de logs de ações a cada street (pre-flop ao showdown)
│   │   └── schemas.py      # Esquemas estruturados para persistência das partidas
│   │
│   └── analysis/           # Motor de detecção e classificação de blefe
│       ├── features.py     # Engenharia de atributos (agressividade, histórico de apostas)
│       └── detector.py     # Modelos preditivos e classificadores de blefes
│
├── tests/                  # Testes unitários cobrindo engine, agentes e avaliação
├── scripts/                # Scripts utilitários e demonstrações interativas
├── notebooks/              # Análise exploratória e visualização dos dados coletados
├── requirements/           # Dependências de ambiente (base e desenvolvimento)
├── Dockerfile              # Imagem do ambiente de execução
├── docker-compose.yml      # Orquestração do contêiner Docker
└── README.md               # Este documento
```

---

## 4. Metodologia de Detecção de Blefe

No contexto deste projeto, um **blefe** é categorizado e medido através de:
1. **Disparidade Ação-Mão:** Tomada de ação agressiva (aposta/aumento) com equidade de mão baixa (mãos fracas ou especulativas) em relação ao board.
2. **Semi-blefe:** Agressão com mãos fracas no momento, mas com alta equidade futura (draws de flush ou sequência).
3. **Métricas de Agressão do Agente:** Razão entre apostas/aumentos e ações passivas (check/call) ponderada pela força real das cartas em cada rodada (*street*).
4. **Extração de Atributos:** Posição na mesa, relação aposta/pote (*bet sizing*), histórico recente do agente e textura do bordo.

---

## 5. Como Executar

### 5.1 Ambiente Virtual Local

```bash
# Ativação do ambiente virtual
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux / macOS

# Execução da suíte de testes unitários (37 testes)
pytest -v

# Validação de formatação e linter
flake8 src/ tests/ scripts/
black --check src/ tests/ scripts/

# Execução da demonstração dos componentes da Sprint 1
python scripts/demo_sprint1.py

# Jogo interativo contra a máquina no terminal
python scripts/play_poker.py

# Jogo interativo com MESA GRÁFICA VIRTUAL no navegador
python scripts/play_poker_web.py
# (ou alternativamente: python scripts/play_poker.py --web)
```

### 5.2 Execução com Docker

```bash
# Construção e inicialização do contêiner
docker compose up --build

# Execução de testes no contêiner
docker compose run --rm poker pytest -v
```

---

## 6. Roadmap do Projeto

- [x] **Sprint 1: Fundação do Engine, Baralho e Dealer**
  - [x] Baralho padrão de 52 cartas determinístico e queima de cartas (`src/engine/deck.py`).
  - [x] Dealer oficial com regras de distribuição de hole cards e board (`src/engine/dealer.py`).
  - [x] Avaliador de mãos de 7 cartas com desempates precisos por kickers (`src/engine/hand_eval.py`).
  - [x] Gestor de potes e potes paralelos (*side pots*) com all-in (`src/engine/pot.py`).
  - [x] Controlador de mesa, blinds, streets e showdown (`src/engine/table.py` & `src/engine/player.py`).
  - [x] Suíte de 27 testes unitários com 100% de aprovação (`tests/`).
  - [x] Script de demonstração executável (`scripts/demo_sprint1.py`).
- [ ] **Sprint 2: Interface e Agentes Baseline**
  - [ ] Interface de agente com observação parcial (`src/agents/base.py`).
  - [ ] Agentes baseline (`Random`, `Tight-Aggressive`, `Passive`).
- [ ] **Sprint 3: Telemetria e Persistência**
  - [ ] Modelos de dados e schemas (`src/telemetry/schemas.py`).
  - [ ] Rastreador de trajetórias pré-flop ao showdown (`src/telemetry/tracker.py`).
- [ ] **Sprint 4: Detecção e Análise de Blefes**
  - [ ] Engenharia de features de agressão e disparidade (`src/analysis/features.py`).
  - [ ] Modelos classificadores de blefes (`src/analysis/detector.py`).
