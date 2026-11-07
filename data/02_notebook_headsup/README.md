# 02 - Experimentos no Notebook: Duelos Heads-Up (1 vs 1)

Este diretório armazena os confrontos diretos isolados gerados no notebook para medir a dominância par a par entre os 3 agentes definitivos do TCC.

---

## 1. Duelos Configurados (500 Mãos por Duelo)

### Duelo 1: Blefador vs Matemático
- **Objetivo:** Confronto entre agressão com blockers/teoria dos jogos e a disciplina matemática pura de pot odds e equidade Monte Carlo.
- **Assentos:** `bluffer`, `math`
- **Semente:** 101
- **Pasta:** `data/02_notebook_headsup/duel_bluffer_vs_matematico/`

### Duelo 2: Híbrido vs Matemático
- **Objetivo:** Avaliar como a alternância entre valor, slow-plays e semi-blefes do Híbrido se comporta contra a precisão analítica do Matemático.
- **Assentos:** `hybrid`, `math`
- **Semente:** 101
- **Pasta:** `data/02_notebook_headsup/duel_hibrido_vs_matematico/`

### Duelo 3: Híbrido vs Blefador
- **Objetivo:** Duelo de alta volatilidade entre dois agentes agressivos, testando a adaptação do Híbrido contra tentativas constantes de roubo de pote.
- **Assentos:** `hybrid`, `bluffer`
- **Semente:** 101
- **Pasta:** `data/02_notebook_headsup/duel_hibrido_vs_bluffer/`

---

## 2. Execução Automatizada (Todos do Notebook de uma só vez)
Execute no terminal:
```powershell
python scripts/run_experiments_notebook.py --seed 101 --tag seed101
```
