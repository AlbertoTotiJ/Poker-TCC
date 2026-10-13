# Módulo de Agentes de IA - Poker Bot

Este diretório contém a modelagem, a lógica de tomada de decisão e o pipeline de execução individual dos agentes autônomos de Poker desenvolvidos para o Trabalho de Conclusão de Curso (TCC).

O foco deste módulo é isolar os algoritmos de decisão para que cada agente possua independência arquitetural, permitindo treinamento, testes de desempenho e calibrações fora do ecossistema principal da aplicação.

---

## Estrutura do Módulo

Cada agente possui um arquivo de execução isolado contendo suas próprias heurísticas, cálculos e/ou modelos de aprendizado:

```text
src/agents/
│
├── mathematical_agent.py   # Agente Matemático (Totalmente probabilístico e analítico)
├── bluffer_agent.py        # Agente Blefador (Planejado / Em backlog)
├── hybrid_agent.py         # Agente Híbrido (Integração lógico-comportamental)
└── README.md               # Documentação técnica do módulo
```

---

## Especificação dos Agentes

### 1. Agente Matemático (`mathematical_agent.py`)

Agente projetado com base estrita na teoria das probabilidades e análise combinatória.

* **Comportamento:** Individualista e determinístico em relação ao estado das cartas. Ignora histórico, perfil ou tendências dos oponentes na mesa.  
* **Mecânica de Decisão:**  
  * Analisa estritamente a força relativa da sua mão atual (*hole cards*) combinada às cartas comunitárias (*board*).  
  * Calcula a equidade (*hand strength*) e probabilidades de evolução (*draws* no Flop e Turn) frente ao baralho restante.  
  * Decide ações (Fold, Check, Call, Raise) fundamentado no valor esperado (EV) e relação de retorno matemático, sem interferência de vieses psicológicos ou táticas de engano.

### 2. Agente Blefador (`bluffer_agent.py`)

Agente focado em exploração de mesa, variações de apostas e dinâmicas de pressão psicológica.

* **Status Atual:** **Implementado e Integrado**.  
* **Mecânica de Decisão:**  
  * Avalia a textura do bordo identificando mesas secas (*dry boards*) e cartas intimidatórias (*scare cards* como Áses e Reis no Turn/River).  
  * Estima *Fold Equity* com base no número de oponentes ativos e nos custos de aposta.  
  * Executa roubos de potes órfãos (*C-Bet Steals*), re-aumentos desbalanceados (*Bluff Raises*) e blefes puros quando os adversários demonstram passividade ou fraqueza.

### 3. Agente Híbrido (`hybrid_agent.py`)

Agente balanceado que unifica o rigor probabilístico do Agente Matemático com os padrões táticos do Agente Blefador.

* **Status Atual:** **Implementado e Integrado**.  
* **Comportamento:** Utiliza o piso probabilístico (Monte Carlo e Pot Odds) para evitar jogadas matematicamente inviáveis a longo prazo, alternando entre linhas de valor (*value bets*), semi-blefes em *draws* de sequência e flush, blefes oportunistas em mesas passivas e desaceleração tática (*slow-play traps*) quando possui mãos dominantes.

---

## Desenvolvimento e Execução Isolada

Todos os scripts são construídos para funcionar tanto de forma desacoplada quanto integrados à engine principal da partida:

1. **Testes Unitários e Validação:** É possível instanciar qualquer agente passando estados simulados de mesa (mão privada, cartas do flop/turn/river, pot e aposta mínima) diretamente no `__main__` de cada arquivo.  
2. **Treinamento Individual:** Ajustes de hiperparâmetros, pesos de decisão ou rotinas de simulação Monte Carlo podem ser executados isoladamente sem a necessidade de subir todo o ecossistema do projeto ou containers adicionais.
