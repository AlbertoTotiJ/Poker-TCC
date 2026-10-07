# Detecção e Análise de Blefes em Agentes Autônomos de Texas Hold'em

Repositório central de desenvolvimento do Trabalho de Conclusão de Curso (TCC). O projeto consiste em um ambiente fechado de simulação de poker na modalidade *Texas Hold'em*, com agentes autônomos baseados em Inteligência Artificial, instrumentação para observabilidade de ações e pipeline estatístico/preditivo para identificação e análise de blefes.

---

## 1. Visão Geral do Projeto

O objetivo principal deste trabalho é construir um ecossistema experimental para simular partidas de Texas Hold'em entre agentes inteligentes e quantificar/detectar padrões de blefe a partir de dados observáveis da partida.

### 1.1 Objetivos Principais
1. **Ambiente Fechado de Simulação:** Implementar a mecânica oficial do Texas Hold'em (rodadas pré-flop, flop, turn e river, gestão de potes, blinds, side pots e showdown).
2. **Agentes Autônomos de IA:** Desenvolver agentes com perfis estratégicos variados (e.g., conservador/tight, agressivo/loose, baseados em heurística ou aprendizado por reforço).
3. **Mecanismo de Telemetria e Observação:** Registrar de forma estruturada as trajetórias completas do jogo (histórico de apostas, tamanho de raises, posições na mesa, cartas comunitárias e cartas privadas reveladas pós-showdown).
4. **Módulo de Análise e Detecção de Blefe:** Extrair métricas comportamentais (frequência de agressão, disparidade entre valor real da mão e padrão de aposta, timing e sizing) e treinar modelos para classificação ou detecção precoce de blefes.
5. **Todas as respostas dos agentes será em PORTUGUÊS** 

---

## 2. Diretrizes Estritas de Codificação (Clean Code)

A manutenção, legibilidade e rigor técnico do código são pilares fundamentais deste projeto. Todas as contribuições devem aderir estritamente às normas abaixo.

### 2.1 Política de Comentários
* **Proibidos comentários triviais e óbvios:** Não explique *o que* a linha de código faz quando a própria sintaxe já torna isso claro.
* **Permitidos apenas comentários de contexto/motivação:** Comentários só devem existir para justificar decisões não triviais (e.g., uma escolha matemática específica, contorno de limitação de regras de poker ou suposições de teoria dos jogos).
* **Código autodocumentável:** A intenção deve ser comunicada por nomes descritivos de funções, métodos e variáveis, nunca por comentários adjacentes.

### 2.2 Estrutura e Modularidade
* **Princípio da Responsabilidade Única (SRP):** Cada função, método ou classe deve resolver exatamente um problema bem delimitado.
* **Funções pequenas e sem efeitos colaterais ocultos:** Prefira funções puras sempre que possível, facilitando a testabilidade.
* **Tipagem Estrita (Type Annotations):** Toda assinatura de função e método deve incluir tipos explícitos para parâmetros e retorno (`typing`).
* **Docstrings:** Use docstrings concisas (padrão Google ou PEP 257) focadas no contrato da função (entradas, saídas e possíveis exceções levantadas), sem redundâncias.

---

## 3. Padrão de Código: Exemplos Comparativos

### ❌ Incorreto (Ruído visual e comentários desnecessários)

```python
# Função que avalia a aposta
def bet_eval(p, b, c):
    # Pega o pote
    pot = p
    # Pega a aposta
    bet = b
    # Calcula a razao do pote
    # Divide a aposta pelo total do pote mais aposta
    ratio = bet / (pot + bet)  # calcula odds
    
    # Se a razao for menor que 0.3 retorna verdadeiro
    if ratio < 0.3:
        return True # pode pagar
    else:
        return False # folda
```

### ✅ Correto (Código limpo, tipado e autoexplicativo)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PotOdds:
    current_pot: float
    bet_to_call: float

    @property
    def call_ratio(self) -> float:
        return self.bet_to_call / (self.current_pot + self.bet_to_call)

    def is_favorable(self, required_threshold: float = 0.30) -> bool:
        """Determina se a aposta é matematicamente vantajosa com base no limiar exigido."""
        return self.call_ratio < required_threshold
```

---

## 4. Arquitetura Modular do Repositório

O projeto é organizado em módulos desacoplados para garantir isolamento entre as regras do jogo, a lógica dos agentes e o motor de telemetria/análise:

```text
├── src/
│   ├── engine/             # Regras fundamentais do Texas Hold'em
│   │   ├── deck.py         # Baralho, naipes e embaralhamento
│   │   ├── hand_eval.py    # Avaliador de força e combinações de mãos
│   │   ├── pot.py          # Gestão do pote principal e potes paralelos (side pots)
│   │   └── table.py        # Estado da mesa, posições (dealer, blinds) e transições
│   │
│   ├── agents/             # Implementação dos jogadores autônomos
│   │   ├── base.py         # Interface abstrata padrão para agentes
│   │   ├── heuristic.py    # Agentes baseados em regras/heurísticas de probabilidade
│   │   └── rl/             # Agentes baseados em aprendizado por reforço / Teoria dos Jogos
│   │
│   ├── telemetry/          # Mecanismos de observação e persistência
│   │   ├── tracker.py      # Captura de logs de ações a cada street (pre-flop ao showdown)
│   │   └── schemas.py      # Esquemas estruturados para persistência das partidas
│   │
│   └── analysis/           # Motor de detecção e classificação de blefe
│       ├── features.py     # Engenharia de atributos (agressividade, histórico de apostas)
│       └── detector.py     # Modelos preditivos e classificadores de blefes
│
├── tests/                  # Testes unitários cobrindo engine, agentes e avaliação
├── notebooks/              # Análise exploratória e visualização dos dados coletados
├── config/                 # Parâmetros de simulação (blinds, bankroll, número de mãos)
├── requirements.txt        # Dependências do projeto
└── README.md               # Este documento
```

---

## 5. Metodologia de Detecção de Blefe

No contexto deste projeto, um **blefe** é categorizado e medido através de:
1. **Disparidade Ação-Mão:** Tomada de ação agressiva (aposta/aumento) com equidade de mão baixa (mãos fracas ou especulativas) em relação ao board.
2. **Semi-blefe:** Agressão com mãos fracas no momento, mas com alta equidade futura (draws de flush ou sequência).
3. **Métricas de Agressão do Agente:** Razão entre apostas/aumentos e ações passivas (check/call) ponderada pela força real das cartas em cada rodada (*street*).
4. **Extração de Atributos:** Posição na mesa, relação aposta/pote (*bet sizing*), histórico recente do agente e textura do bordo.

---

## 6. Ambiente de Desenvolvimento e Ferramentas

* **Linguagem:** Python 3.10+
* **Formatação e Estilo:** `black` e `ruff` para manter padrão estético sem debates manuais.
* **Verificação Estática:** `mypy` para validação rigorosa de tipos.
* **Testes Automatizados:** `pytest` para testes das regras do jogo e avaliador de mãos.

```bash
# Instalação das dependências
pip install -r requirements.txt

# Execução da suíte de testes
pytest tests/ -v

# Validação de tipos
mypy src/
```

---

## 7. Próximos Passos (Roadmap do TCC)

- [ ] Implementar motor do baralho e avaliador de mãos de 7 cartas (`engine/hand_eval.py`).
- [ ] Construir o loop principal de rodadas de apostas e gestão de potes (`engine/table.py`).
- [ ] Definir a interface padrão de agente com observação parcial das informações (`agents/base.py`).
- [ ] Implementar agentes baseline (Randômico, Heurístico Básico, Tight-Aggressive).
- [ ] Desenvolver o sistema de telemetria com exportação para Parquet/JSON.
- [ ] Implementar pipeline de rotulagem e detecção supervisionada/não-supervisionada de blefes.
