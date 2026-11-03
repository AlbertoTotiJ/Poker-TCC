# 02 - Experimentos no Notebook: Duelos Heads-Up (1 vs 1)

Este diretório armazena os confrontos diretos isolados gerados no notebook para medir a dominância par a par entre os paradigmas do TCC.

---

## 1. Duelos Configurados (500 Mãos por Duelo)

### Duelo 1: GhBluffer (GTO Nash/Blockers) vs Matemático (Baseline Invariante)
- **Assentos:** `gh_bluffer`, `math`
- **Semente:** 101
- **Pasta:** `data/02_notebook_headsup/duel_ghbluffer_vs_matematico/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats gh_bluffer math `
      --seed 101 `
      --test-id duel_ghbluffer_vs_matematico `
      --output-dir data/02_notebook_headsup
  ```

### Duelo 2: Híbrido (Evolutivo Adaptativo) vs GhMath (Kelly Fracionário/XAI)
- **Assentos:** `hybrid`, `gh_math`
- **Semente:** 102
- **Pasta:** `data/02_notebook_headsup/duel_hibrido_vs_ghmath/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats hybrid gh_math `
      --seed 102 `
      --test-id duel_hibrido_vs_ghmath `
      --output-dir data/02_notebook_headsup
  ```

### Duelo 3: Blefador Clássico (Heurístico) vs Matemático (Baseline Invariante)
- **Assentos:** `bluffer`, `math`
- **Semente:** 103
- **Pasta:** `data/02_notebook_headsup/duel_bluffer_vs_matematico/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 500 `
      --custom-seats bluffer math `
      --seed 103 `
      --test-id duel_bluffer_vs_matematico `
      --output-dir data/02_notebook_headsup
  ```

---

## 2. Execução Automatizada (Todos do Notebook de uma só vez)
Execute no terminal do notebook:
```powershell
.venv\Scripts\python.exe scripts/run_experiments_notebook.py
```
