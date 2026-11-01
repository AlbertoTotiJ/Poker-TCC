# 🎭 Especificação e Arquitetura: Agente Blefador GH (`GhBlufferAgent`)
## Engenharia de Blefes Inexploráveis baseada em Teoria dos Jogos (Libratus & Pluribus)

> **Autor:** Gustavo (GH)  
> **Status:** 🚀 **Em Desenvolvimento Ativo (Local)**  
> **Módulo:** `src/agents/gh_bluffer_agent.py`  
> **Classe Principal:** `GhBlufferAgent`  
> **Coexistência:** Preserva integralmente o agente criado pelo Alberto (`bluffer_agent.py`), permitindo benchmarks comparativos diretos no TCC.

---

## 1. Motivação e Resolução das Falhas do Agente do Alberto

### 1.1 As 3 Falhas Críticas do Bot do Alberto (`bluffer_agent.py`)
1. **Blefes Desbalanceados por Probabilidade Cega:**
   O agente do Alberto blefa rodando um dado aleatório (`roll < 0.40 * (fold_equity / 0.50)`). Isso não respeita nenhuma proporção matemática em relação às apostas por valor, tornando o agente facilmente explorável por oponentes atentos.
2. **"Calling Station" Disfarçado (Sangria de Fichas):**
   Na linha 573 de `bluffer_agent.py`, o bot executa a instrução `roll < 0.60` para dar `CALL` em apostas adversárias. Ele paga 60% das vezes sem *Pot Odds* nem equidade mínima, sangrando o bankroll até a eliminação.
3. **Ausência do Efeito de Remoção de Cartas (*Blockers*):**
   No poker profissional e nos sistemas de ponta (Libratus e Pluribus), blefa-se com cartas que **bloqueiam as melhores mãos do adversário** (ex: segurar o Ás do naipe do flush ou bloquear sequências). O bot do Alberto blefa com "qualquer mão fraca", maximizando o risco de trombar com o monstro do adversário.
4. **Dimensionamento Rígido de 40% do Pote:**
   O bot do Alberto aposta sempre 40% do pote (`bet_sizing_factor = 0.40`). Esse valor oferece pot odds muito favoráveis para o adversário pagar (apenas 22%), destruindo a *Fold Equity* real do blefe.

### 1.2 Como o `GhBlufferAgent` Resolve Isso
1. **Proporção Áurea de Nash entre Valor e Blefe (*GTO Bluff-to-Value Ratio*):**
   A cada aposta $B$ em um pote $P$, o agente calcula a frequência exata de indiferença de Nash:
   $$\text{Frequência de Blefe} = \frac{B}{P + 2B}$$
   Assim, o oponente fica matematicamente indiferente entre dar call ou fold, tornando o blefe inexplorável a longo prazo.
2. **Motor de Pontuação de Bloqueadores (*Blocker Scoring Engine*):**
   Calcula se as cartas privadas do herói removem combos do topo do range do adversário (Nut Flush Blockers, Straight Blockers e Top Pair Blockers). Se a mão não tem blockers relevantes, o agente prefere dar Check ou Fold prudente.
3. **Semi-Blefes com Retenção de Equidade (Flop e Turn):**
   Prioriza apostas e aumentos quando possui cartas com plano B (Flush Draw, Straight Draw, Overcards). Se o adversário pagar, o agente ainda pode acertar a carta vencedora e levar um pote gigante.
4. **Eliminação do Call Passivo:**
   Substitui a rolagem cega de 60% por uma rigorosa validação matemática de Pot Odds e Implied Odds. Não joga fichas fora sem justificativa probabilística.
5. **Dimensionamento Polarizado no River:**
   Em blefes no river, aposta entre 75% e 100% do pote, maximizando a pressão psicológica e estatística sobre mãos médias do oponente.

---

## 2. Matriz Comparativa: Alberto (`BlufferAgent`) vs. Gustavo (`GhBlufferAgent`)

| Dimensão Estratégica | Agente do Alberto (`BlufferAgent`) | Agente do Gustavo (`GhBlufferAgent`) | Impacto no Jogo e TCC |
| :--- | :--- | :--- | :--- |
| **Gatilho de Blefe** | Aleatório fixo (`roll < 0.40`). | **Razão Áurea GTO ($B / (P + 2B)$) ponderada por Blockers.** | Inexplorabilidade teórica fundamentada em Nash. |
| **Seleção de Cartas** | Qualquer mão fraca sem critério combinatório. | **Prioridade para Semi-Blefes com Outs e Nut Blockers.** | Maximiza a chance de fold e mantém plano B de vitória. |
| **Defesa contra Apostas** | Paga em 60% das vezes às cegas (`roll < 0.60`). | **Call apenas com Pot Odds + Implied Odds; caso contrário Fold.** | Elimina a sangria crônica de fichas (calling station). |
| **Efeito de Remoção (Blockers)** | Inexistente (ignora impacto no range do vilão). | **Detecção ativa de Nut Flush / Straight / Top Pair Blockers.** | Aplicação direta dos princípios do Pluribus/Libratus. |
| **Dimensionamento do Blefe** | Fixo em 40% do pote (pot odds baratas pro vilão). | **Polarizado (75% a 100% no River; 33% a 66% no Flop).** | Gera Fold Equity real forçando decisões difíceis. |
| **Multiway Pots (3+ Jogadores)** | Blefa quase igualmente em multiway. | **Penalidade severa: desativa blefes puros no River multiway.** | Evita suicídio em potes disputados por vários jogadores. |
| **Explicabilidade (XAI)** | Telemetria básica de contadores. | **Payload Cognitivo Completo (`GhBluffMetrics`).** | Rastreabilidade perfeita das decisões para a banca do TCC. |

---

## 3. Roteiro de Como Explicar o Agente a Terceiros (Pitch do TCC)

Para explicar o `GhBlufferAgent` para o orientador, banca ou colegas:

> *"O GhBlufferAgent é um agente de poker inspirado na arquitetura de tomada de decisão do Libratus e Pluribus. Ele desmistifica a ideia de que o blefe é um ato aleatório ou de pura sorte.
> 
> Ele opera sobre três alicerces matemáticos:
> 1. **A Proporção Áurea de Indiferença de Nash:** Para cada tamanho de aposta, ele calcula exatamente quantos blefes deve ter no seu range em relação às apostas por valor ($B / (P + 2B)$). Isso faz com que o adversário fique matematicamente indiferente entre pagar ou desistir.
> 2. **O Efeito de Remoção de Cartas (Blockers):** Ele não blefa com qualquer mão ruim. No River, ele seleciona preferencialmente mãos que possuem cartas-chave (como o Ás do naipe do flush), impedindo que o oponente tenha a melhor mão possível.
> 3. **Semi-Blefes com Retenção de Equidade:** No Flop e Turn, ele blefa pesado quando possui pedidas de sequência ou flush. Se o oponente pagar, o agente ainda tem alta probabilidade de virar o jogo na rodada seguinte.
> 
> Enquanto o agente de referência do projeto sangrava fichas pagando apostas sem critério e blefando em frequências desbalanceadas, o GhBlufferAgent atua com agressividade cirúrgica, protegendo o bankroll e maximizando o EV."*

---

## 4. Estrutura de Código (`src/agents/gh_bluffer_agent.py`)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence, Tuple
from src.agents.base import BaseAgent
from src.engine.deck import Card
from src.engine.table import Action, ActionType, Street, Table

class GhBluffTactic(str, Enum):
    POLARIZED_RIVER_BLUFF = "Polarized River Bluff (GTO Blocker)"
    NUT_BLOCKER_BLUFF = "Nut Blocker Bluff"
    SEMI_BLUFF_DRAW = "Semi-Bluff Draw (Outs Pressure)"
    CBET_STEAL = "C-Bet Steal (Dry Board Float)"
    PREFLOP_3BET_BLUFF = "Preflop Polarized 3-Bet Bluff"
    VALUE_PLAY = "Value Play (Range Protection)"
    FREE_CHECK = "Free Check (Pot Control)"
    DISCIPLINED_FOLD = "Disciplined Fold (Anti-Leak)"
    PROBE_DEFEND = "Pot-Odds Defend (Implied Call)"
    CONTINGENCY = "Contingency Fallback"

@dataclass(frozen=True)
class GhBluffMetrics:
    raw_equity: float
    adjusted_equity: float
    pot_odds: float
    gto_bluff_threshold: float
    random_roll: float
    blocker_score: float
    semi_bluff_outs: int
    is_bluff: bool
    tactic: str
    tactical_rationale: str
    formula_reference: str

@dataclass(frozen=True)
class GhBluffDecision:
    action_type: ActionType
    amount: int
    metrics: GhBluffMetrics

class GhBlufferAgent(BaseAgent):
    """Agente Blefador GH com Indiferença GTO, Blockers e Semi-Blefes."""
    ...
```

---

## 5. Roteiro de Validação e Testes Locais

1. **Implementação do Agente:** `src/agents/gh_bluffer_agent.py`.
2. **Atualização de Módulo:** Registro em `src/agents/__init__.py`.
3. **Testes Unitários:** `tests/test_gh_bluffer_agent.py` cobrindo cenários isolados:
   - Check gratuito obrigatório (to_call == 0).
   - Semi-blefe no flop com flush draw / straight draw.
   - Blefe polarizado no river ativado por nut blockers.
   - Fold disciplinado contra apostas pesadas sem blockers e sem odds.
   - 3-Bet de blefe no pré-flop com ases fracos naipados (A5s/A4s).
4. **Benchmark Comparativo:** `scripts/benchmark_gh_bluffer_vs_alberto.py` disputando 500 a 1.000 mãos entre:
   - `GhBlufferAgent` (Gustavo)
   - `BlufferAgent` (Alberto)
   - `MathematicalAgent` (Alberto)
   - `HeuristicAgent` (Agressivo / Equilibrado)
5. **Relatório de Desempenho:** Mensuração de $BB/100$, Win Rate, Net Chips e Frequência Real de Blefe.
