# 📐 Especificação e Arquitetura: Agente Matemático GH (`GhMathAgent`)

> **Autor:** Gustavo (GH)  
> **Status:** ⏳ **Aguardando Aprovação Final para Codificação**  
> **Módulo:** `src/agents/gh_math_agent.py`  
> **Classe Principal:** `GhMathAgent`  
> **Coexistência:** Preserva integralmente os agentes criados pelo Alberto (`mathematical_agent.py`, `bluffer_agent.py`, `hybrid_agent.py`), permitindo benchmarks comparativos diretos no TCC.

---

## 1. Motivação e Resolução do Problema do Alberto

### 1.1 O Problema do Bot do Alberto (Folds Irreais no Pré-Flop)
O agente do Alberto calcula a equidade pré-flop simulando a mão do herói contra **todos os oponentes da mesa simultaneamente** como mãos aleatórias (*multi-way raw equity*).
* Em uma mesa de 6 ou 9 jogadores, a equidade média de qualquer mão cai para $15\% - 25\%$.
* Como o custo de pagar um aumento (*Pot Odds*) costuma exigir entre $30\% - 40\%$, a condição `Equity >= PotOdds` quase nunca é satisfeita.
* **Resultado:** O bot do Alberto desiste (*fold*) em cerca de 80% a 90% das mãos logo na primeira rodada, gerando um comportamento passivo, irreal e entediante.

### 1.2 Como o `GhMathAgent` Resolve Isso
O agente GH introduz três conceitos profissionais que corrigem o pré-flop:
1. **Realização de Equidade e Implied Odds:** Mãos especulativas (pares médios, conectores de mesmo naipe como 98s, JTs) têm custo baixo para ver o flop em relação aos stacks restantes. Se o stack efetivo for $\ge 8\times$ o valor do call, o call é lucrativo a longo prazo.
2. **Defesa de Blinds & Posição:** No Button, Cutoff e Big Blind, o agente defende seu investimento com ranges dinâmicos de abertura e defesa (RFI - Raise First In), jogando com 25% a 40% das mãos conforme a posição.
3. **Isolamento de Confronto:** Ao enfrentar um agressor, calcula a equidade relativa focada no range plausível do agressor, e não na mesa inteira.

---

## 2. Matriz Comparativa: Alberto vs. Gustavo (GH)

| Dimensão Matemática | Agente do Alberto (`MathematicalAgent`) | Agente do Gustavo (`GhMathAgent`) | Impacto no Jogo e TCC |
| :--- | :--- | :--- | :--- |
| **Comportamento Pré-Flop** | Folds constantes e irreais (~85% folds). | **Ranges Dinâmicos de Posição & Implied Odds.** | Jogo fluido, realista e competitivo no pré-flop. |
| **Modelagem de Oponentes** | Oponentes com mãos 100% aleatórias. | **Ranges Perceptuais:** Infere força baseada no tipo de aposta do adversário. | Equidade calculada com rigor estatístico superior. |
| **Cálculo de Odds** | Apenas *Direct Pot Odds*. | **Direct Pot Odds + Implied Odds Dinâmicas.** | Permite pagar pedidas (*draws*) lucrativas no Flop/Turn. |
| **Dimensionamento de Aposta** | Sizing estático e fixo em 75% do pote. | **Critério de Kelly Fracionário & Geometric Sizing.** | Aumentos proporcionais à vantagem matemática ($EV$). |
| **Consciência Posicional** | Nenhuma (trata Button igual a UTG). | **Positional Awareness Modifiers.** | Mais agressivo em posição tardia, cauteloso fora de posição. |
| **Explicabilidade (XAI)** | Retorna apenas valores numéricos básicos. | **Payload Cognitivo Estruturado (Rede Neural).** | Alimenta perfeitamente a Visão Micro no Quartz. |

---

## 3. Roteiro de Como Explicar o Agente a Terceiros (Pitch do TCC)

Para explicar o `GhMathAgent` para seu orientador, banca ou colegas:

> *"O GhMathAgent é um tomador de decisão probabilístico que opera como um gestor de risco financeiro no poker. Em vez de jogar por intuição ou decorar jogadas, a cada rodada ele calcula três pilares matemáticos:*
> 1. *A **Equidade Real**: qual a chance percentual exata da mão dele vencer até o final.*
> 2. *As **Pot Odds e Implied Odds**: se o preço cobrado na aposta vale a pena em relação ao dinheiro que já está no pote e ao dinheiro que ainda podemos ganhar dos adversários.*
> 3. *O **Critério de Kelly**: quando ele tem vantagem matemática comprovada, ele usa a fórmula de Kelly para calcular a fração exata do pote a apostar, maximizando o lucro e minimizando a variância.*
> 
> *A grande evolução em relação aos modelos baseline é que o GhMathAgent entende o valor da posição na mesa e das fichas futuras, eliminando os folds excessivos e jogando com agressividade calculada."*

---

## 4. Estrutura de Código (`src/agents/gh_math_agent.py`)

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from src.agents.base import BaseAgent
from src.engine.deck import Card
from src.engine.table import Action, ActionType, Street, Table

@dataclass(frozen=True)
class GhCognitiveMetrics:
    """Métricas explicáveis para a Visão Micro da Rede Neural."""
    raw_equity: float
    adjusted_equity: float
    direct_pot_odds: float
    implied_odds: float
    expected_value_call: float
    expected_value_raise: float
    kelly_fraction: float
    outs_count: int
    position_name: str
    tactical_rationale: str
    formula_reference: str

@dataclass(frozen=True)
class GhMathDecision:
    action_type: ActionType
    amount: int
    metrics: GhCognitiveMetrics

class GhMathAgent(BaseAgent):
    """Agente Matemático com Implied Odds, Critério de Kelly e Ranges Posicionais."""
    ...
```

---

## 5. Roteiro de Teste Local (Sem Push Prematuro)

1. **Implementação:** Criação de `src/agents/gh_math_agent.py`.
2. **Testes Unitários:** `tests/test_gh_math_agent.py` testando cenários de pré-flop, implied odds e sizing.
3. **Duelo de Validação (1.000 mãos):** `scripts/benchmark_gh_vs_alberto.py` colocando `GhMathAgent` contra `MathematicalAgent` (Alberto) para comprovar superioridade em $BB/100$ e eliminação dos folds irreais.
4. **Apresentação:** Relatório exibido para você aprovar antes de qualquer commit ou push.
