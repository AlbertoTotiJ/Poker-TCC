# 🃏 Poker-TCC

## Inteligência Artificial para Texas Hold'em utilizando Reinforcement Learning

Projeto de Trabalho de Conclusão de Curso (TCC) do curso de **Ciência de Dados**, com foco no desenvolvimento, treinamento e avaliação de agentes inteligentes para o jogo **Texas Hold'em No-Limit Poker** utilizando técnicas de **Reinforcement Learning (RL)**.

---

# 📖 Objetivo

O objetivo deste projeto é desenvolver agentes capazes de aprender estratégias de poker através de interação com o ambiente, comparando diferentes algoritmos de aprendizado por reforço e avaliando seu desempenho por meio de métricas experimentais.

Além do treinamento dos agentes, o projeto contempla:

* Modelagem do ambiente de poker;
* Treinamento utilizando algoritmos de RL;
* Avaliação estatística dos agentes;
* Visualização de métricas e resultados;
* Organização do projeto seguindo boas práticas de Engenharia de Software.

---

# 🎯 Objetivos Específicos

* Estudar o ambiente Texas Hold'em.
* Utilizar o RLCard como simulador.
* Integrar o ambiente ao Gymnasium.
* Implementar agentes utilizando Stable-Baselines3.
* Comparar diferentes algoritmos de Reinforcement Learning.
* Avaliar desempenho utilizando métricas quantitativas.

---

# 🛠 Tecnologias

* Python 3.11
* PyTorch
* RLCard
* Gymnasium
* Stable-Baselines3
* NumPy
* Pandas
* Scikit-Learn
* Matplotlib
* Plotly
* SQLAlchemy
* PostgreSQL
* Docker

---

# 📂 Estrutura do Projeto

```text
Poker-TCC/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── generated/
│
├── docs/
│
├── models/
│
├── notebooks/
│
├── requirements/
│   ├── base.txt
│   └── dev.txt
│
├── src/
│   ├── agents/
│   ├── env/
│   ├── training/
│   ├── evaluation/
│   ├── visualization/
│   ├── database/
│   ├── utils/
│   └── scripts/
│
├── tests/
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

# 🚀 Como executar

## 1. Clonar o projeto

```bash
git clone https://github.com/AlbertoTotiJ/Poker-TCC.git
```

```bash
cd Poker-TCC
```

---

## 2. Criar ambiente virtual

Windows

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\activate
```

Linux / Mac

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

---

## 3. Instalar dependências

```bash
pip install -r requirements/dev.txt
```

---

## 📊 Fluxo do Projeto

```text
Ambiente RLCard
        │
        ▼
Integração com Gymnasium
        │
        ▼
Treinamento dos Agentes
        │
        ▼
Avaliação
        │
        ▼
Análise Estatística
        │
        ▼
Visualização dos Resultados
```

---

# 📈 Algoritmos previstos

* Random Agent
* PPO
* DQN
* A2C
* Outros algoritmos experimentais

---

# 📚 Bibliotecas Principais

| Biblioteca        | Finalidade                           |
| ----------------- | ------------------------------------ |
| RLCard            | Simulação do ambiente de Poker       |
| Gymnasium         | Interface do ambiente                |
| Stable-Baselines3 | Algoritmos de Reinforcement Learning |
| PyTorch           | Backend de Deep Learning             |
| Pandas            | Manipulação de dados                 |
| NumPy             | Computação Numérica                  |
| Matplotlib        | Visualização                         |
| Plotly            | Dashboards e gráficos                |

---

# 🧪 Status do Projeto

* [x] Estrutura inicial criada
* [x] Ambiente Python configurado
* [x] Dependências instaladas
* [ ] Configuração Docker
* [ ] Integração com RLCard
* [ ] Desenvolvimento dos agentes
* [ ] Treinamento
* [ ] Avaliação
* [ ] Documentação final

---

# 👨‍💻 Autores

Alberto Toti José
Giovane Adão de Moraes
Gustavo de Souza Ramos

Curso de Ciência de Dados

---

# 📄 Licença

Projeto desenvolvido exclusivamente para fins acadêmicos.
