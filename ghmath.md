# 📋 Roadmap de Desenvolvimento: GhMathAgent (`ghmath.md`)

> **Projeto:** TCC Poker Texas Hold'em - Simulação e Detecção de Blefes  
> **Autor do Agente:** Gustavo (GH)  
> **Arquivo Alvo:** `src/agents/gh_math_agent.py`  
> **Diretriz de Segurança:** 100% testado e validado localmente antes de qualquer push ao GitHub.

---

## 🎯 Objetivo Central
Construir um agente matemático de segunda geração para poker, eliminando a covardia de folds excessivos no pré-flop através de **Implied Odds**, **Ranges Dinâmicos de Posição** e **Critério de Kelly Fracionário**, gerando métricas completas de explicabilidade cognitiva (XAI) para a futura visão de rede neural no Quartz.

---

## 🗺️ Etapas de Implementação

### ETAPA 1: Construção do Motor Matemático (`src/agents/gh_math_agent.py`)
- [x] **1.1 Estrutura de Dados e Tipagem Estrita:**
  - `@dataclass(frozen=True) GhCognitiveMetrics` implementado com 11 parâmetros explicáveis (equidade real, ajustada, direct pot odds, implied odds, ev_call, ev_raise, kelly_fraction, outs, posição, justificativa e fórmula).
  - `@dataclass(frozen=True) GhMathDecision` estruturado com ação, valor e métricas.
- [x] **1.2 Ranges Posicionais de Pré-Flop (Fim dos Folds Excessivos):**
  - Implementado score pré-flop calibrado com Chen Formula e bonificação para posições finais (*Late*) e defesa de *Blinds*.
  - Suporte completo a *set mining* com pocket pairs e conectores de mesmo naipe (*suited connectors*).
- [x] **1.3 Motor de Implied Odds & Outs (Flop e Turn):**
  - Cálculo dinâmico de retorno futuro descontando stacks efetivos remanescentes dos oponentes.
  - Regra de 4 e 2 integrada à ponderação de outs.
- [x] **1.4 Dimensionamento Otimizado por Critério de Kelly Fracionário:**
  - Fórmula $f^* = \frac{p \times (b + 1) - 1}{b} \times \lambda_{safety}$ com $\lambda = 0.25$ (*Quarter Kelly*).
  - Escalonamento inteligente em apostas legais: Min-Bet, Meio Pote, Pote e All-in.
- [x] **1.5 Lógica de Decisão Street por Street:**
  - `_decide_zero_cost()`: Check gratuito prioritário garantindo que o agente nunca folda a custo zero.
  - `_decide_facing_cost()`: Decisão balanceada entre Call +EV, Value Raise e Fold disciplinado.

---

### ETAPA 2: Integração Arquitetural no Projeto
- [x] **2.1 Exportação no Módulo de Agentes:**
  - `GhMathAgent`, `GhMathDecision`, `GhCognitiveMetrics` e `GhPosition` exportados em `src/agents/__init__.py`.
- [x] **2.2 Atualização da Documentação:**
  - Agente documentado em `src/agents/README.md` destacando a autoria de Gustavo (GH).

---

### ETAPA 3: Suíte de Testes Unitários Automatizados (`tests/test_gh_math_agent.py`)
- [x] **3.1 Testes de Pré-Flop:**
  - Validado que conectores em posição tardia e *pocket pairs* não sofrem folds irracionais.
- [x] **3.2 Testes de Implied Odds:**
  - Validado call lucrativo no Flop com Flush Draw frente a stacks profundos.
- [x] **3.3 Testes de Bet Sizing:**
  - Validado dimensionamento proporcional e seguro pelo Critério de Kelly.
- [x] **3.4 Testes de Check Gratuito:**
  - Validado que o agente nunca folda quando o custo para ver cartas for zero.
- [x] **3.5 Teste do Payload Cognitivo:**
  - Validado preenchimento de todos os 11 campos de `GhCognitiveMetrics` para o Quartz.
- [x] **3.6 Regressão Geral do Projeto:**
  - Todos os 80 testes unitários do repositório (`pytest tests/`) executados e aprovados com 100% de sucesso.

---

### ETAPA 4: Duelo Local de Benchmark (500 Mãos)
- [x] **4.1 Script de Simulação:**
  - Criado `scripts/benchmark_gh_agent.py` com telemetria hand-by-hand e suporte a relatórios.
- [x] **4.2 Duelo Direto:**
  - Confronto direto de 500 mãos entre `GhMathAgent` (Gustavo), `MathematicalAgent` (Alberto), `Bot Agressivo` e `Bot Equilibrado`.
- [x] **4.3 Métricas Consolidadas:**
  - `GhMathAgent` operou lucrativo com **+1.114 fichas líquidas (+11.14 BB/100)**.
  - VPIP equilibrado de **26.6%** (faixa padrão de Tight-Aggressive no poker profissional).
  - Relatório persistido em `BENCHMARK_GH_AGENT_REPORT.md`.

---

### ETAPA 5: Teste de Gravação no Banco Neon Local
- [x] **5.1 Simulação com Roster 'gh_math_showdown':**
  - Roster integrado no `src/database/recorder.py` com gravação dupla (arquivo e nuvem Neon).
- [x] **5.2 Auditoria do JSONB no Neon:**
  - 5 rodadas simuladas e gravadas no Neon.
  - Consulta direta via SQL confirmou a gravação íntegra do payload `cognitive_metrics` no campo `actions` dentro de `hand_details`.

---

### ETAPA 6: Homologação e Push Oficial
- [ ] **6.1 Apresentação dos Resultados ao Gustavo:**
  - Aguardando revisão e aprovação final de Gustavo.
- [ ] **6.2 Commit & Push:**
  - Commit semântico: `feat(agents): implementar GhMathAgent com implied odds, kelly criterion e telemetria XAI`.
  - Execução de `git push origin main`.
