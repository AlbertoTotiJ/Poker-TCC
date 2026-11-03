# 01 - Experimentos no Computador Desktop: Mesas Coletivas (6-Max e 9-Max Full Ring)

Este diretório armazena os dados das simulações multi-agente completas (mesas coletivas heterogêneas) geradas no computador principal.

---

## 1. Experimentos Configurados

### Exp 1: Mesa 6-Max Heterogênea (1.000 Mãos)
- **Assentos:** 6 agentes com estilos distintos (`gh_bluffer`, `gh_math`, `math`, `bluffer`, `hybrid`, `balanced`).
- **Semente:** 42 (reprodutibilidade estrita).
- **Pasta de Saída:** `data/01_desktop_mesas/6max_heterogeneo_1000m/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 1000 `
      --custom-seats gh_bluffer gh_math math bluffer hybrid balanced `
      --seed 42 `
      --test-id 6max_heterogeneo_1000m `
      --output-dir data/01_desktop_mesas
  ```

### Exp 2: Mesa 9-Max Full Ring Completa (1.000 Mãos)
- **Assentos:** Todos os 9 perfis de agentes desenvolvidos no projeto (`gh_bluffer`, `gh_math`, `math`, `trained_math`, `bluffer`, `trained_bluffer`, `hybrid`, `aggressive`, `conservative`).
- **Semente:** 42.
- **Pasta de Saída:** `data/01_desktop_mesas/9max_full_ring_1000m/`
- **Comando Manual:**
  ```powershell
  .venv\Scripts\python.exe scripts/generate_decision_telemetry.py `
      --hands 1000 `
      --custom-seats gh_bluffer gh_math math trained_math bluffer trained_bluffer hybrid aggressive conservative `
      --seed 42 `
      --test-id 9max_full_ring_1000m `
      --output-dir data/01_desktop_mesas
  ```

---

## 2. Execução Automatizada (Todos do Desktop de uma só vez)
Execute no terminal:
```powershell
.venv\Scripts\python.exe scripts/run_experiments_desktop.py
```
