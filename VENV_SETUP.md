# Ambiente Virtual - RLCard Leduc Feature

## Localização
- **Caminho**: `C:\venv_poker`
- **Sessão**: shakyta1-solid-waffle (feature/rlcard-leduc)

## Ativação

### Windows CMD
```batch
C:\venv_poker\Scripts\activate.bat
```

### Windows PowerShell
```powershell
C:\venv_poker\Scripts\Activate.ps1
```

### Quick Activate (atalho)
```batch
.\activate_env.bat
```

## Dependências Instaladas

### Base (requirements/base.txt)
- **Data Science**: numpy, pandas, scipy, scikit-learn
- **RL Framework**: gymnasium, rlcard, stable-baselines3
- **Deep Learning**: torch
- **Visualização**: matplotlib, plotly
- **Database**: sqlalchemy, psycopg2-binary
- **Utilitários**: tqdm

### Development (disponível em requirements/dev.txt)
- jupyter, ipykernel
- pytest
- black, isort, flake8
- python-dotenv

## Verificação

Para verificar se o ambiente está funcionando:

```python
import rlcard
import gymnasium
import torch
import numpy as np

print("✓ RLCard:", rlcard.__version__)
print("✓ Gymnasium OK")
print("✓ PyTorch OK")
print("✓ NumPy OK")
```

## Nota
A instalação dos pacotes de dev (jupyter, etc) foi limitada devido a restrições de caminhos longos no Windows. As dependências base necessárias para o projeto RLCard estão todas instaladas.
