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

---

## 2. Execução Automatizada
Execute no terminal do notebook:
```powershell
.venv\Scripts\python.exe scripts/run_experiments_notebook.py
```
