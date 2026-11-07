# 03 - Experimentos no Notebook: Mesas de Estresse (1 vs 5)

Este diretório armazena os testes de estresse projetados para avaliar a robustez de cada um dos 3 agentes definitivos colocado em um ecossistema hostil (1 agente isolado contra 5 oponentes de outro perfil ou perfil misto).

---

## 1. Cenários de Estresse Configurados (500 Mãos por Cenário - Seed 101)

### Bloco 1: O Matemático como "1"
- **Cenário 1: 1 Matemático vs 5 Blefadores** (`01_math_vs_5_bluffers`)
  - **Assentos:** `math, bluffer, bluffer, bluffer, bluffer, bluffer`
  - **Objetivo:** Medir se a baseline matemática sobrevive e pune uma mesa inteira de blefadores contínuos.
- **Cenário 2: 1 Matemático vs 5 Híbridos** (`02_math_vs_5_hybrids`)
  - **Assentos:** `math, hybrid, hybrid, hybrid, hybrid, hybrid`
  - **Objetivo:** Testar se o cálculo rígido de odds consegue neutralizar as armadilhas (*slow-plays*) e semi-blefes de múltiplos agentes adaptativos.
- **Cenário 3: 1 Matemático vs 5 Mistos** (`03_math_vs_5_mistos`)
  - **Assentos:** `math, bluffer, bluffer, bluffer, hybrid, hybrid`
  - **Objetivo:** Avaliar o isolamento do matemático contra um ambiente heterogêneo hostil de 3 blefadores e 2 híbridos.

### Bloco 2: O Blefador como "1"
- **Cenário 4: 1 Blefador vs 5 Matemáticos** (`04_bluffer_vs_5_maths`)
  - **Assentos:** `bluffer, math, math, math, math, math`
  - **Objetivo:** Testar a viabilidade da teoria dos jogos e blockers quando 5 oponentes calculam odds friamente e não caem em blefes banais.
- **Cenário 5: 1 Blefador vs 5 Híbridos** (`05_bluffer_vs_5_hybrids`)
  - **Assentos:** `bluffer, hybrid, hybrid, hybrid, hybrid, hybrid`
  - **Objetivo:** Medir a rentabilidade de blefes contra adversários que também sabem blefar e contra-atacar.
- **Cenário 6: 1 Blefador vs 5 Mistos** (`06_bluffer_vs_5_mistos`)
  - **Assentos:** `bluffer, math, math, math, hybrid, hybrid`
  - **Objetivo:** Avaliar o blefador isolado contra 3 matemáticos sólidos e 2 híbridos dinâmicos.

### Bloco 3: O Híbrido como "1"
- **Cenário 7: 1 Híbrido vs 5 Matemáticos** (`07_hybrid_vs_5_maths`)
  - **Assentos:** `hybrid, math, math, math, math, math`
  - **Objetivo:** Avaliar a extração de fichas e armadilhas do híbrido contra uma mesa estritamente conservadora em odds.
- **Cenário 8: 1 Híbrido vs 5 Blefadores** (`08_hybrid_vs_5_bluffers`)
  - **Assentos:** `hybrid, bluffer, bluffer, bluffer, bluffer, bluffer`
  - **Objetivo:** Avaliar como o híbrido pune blefadores excessivos explorando suas fraquezas no turn e river.
- **Cenário 9: 1 Híbrido vs 5 Mistos** (`09_hybrid_vs_5_mistos`)
  - **Assentos:** `hybrid, math, math, math, bluffer, bluffer`
  - **Objetivo:** Testar a adaptabilidade completa do híbrido isolado em um ecossistema equilibrado de 3 matemáticos e 2 blefadores.

---

## 2. Execução Automatizada
Execute no terminal:
```powershell
python scripts/run_experiments_notebook.py --seed 101 --tag seed101
```
