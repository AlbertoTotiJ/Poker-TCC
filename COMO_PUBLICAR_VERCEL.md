# 🌐 Guia de Publicação no Vercel (Poker-TCC)

Este guia ensina como colocar o jogo de poker online gratuitamente no **Vercel**, permitindo que qualquer pessoa acesse e jogue pelo navegador no PC ou celular através de um link público (ex: `https://poker-tcc.vercel.app`).

---

## 🏗️ 1. Como a Arquitetura da Vercel Funciona neste Projeto

O projeto foi estruturado com suporte nativo à Vercel:
- **Front-end (`public/index.html`):** A mesa de feltro verde e a interface visual são distribuídas globalmente pela CDN Edge da Vercel (carregamento instantâneo).
- **Back-end Serverless (`api/index.py`):** O motor de Texas Hold'em, as regras de aposta e os agentes de IA (`HeuristicAgent`) rodam em Serverless Functions em Python.
- **Isolamento de Sessões (`session_id`):** Cada jogador que acessa o link tem sua própria mesa e seus próprios bots, sem interferir na partida de outros usuários.
- **Zero Dependências Pesadas:** O servidor utiliza exclusivamente a biblioteca padrão do Python, garantindo um build ultrarrápido (menos de 10 segundos).

---

## 🚀 2. Método Recomendado: Publicação via GitHub (1 Clique)

Como o seu projeto já está sincronizado com o GitHub, esse é o caminho mais rápido e profissional:

1. Acesse **[vercel.com](https://vercel.com)** e faça login com a sua conta do GitHub.
2. No painel principal (Dashboard), clique no botão **"Add New..."** e selecione **"Project"**.
3. Na lista de repositórios, localize o **`Poker-TCC`** e clique em **"Import"**.
4. **Configurações do Projeto:**
   - **Framework Preset:** Deixe como *Other* (a Vercel detectará o `vercel.json` automaticamente).
   - **Root Directory:** Deixe `./` (raiz).
   - **Build & Output Settings:** Deixe os padrões.
5. Clique em **"Deploy"**.

Em menos de 1 minuto, a Vercel gerará o link oficial do seu jogo (ex: `https://poker-tcc-seu-usuario.vercel.app`).

> 💡 **Deploy Contínuo:** Toda vez que você fizer um `git push` para a branch `main`, a Vercel atualizará o jogo no ar automaticamente!

---

## 💻 3. Método Alternativo: Publicação pelo Terminal (`npx vercel`)

Você também pode publicar diretamente pelo seu terminal, sem precisar abrir o navegador:

1. Abra o terminal na pasta do projeto e execute:
   ```powershell
   npx vercel
   ```
2. Na primeira vez, o terminal abrirá uma autenticação rápida no navegador.
3. Responda às perguntas no terminal (pressione `Enter` para aceitar todas as opções padrão):
   - *Set up and deploy?* -> `Y`
   - *Which scope?* -> [Seu usuário]
   - *Link to existing project?* -> `N`
   - *Project name?* -> `poker-tcc` (ou pressione Enter)
   - *Directory?* -> `./` (Enter)
4. Para enviar a versão definitiva para produção:
   ```powershell
   npx vercel --prod
   ```

O link final de produção será exibido diretamente no seu terminal!

---

## 📁 4. Arquivos de Configuração Criados

- [`vercel.json`](vercel.json): Regras de roteamento de `/api/(.*)` para o handler serverless em Python.
- [`api/index.py`](api/index.py): Ponto de entrada das funções serverless da Vercel.
- [`public/index.html`](public/index.html): Interface gráfica estática da mesa de poker.
- [`.vercelignore`](.vercelignore): Exclui ambientes locais (`.venv`, notebooks, caches) para otimizar o tempo de envio.
- [`requirements.txt`](requirements.txt): Declaração leve de dependências para o ambiente de execução serverless.
