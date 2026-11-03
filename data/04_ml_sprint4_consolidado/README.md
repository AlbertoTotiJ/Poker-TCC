# 04 - Pipeline de Machine Learning para Detecção de Blefes (Sprint 4)

Este diretório armazena os datasets particionados e os artefatos de modelos preditivos treinados para inferir blefes a partir de dados públicos da mesa.

---

## 1. Conteúdo Esperado
- `train_features.csv` (70% das mãos para treinamento supervisionado)
- `val_features.csv` (15% para ajuste de hiperparâmetros)
- `test_blind.csv` (15% para teste cego de generalização)
- `plots/`:
  - `matriz_confusao.png` (Matriz de confusão normalizada para blefe vs valor)
  - `curva_roc_pr.png` (Curvas ROC e Precision-Recall)
  - `shap_summary_explicabilidade.png` (Gráfico XAI de importância de atributos)
