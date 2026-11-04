# 03 - Experimentos no Notebook: Mesas de Estresse Homogêneas (1 vs 5)

Este diretório armazena os testes de estresse projetados para avaliar a robustez de um agente colocado em um ecossistema extremo (1 agente isolado contra 5 oponentes de perfil agressivo, passivo ou blefador).

---

## 1. Cenários de Estresse Configurados (500 Mãos por Cenário)

### Cenário 1: 1 Matemático vs 5 Blefadores Maníacos
- **Objetivo:** Testar se a baseline estritamente matemática (+EV) resiste à pressão de roubo de potes contínua ou se é explorada por over-folding.
- **Assentos:** `math`, `bluffer`, `bluffer`, `bluffer`, `bluffer`, `bluffer`
- **Semente:** 201
- **Pasta:** `data/03_notebook_estresse_1v5/01_math_vs_5_bluffers/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats math bluffer bluffer bluffer bluffer bluffer `
      --seed 201 `
      --test-id 01_math_vs_5_bluffers `
      --output-dir data/03_notebook_estresse_1v5
  ```

### Cenário 2: 1 GhBluffer (GTO Nash) vs 5 Conservadores Passivos (NITs)
- **Objetivo:** Avaliar a capacidade de extração de fold equity do modelo GTO com blockers contra uma mesa que recusa confrontos e só joga mãos premium.
- **Assentos:** `gh_bluffer`, `conservative`, `conservative`, `conservative`, `conservative`, `conservative`
- **Semente:** 202
- **Pasta:** `data/03_notebook_estresse_1v5/02_ghbluffer_vs_5_passivos/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats gh_bluffer conservative conservative conservative conservative conservative `
      --seed 202 `
      --test-id 02_ghbluffer_vs_5_passivos `
      --output-dir data/03_notebook_estresse_1v5
  ```

### Cenário 3: 1 Híbrido Mestre vs 5 Agressivos Descontrolados (LAGs)
- **Objetivo:** Avaliar como a alternância entre valor e camuflagem do híbrido se comporta contra um field altamente volátil que infla todos os potes.
- **Assentos:** `hybrid`, `aggressive`, `aggressive`, `aggressive`, `aggressive`, `aggressive`
- **Semente:** 203
- **Pasta:** `data/03_notebook_estresse_1v5/03_hibrido_vs_5_agressivos/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats hybrid aggressive aggressive aggressive aggressive aggressive `
      --seed 203 `
      --test-id 03_hibrido_vs_5_agressivos `
      --output-dir data/03_notebook_estresse_1v5
  ```

### Cenário 4: 1 GhMath (Gustavo) vs 5 Blefadores Maníacos
- **Objetivo:** Avaliar a precisão bayesiana e o dimensionamento de Kelly do GhMath ao caçar blefes constantes de 5 oponentes irracionais.
- **Assentos:** `gh_math`, `bluffer`, `bluffer`, `bluffer`, `bluffer`, `bluffer`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/04_ghmath_vs_5_bluffers/`

### Cenário 5: 1 Matemático Treinado (Tier S) vs 5 Blefadores Maníacos
- **Objetivo:** Avaliar a política por reforço (DQN/RL) do Matemático Treinado contra blefes contínuos.
- **Assentos:** `trained_math`, `bluffer`, `bluffer`, `bluffer`, `bluffer`, `bluffer`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/05_trained_math_vs_5_bluffers/`

### Cenário 6: 1 Blefador Treinado (Tier S) vs 5 Conservadores Passivos (NITs)
- **Objetivo:** Avaliar como a rede de blefe treinada explora jogadores super passivos.
- **Assentos:** `trained_bluffer`, `conservative`, `conservative`, `conservative`, `conservative`, `conservative`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/06_trained_bluffer_vs_5_passivos/`

### Cenário 7: 1 Blefador Heurístico vs 5 Matemáticos Baseline
- **Objetivo:** Testar o que acontece com um blefador contínuo quando a mesa inteira calcula Pot Odds friamente.
- **Assentos:** `bluffer`, `math`, `math`, `math`, `math`, `math`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/07_bluffer_vs_5_matematicos/`

### Cenário 8: 1 Equilibrado (TAG) vs 5 Blefadores Maníacos
- **Objetivo:** Avaliar a disciplina de uma estratégia Tight-Aggressive padrão contra maníacos.
- **Assentos:** `balanced`, `bluffer`, `bluffer`, `bluffer`, `bluffer`, `bluffer`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/08_balanced_vs_5_bluffers/`

### Cenário 9: 1 Conservador (NIT) vs 5 Agressivos Descontrolados (LAGs)
- **Objetivo:** Testar a capacidade de sobrevivência e punição de um jogador ultra-tight contra LAGs.
- **Assentos:** `conservative`, `aggressive`, `aggressive`, `aggressive`, `aggressive`, `aggressive`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/09_conservative_vs_5_agressivos/`

### Cenário 10: 1 Agressivo (LAG) vs 5 Conservadores Passivos (NITs)
- **Objetivo:** Medir a taxa de roubo de potes incontestados de um jogador agressivo contra passivos.
- **Assentos:** `aggressive`, `conservative`, `conservative`, `conservative`, `conservative`, `conservative`
- **Semente:** 42
- **Pasta:** `data/03_notebook_estresse_1v5/10_aggressive_vs_5_passivos/`

---

## 2. Execução Automatizada
Execute no terminal do notebook:
```powershell
.venv\Scripts\python.exe scripts/run_experiments_notebook.py
```
