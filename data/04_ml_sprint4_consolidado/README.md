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

## 2. Arquitetura dos Modelos Treinados

Foram desenvolvidos e validados dois modelos complementares:

### A. Modelo In-Game / Blind Observer (`bluff_detector_model.joblib`)
- **Premissa Operacional:** Utiliza **exclusivamente dados públicos da mesa**, sem acesso às cartas fechadas de nenhum adversário. É o modelo utilizado para inferência em tempo real nas partidas.
- **Atributos de Entrada (100% Públicos):**
  - `street` (PREFLOP, FLOP, TURN, RIVER)
  - `action_taken` (BET, RAISE, ALL_IN)
  - `bettor_profile` (Matemático, Blefador, Híbrido)
  - `amount` (Valor da aposta atual)
  - `pot_before` (Tamanho do pote acumulado antes da aposta)
  - `bet_to_pot_ratio` (Razão entre a aposta e o pote — *Bet Sizing*)
  - `stack_to_pot_ratio` (Stack restante do vilão em relação ao pote — *SPR*)
  - `pot_odds` (Odds financeiras oferecidas pela mesa)
- **Performance no Teste Cego (7.647 Amostras Inéditas):**
  - **Acurácia Global:** **89,25%**
  - **Sensibilidade / Recall de Blefe:** **91,76%** *(detecta mais de 9 em cada 10 blefes antes do showdown)*
  - **Precisão de Blefe:** **84,71%**
  - **F1-Score:** **0,8809**
  - **Área sob a Curva ROC (ROC-AUC):** **0,9665** (96,65%)
  - **Área sob a Curva PR (PR-AUC):** **0,9589** (95,89%)

### B. Modelo XAI Oracle / Auditoria Teórica (`bluff_detector_xai.joblib`)
- **Premissa Operacional:** Incorpora os atributos cognitivos internos do agente (`raw_equity` via Monte Carlo, `equity_disparity` e `outs_count`).
- **Performance:** **100,00% de Acurácia** e **1,0000 ROC-AUC**, comprovando matematicamente a consistência sem ruído da função de rotulagem do simulador.

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
