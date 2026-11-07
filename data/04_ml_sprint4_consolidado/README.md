# 04 — Pipeline de Machine Learning para Detecção e Análise de Blefes (Sprint 4)

Este diretório contém os conjuntos de dados particionados, artefatos serializados e gráficos científicos resultantes do treinamento de modelos preditivos supervisionados de Machine Learning para a identificação autônoma de blefes no Texas Hold'em Poker.

---

## 1. Resumo Executivo e Volume de Dados

O dataset experimental consolidado foi gerado através das três seeds definitivas de simulação (**Seed 101, Seed 144 e Seed 99**), cobrindo os três cenários empíricos:
- **01 - Desktop Mesas Completas (Full-Ring 9-Max, Tripartite: 3 Matemáticos, 3 Blefadores, 3 Híbridos)**
- **02 - Notebook Heads-Up (1v1 Clássico entre todos os pares de perfis)**
- **03 - Notebook Estresse 1v5 (1 Agente Solitário contra 5 Clones de perfil antagônico)**

| Métrica | Quantidade |
| :--- | :--- |
| **Total de Decisões Brutas Consolidadas** | **181.083** decisões |
| **Apostas Agressivas Analisadas (BET, RAISE, ALL-IN)** | **50.978** amostras |
| **Apostas Reais de Valor (Ground Truth = 0)** | **28.886** (56,66%) |
| **Blefes Reais Detectados (Ground Truth = 1)** | **22.092** (43,34%) |
| **Divisão Estratificada (Train / Val / Test)** | **70%** (35.684) / **15%** (7.647) / **15%** (7.647) |

---

## 2. Benchmark Comparativo dos 4 Modelos de Machine Learning (Dados Públicos In-Game)

Para inferir blefes a partir de dados 100% públicos da mesa, foram implementados e submetidos a benchmark comparativo **quatro algoritmos supervisionados de famílias distintas**:

1. **HistGradientBoosting Classifier:** Gradient Boosting baseado em histogramas para particionamento contínuo rápido e mapeamento de interações não-lineares.
2. **Random Forest Classifier:** Ensemble de 150 árvores de decisão independentes (Bagging) com impureza de Gini e paralelização nativa.
3. **Rede Neural MLP (Multi-Layer Perceptron):** Arquitetura neural profunda com 2 camadas densas (64 e 32 neurônios), ativação ReLU, otimizador Adam e regularização early stopping.
4. **Regressão Logística com Regularização L2 (Ridge):** Modelo linear estatístico (C=1.0) utilizado para estabelecer a linha de base e testar a hipótese de linearidade das variáveis da mesa.

### Tabela Oficial de Benchmark no Teste Cego Independente (7.647 Amostras Inéditas):

| Algoritmo | Acurácia | Precisão | Recall (Sensibilidade) | F1-Score | ROC-AUC | PR-AUC | Tempo Treino |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **HistGradientBoosting** | **89,43%** | **85,54%** | 91,01% | **0,8819** | **0,9704 (97,0%)** | **0,9635** | 3,31s |
| **Random Forest (150 Árvores)** | **89,25%** | 84,71% | **91,76%** | 0,8809 | 0,9665 (96,7%) | 0,9589 | **1,09s** |
| **Rede Neural MLP (64x32)** | 86,86% | 80,60% | **91,76%** | 0,8582 | 0,9499 (95,0%) | 0,9387 | 5,99s |
| **Regressão Logística (L2)** | 76,00% | 70,67% | 76,28% | 0,7337 | 0,8574 (85,7%) | 0,7866 | **0,15s** |

### Destaques e Discussão dos Resultados:
- **Árvores de Decisão & Boosting (Campeões):** O HistGradientBoosting e o Random Forest alcançaram a melhor performance geral (~89,4% acurácia e 97,0% ROC-AUC), evidenciando que cortes por limiares numéricos (*Threshold splits*) são ideais para capturar o comportamento de *Bet Sizing* e *Pot Odds*.
- **Alta Sensibilidade Neural:** A Rede Neural MLP empatou no topo da sensibilidade (91,76% de Recall de Blefe), mostrando grande robustez ao identificar agressores com blefes ativos.
- **Comprovação de Não-Linearidade:** A queda de desempenho da Regressão Logística para 76,00% comprova que o blefe no Poker é um fenômeno **estritamente não-linear**, governado pela relação multiplicativa entre razão aposta/pote e comprometimento de stack.
- **Modelo XAI Oracle (Referência Teórica):** Com a inclusão da telemetria cognitiva interna (`raw_equity`, `equity_disparity`, `outs_count`), o classificador atinge **100,00% de acurácia e 1,000 ROC-AUC**, comprovando a ausência de ruído na rotulagem algorítmica do projeto.

---

## 3. Gráficos Científicos de Alta Resolução (300 DPI)

Os gráficos em `plots/` foram formatados seguindo os padrões visuais exigidos para teses e artigos acadêmicos:

1. **`matriz_confusao.png`**: Matriz de confusão normalizada com contagem amostral por quadrante do detector In-Game.
2. **`curva_roc_pr.png`**: Curvas ROC e Precision-Recall comparativas (In-Game vs XAI Oracle vs Classificador Aleatório).
3. **`shap_summary_explicabilidade.png`**: Ranking de importância de atributos (*Feature Importance*) que detalha o que mais denuncia um blefe (liderado pela Razão Aposta/Pote com ~35% de peso).
4. **`distribuicao_probabilidade_blefe.png`**: Histograma calibrado da probabilidade contínua preditiva $P(\text{Blefe})$, ilustrando a nítida separação bimodal entre mãos de valor e blefes.

---

## 4. Como Executar a Inferência

Para consultar o detector em tempo real em qualquer módulo ou partida:

```python
from src.models.bluff_detector import BluffDetector

detector = BluffDetector()

# Aposta suspeita realizada na mesa
veredito = detector.analyze_bet({
    "street": "RIVER",
    "action_taken": "RAISE",
    "bettor_profile": "Blefador",
    "amount": 250.0,
    "pot_before": 100.0,
    "player_stack_before": 800.0,
    "pot_odds": 0.35
})

print(veredito)
# Saída:
# {
#   'bluff_probability': 0.8842,
#   'is_bluff': True,
#   'verdict': 'ALTO_RISCO_BLEFE',
#   'tactical_recommendation': 'Re-aumentar ou dar Call (Vilão muito polarizado para blefe).'
# }
```
