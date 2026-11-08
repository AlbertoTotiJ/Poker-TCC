#!/usr/bin/env python3
"""
generate_defense_presentation.py
Gera a apresentação oficial completa em PowerPoint (.pptx) para a aula/defesa do TCC:
"Detecção de Blefe e análise de Comportamento utilizando Agentes de I.A"
Centro Paula Souza - Fatec Ourinhos

Autores:
- Alberto Totti José
- Giovane Adão de Moraes
- Gustavo de Souza
Orientador:
- Prof. Dr. Sidney Carlos Ferrari
"""

import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def create_deck():
    prs = Presentation()
    # 16:9 Widescreen dimensions
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # Blank slide

    # Color Palette (Dark Theme / Cyber-Executive)
    C_BG_DARK = RGBColor(15, 23, 42)       # Slate 900
    C_CARD_BG = RGBColor(30, 41, 59)       # Slate 800
    C_CARD_BORDER = RGBColor(51, 65, 85)   # Slate 700
    C_CYAN = RGBColor(56, 189, 248)        # Sky 400
    C_BLUE = RGBColor(37, 99, 235)         # Blue 600
    C_GREEN = RGBColor(74, 222, 128)       # Emerald 400
    C_GOLD = RGBColor(251, 191, 36)        # Amber 400
    C_RED = RGBColor(248, 113, 113)        # Rose 400
    C_PURPLE = RGBColor(192, 132, 252)     # Purple 400
    C_TEXT_WHITE = RGBColor(248, 250, 252) # Slate 50
    C_TEXT_MUTED = RGBColor(148, 163, 184) # Slate 400
    C_TEXT_LIGHT = RGBColor(226, 232, 240) # Slate 200

    def add_slide_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = C_BG_DARK
        bg.line.fill.background()
        return bg

    def add_header(slide, title_text, category_text="CENTRO PAULA SOUZA · FATEC OURINHOS"):
        # Category / Tag Pill
        tag_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(0.4))
        tf_tag = tag_box.text_frame
        tf_tag.word_wrap = True
        tf_tag.margin_left = tf_tag.margin_top = tf_tag.margin_right = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = category_text.upper()
        p_tag.font.size = Pt(11)
        p_tag.font.bold = True
        p_tag.font.color.rgb = C_CYAN

        # Main Title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.7), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(24)
        p.font.bold = True
        p.font.color.rgb = C_TEXT_WHITE

        # Divider line
        div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.733), Inches(0.02))
        div.fill.solid()
        div.fill.fore_color.rgb = C_CARD_BORDER
        div.line.fill.background()

    def add_card(slide, left, top, width, height, bg_color=C_CARD_BG, border_color=C_CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1)
        return card

    # =========================================================================
    # SLIDE 1: CAPA OFICIAL (Reproduzindo o modelo fornecido)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    add_slide_background(s1)

    # Institution Header Card
    add_card(s1, Inches(0.8), Inches(0.8), Inches(11.733), Inches(1.4), C_CARD_BG, C_CYAN)
    inst_box = s1.shapes.add_textbox(Inches(1.2), Inches(1.0), Inches(11.0), Inches(1.0))
    tf_inst = inst_box.text_frame
    p_inst = tf_inst.paragraphs[0]
    p_inst.text = "CENTRO PAULA SOUZA  |  FATEC OURINHOS"
    p_inst.font.size = Pt(16)
    p_inst.font.bold = True
    p_inst.font.color.rgb = C_CYAN
    p_sub = tf_inst.add_paragraph()
    p_sub.text = "CURSO SUPERIOR DE TECNOLOGIA · TRABALHO DE CONCLUSÃO DE CURSO"
    p_sub.font.size = Pt(11)
    p_sub.font.color.rgb = C_TEXT_MUTED

    # Title Card
    add_card(s1, Inches(0.8), Inches(2.5), Inches(11.733), Inches(2.2), RGBColor(23, 37, 84), C_BLUE)
    title_box = s1.shapes.add_textbox(Inches(1.2), Inches(2.8), Inches(11.0), Inches(1.6))
    tf_t = title_box.text_frame
    tf_t.word_wrap = True
    p_t = tf_t.paragraphs[0]
    p_t.text = "Detecção de Blefe e análise de Comportamento\nutilizando Agentes de I.A"
    p_t.font.size = Pt(28)
    p_t.font.bold = True
    p_t.font.color.rgb = C_TEXT_WHITE
    p_t.alignment = PP_ALIGN.CENTER

    # Authors Card (Alunos e Orientador)
    add_card(s1, Inches(0.8), Inches(5.0), Inches(11.733), Inches(1.8), C_CARD_BG, C_CARD_BORDER)
    auth_box = s1.shapes.add_textbox(Inches(1.2), Inches(5.2), Inches(11.0), Inches(1.4))
    tf_auth = auth_box.text_frame
    
    p_a1 = tf_auth.paragraphs[0]
    p_a1.text = "DISCENTES (AUTORES):"
    p_a1.font.size = Pt(11)
    p_a1.font.bold = True
    p_a1.font.color.rgb = C_CYAN

    p_names = tf_auth.add_paragraph()
    p_names.text = "• Alberto Totti José          • Giovane Adão de Moraes          • Gustavo de Souza"
    p_names.font.size = Pt(14)
    p_names.font.bold = True
    p_names.font.color.rgb = C_TEXT_WHITE

    p_ori = tf_auth.add_paragraph()
    p_ori.text = "ORIENTADOR:"
    p_ori.font.size = Pt(11)
    p_ori.font.bold = True
    p_ori.font.color.rgb = C_GOLD

    p_ori_name = tf_auth.add_paragraph()
    p_ori_name.text = "Prof. Dr. Sidney Carlos Ferrari"
    p_ori_name.font.size = Pt(14)
    p_ori_name.font.bold = True
    p_ori_name.font.color.rgb = C_TEXT_WHITE

    s1.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Cumprimentar o Prof. Dr. Sidney Carlos Ferrari, a banca avaliadora, os professores e colegas.\n"
        "Apresentar os membros do grupo: Alberto Totti José, Giovane Adão de Moraes e Gustavo de Souza.\n"
        "Introduzir o tema: 'Detecção de Blefe e Análise de Comportamento utilizando Agentes de Inteligência Artificial'."
    )

    # =========================================================================
    # SLIDE 2: CONTEXTO E O PROBLEMA CIENTÍFICO
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_slide_background(s2)
    add_header(s2, "Contexto & Formulação do Problema", "1. FUNDAMENTAÇÃO TEÓRICA")

    # Card 1: Informação Imperfeita
    add_card(s2, Inches(0.8), Inches(1.8), Inches(3.64), Inches(5.0))
    tb1 = s2.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(3.24), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🃏 O Desafio da Informação Oculta"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_CYAN

    bullets1 = [
        ("Xadrez/Go vs. Poker:", " Jogos clássicos possuem informação perfeita. No No-Limit Texas Hold'em, as cartas dos adversários são ocultas e o espaço amostral é estocástico."),
        ("Dimensão do Problema:", " Árvore de jogo de 10^160 nós de decisão com apostas contínuas e payoffs imprevisíveis."),
        ("Limitação Tradicional:", " Algoritmos gulosos ou árvores minimax falham porque ignoram a psicologia estocástica e a assimetria informacional.")
    ]
    for b_title, b_desc in bullets1:
        p_b = tf1.add_paragraph()
        p_b.text = "• " + b_title
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf1.add_paragraph()
        p_d.text = b_desc
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    # Card 2: A Natureza do Blefe
    add_card(s2, Inches(4.84), Inches(1.8), Inches(3.64), Inches(5.0))
    tb2 = s2.shapes.add_textbox(Inches(5.04), Inches(2.0), Inches(3.24), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p2 = tf2.paragraphs[0]
    p2.text = "🎭 O Blefe: Equilíbrio, Não Ruído"
    p2.font.size = Pt(16)
    p2.font.bold = True
    p2.font.color.rgb = C_RED

    bullets2 = [
        ("Conceito de Nash (GTO):", " O blefe não é um erro ou capricho humano, mas uma exigência matemática para tornar as mãos fortes lucrativas."),
        ("Indiferença Estratégica:", " Se um jogador nunca blefa, seus oponentes dão fold facilmente. Se blefa demais, é explorado e punido."),
        ("A Questão Científica:", " Como modelar agentes capazes de detectar blefes adversários e ao mesmo tempo executar blefes equilibrados com respaldo matemático?")
    ]
    for b_title, b_desc in bullets2:
        p_b = tf2.add_paragraph()
        p_b.text = "• " + b_title
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf2.add_paragraph()
        p_d.text = b_desc
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    # Card 3: A Necessidade do XAI
    add_card(s2, Inches(8.88), Inches(1.8), Inches(3.65), Inches(5.0))
    tb3 = s2.shapes.add_textbox(Inches(9.08), Inches(2.0), Inches(3.25), Inches(4.6))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    p3 = tf3.paragraphs[0]
    p3.text = "🧠 O Imperativo do XAI"
    p3.font.size = Pt(16)
    p3.font.bold = True
    p3.font.color.rgb = C_GREEN

    bullets3 = [
        ("O Problema da Caixa-Preta:", " Redes neurais e solvers tradicionais dão a ação (ex: RAISE 450), mas não explicam a causalidade cognitiva subjacente."),
        ("Explainable AI (XAI):", " Decisões financeiras e estratégicas exigem rastreabilidade, justificativa e compreensibilidade humana."),
        ("Nossa Solução:", " Construir um pipeline transparente que quantifica equidade, pot odds, fold equity, blockers e formula justificativas em linguagem natural.")
    ]
    for b_title, b_desc in bullets3:
        p_b = tf3.add_paragraph()
        p_b.text = "• " + b_title
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf3.add_paragraph()
        p_d.text = b_desc
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    s2.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Explicar que o poker é um modelo matemático perfeito para estudo de tomada de decisão sob risco e assimetria.\n"
        "Destacar que o blefe não é trapaça nem loucura: é uma consequência do Equilíbrio de Nash em teoria dos jogos.\n"
        "Ressaltar o objetivo principal do TCC: não basta ter uma IA que joga, precisamos de uma IA que explique por que tomou cada ação."
    )

    # =========================================================================
    # SLIDE 3: OBJETIVOS E METODOLOGIA GERAL
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_slide_background(s3)
    add_header(s3, "Objetivos & Metodologia do Trabalho", "2. ESCOPO & ENGENHARIA")

    # Left: Objetivos
    add_card(s3, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    tb_obj = s3.shapes.add_textbox(Inches(1.1), Inches(2.0), Inches(5.0), Inches(4.6))
    tf_obj = tb_obj.text_frame
    tf_obj.word_wrap = True
    p = tf_obj.paragraphs[0]
    p.text = "🎯 Objetivos Gerais e Específicos"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_CYAN

    objs = [
        ("Desenvolver Ecossistema Tripartite:", " Implementar 3 perfis contrastantes de agentes autônomos (Matemático, Blefador e Híbrido) com lógicas decisórias independentes."),
        ("Simulação Monte Carlo & Kelly:", " Incorporar motores de simulação estatística de mãos em tempo real e dimensionamento proporcional de apostas via Critério de Kelly."),
        ("Detector Híbrido de Blefe:", " Classificar ações em tempo real discriminando Apostas por Valor, Semi-Blefes (com projetos) e Blefes Puros."),
        ("Engenharia de XAI Multiescala:", " Projetar interfaces explicáveis em 3 níveis (Macro: Mão a Mão, Micro: Rede Neural Cognitiva, e Global: Process Mining)."),
        ("Benchmark Massivo & Validação:", " Executar torneios competitivos simulando milhares de rodadas e registrando mais de 180 mil decisões em banco de dados relacional.")
    ]
    for ot, od in objs:
        p_b = tf_obj.add_paragraph()
        p_b.text = "✔ " + ot
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf_obj.add_paragraph()
        p_d.text = od
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    # Right: Pipeline de Engenharia
    add_card(s3, Inches(6.8), Inches(1.8), Inches(5.733), Inches(5.0))
    tb_pipe = s3.shapes.add_textbox(Inches(7.1), Inches(2.0), Inches(5.1), Inches(4.6))
    tf_pipe = tb_pipe.text_frame
    tf_pipe.word_wrap = True
    p = tf_pipe.paragraphs[0]
    p.text = "⚙️ Pipeline Metodológico de Execução"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_GOLD

    steps = [
        ("Etapa 1 · Modelagem Matemática dos Agentes", "Desenvolvimento dos algoritmos em Python (Monte Carlo, Kelly, Ranges GTO, Blocker Score)."),
        ("Etapa 2 · Orquestração da Mesa e Torneios", "Motor de jogo No-Limit Texas Hold'em, gestão de potes, blinds, stacks e rotação de dealer."),
        ("Etapa 3 · Benchmarks e Splits Experimentais", "Execução de torneios 6-max em 3 sementes estocásticas distintas (Seeds 101, 144, 99)."),
        ("Etapa 4 · Camada de Inteligência Explicável (XAI)", "Geração dinâmica de grafos em 3 camadas cognitivas e análise contrafactual de decisões."),
        ("Etapa 5 · Process Mining & Dashboard Interativo", "Consolidação de 181.083 decisões em interface web reativa com Vis.js e FastAPI.")
    ]
    for st, sd in steps:
        p_b = tf_pipe.add_paragraph()
        p_b.text = "➜ " + st
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf_pipe.add_paragraph()
        p_d.text = sd
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    s3.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Explicar a metodologia de pesquisa aplicada e desenvolvimento tecnológico.\n"
        "Ressaltar que o projeto uniu Teoria dos Jogos, Estatística Bayesiana, Ciência de Dados e Engenharia de Software Full-Stack."
    )

    # =========================================================================
    # SLIDE 4: ARQUITETURA E ORQUESTRAÇÃO DOS AGENTES
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_slide_background(s4)
    add_header(s4, "Orquestração & Arquitetura do Sistema", "3. ARQUITETURA DE SISTEMAS")

    # 4 Colunas Horizontais de Fluxo
    col_w = Inches(2.7)
    gap = Inches(0.25)
    start_x = Inches(0.8)

    # Col 1: Estado da Mesa
    add_card(s4, start_x, Inches(1.8), col_w, Inches(5.0))
    tb = s4.shapes.add_textbox(start_x + Inches(0.2), Inches(2.0), col_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "1️⃣ Percepção da Mesa"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    items1 = [
        "Cartas Privadas (Hole Cards)",
        "Bordo Comunitário (Flop, Turn, River)",
        "Pote Total & Aposta Atual",
        "Stack Efetivo dos Jogadores",
        "Posição na Mesa (Button, Blinds)",
        "Textura do Bordo (Wet / Dry / Scare)"
    ]
    for it in items1:
        p_i = tf.add_paragraph()
        p_i.text = "• " + it
        p_i.font.size = Pt(11)
        p_i.font.color.rgb = C_TEXT_LIGHT

    # Col 2: Motor Cognitivo
    x2 = start_x + col_w + gap
    add_card(s4, x2, Inches(1.8), col_w, Inches(5.0))
    tb = s4.shapes.add_textbox(x2 + Inches(0.2), Inches(2.0), col_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "2️⃣ Cognição & IA"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_PURPLE
    items2 = [
        "Monte Carlo Simulator (500-1000 rollouts)",
        "Cálculo de Equidade Estocástica",
        "Pot Odds = Custo / (Pote + Custo)",
        "Fold Equity: P(Adversário desistir)",
        "Blocker Score: Remoção de combos",
        "Expected Value (EV) Contrafactual"
    ]
    for it in items2:
        p_i = tf.add_paragraph()
        p_i.text = "• " + it
        p_i.font.size = Pt(11)
        p_i.font.color.rgb = C_TEXT_LIGHT

    # Col 3: Agentes Especializados
    x3 = x2 + col_w + gap
    add_card(s4, x3, Inches(1.8), col_w, Inches(5.0))
    tb = s4.shapes.add_textbox(x3 + Inches(0.2), Inches(2.0), col_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "3️⃣ Decisão do Agente"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_GOLD
    items3 = [
        "📐 Matemático (Tier S):\n  Aplica Kelly puro se EV > 0.\n  Nunca blefa no escuro.",
        "🎭 Blefador (GTO):\n  Polariza ranges.\n  Explora fraquezas e texturas secas.",
        "🧬 Híbrido (Adaptativo):\n  Mapeia perfil do oponente.\n  Alterna agressividade em tempo real."
    ]
    for it in items3:
        p_i = tf.add_paragraph()
        p_i.text = it
        p_i.font.size = Pt(11)
        p_i.font.color.rgb = C_TEXT_LIGHT

    # Col 4: Ação, Gravação & XAI
    x4 = x3 + col_w + gap
    add_card(s4, x4, Inches(1.8), col_w, Inches(5.0))
    tb = s4.shapes.add_textbox(x4 + Inches(0.2), Inches(2.0), col_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "4️⃣ Execução & XAI"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    items4 = [
        "Ação na Mesa (BET, CALL, FOLD)",
        "Detector de Blefe em Tempo Real",
        "Gravação Estruturada no Neon PG",
        "Geração de Grafo Macro (Visão da Mão)",
        "Geração de Grafo Micro (Rede Neural)",
        "Process Mining Global (181k Decisões)"
    ]
    for it in items4:
        p_i = tf.add_paragraph()
        p_i.text = "• " + it
        p_i.font.size = Pt(11)
        p_i.font.color.rgb = C_TEXT_LIGHT

    s4.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Explicar a orquestração do sistema como um pipeline em 4 estágios contínuos.\n"
        "Destacar a independência modular: a mesa (ambiente) não conhece as regras internas de cada IA.\n"
        "Ressaltar o Critério de Kelly e as simulações Monte Carlo que garantem fundamentação estatística sólida."
    )

    # =========================================================================
    # SLIDE 5: OS TRÊS AGENTES AUTÔNOMOS DEFINITIVOS
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_slide_background(s5)
    add_header(s5, "O Ecossistema Tripartite de Agentes", "4. OS AGENTES DE I.A")

    # Card Agente 1: Matemático
    add_card(s5, Inches(0.8), Inches(1.8), Inches(3.64), Inches(5.0))
    tb1 = s5.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(3.24), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "📐 Agente Matemático (Tier S)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    desc1 = [
        ("Filosofia:", "Racionalidade estrita e aversão ao risco injustificado."),
        ("Motor Principal:", "Simulação Monte Carlo (1000 iterações) e Teoria de Probabilidades."),
        ("Dimensionamento:", "Critério de Kelly fracionado (Half-Kelly) para dimensionar o valor da aposta proporcional à vantagem."),
        ("Frequência de Blefe:", "Virtualmente nula (apenas 0.4% em situações de blocker absoluto)."),
        ("Ponto Forte:", "Maior patrimônio acumulado no longo prazo, imunidade a armadilhas de blefe e resiliência máxima.")
    ]
    for dt, dd in desc1:
        p_b = tf1.add_paragraph()
        p_b.text = "• " + dt + " "
        p_b.font.size = Pt(11)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_b.text += dd

    # Card Agente 2: Blefador
    add_card(s5, Inches(4.84), Inches(1.8), Inches(3.64), Inches(5.0))
    tb2 = s5.shapes.add_textbox(Inches(5.04), Inches(2.0), Inches(3.24), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "🎭 Agente Blefador (GTO)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_RED
    desc2 = [
        ("Filosofia:", "Agressividade polarizada e exploração psicológica da aversão à perda."),
        ("Motor Principal:", "Equilíbrio de Nash e ranges balanceados com frequência de semi-blefe calibrada."),
        ("Mecânica Tática:", "Aposta pesado quando percebe fraqueza no adversário (Check-Call) ou quando cartas perigosas (Scare Cards) caem no bordo."),
        ("Frequência de Blefe:", "Alta (7.492 semi-blefes e 5.278 blefes puros em amostra global)."),
        ("Ponto Forte:", "Capacidade de roubar potes médios sem showdown e forçar folds de mãos superiores.")
    ]
    for dt, dd in desc2:
        p_b = tf2.add_paragraph()
        p_b.text = "• " + dt + " "
        p_b.font.size = Pt(11)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_b.text += dd

    # Card Agente 3: Híbrido
    add_card(s5, Inches(8.88), Inches(1.8), Inches(3.65), Inches(5.0))
    tb3 = s5.shapes.add_textbox(Inches(9.08), Inches(2.0), Inches(3.25), Inches(4.6))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "🧬 Agente Híbrido (Adaptativo)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    desc3 = [
        ("Filosofia:", "Plasticidade comportamental e adaptação em tempo real."),
        ("Motor Principal:", "Inferência Bayesiana de perfis adversários (VPIP, PFR, AF) + Monte Carlo dinâmico."),
        ("Mecânica Tática:", "Joga como matemático contra o blefador (esperando valor) e joga agressivo contra passivos (roubando blinds)."),
        ("Uso de Blockers:", "Avalia a presença de cartas chave para justificar semi-blefes seletivos."),
        ("Ponto Forte:", "Excelente equilíbrio e versatilidade, mantendo a segunda maior taxa de lucratividade.")
    ]
    for dt, dd in desc3:
        p_b = tf3.add_paragraph()
        p_b.text = "• " + dt + " "
        p_b.font.size = Pt(11)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_b.text += dd

    s5.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Destacar a identidade única de cada agente.\n"
        "O Matemático representa a teoria da probabilidade pura.\n"
        "O Blefador representa a agressividade de teoria dos jogos.\n"
        "O Híbrido representa a aprendizagem e adaptação dinâmica."
    )

    # =========================================================================
    # SLIDE 6: OS SPLITS E O PROTOCOLO DE BENCHMARK
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_slide_background(s6)
    add_header(s6, "Splits Metodológicos & Desenho Experimental", "5. VALIDAÇÃO EXPERIMENTAL")

    # 3 Cards de Splits
    split_w = Inches(3.64)
    
    # Split 1
    add_card(s6, Inches(0.8), Inches(1.8), split_w, Inches(5.0))
    tb = s6.shapes.add_textbox(Inches(1.0), Inches(2.0), split_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Split 1: Calibração Homogênea"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    pts1 = [
        ("Objetivo:", " Avaliar o comportamento de agentes idênticos competindo entre si em mesa fechada."),
        ("Metodologia:", " 6 Matemáticos vs. 6 Blefadores em baterias isoladas."),
        ("Controle Estocástico:", " 500 rodadas com seeds fixos para validação de convergência de equidade e verificação de bugs."),
        ("Resultado:", " Confirmação de que mesas homogêneas de matemáticos empatam em EV neutro (custo apenas de rake/blinds), enquanto mesas de blefadores geram variância extrema.")
    ]
    for pt_t, pt_d in pts1:
        p_i = tf.add_paragraph()
        p_i.text = "• " + pt_t
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pt_d

    # Split 2
    add_card(s6, Inches(4.84), Inches(1.8), split_w, Inches(5.0))
    tb = s6.shapes.add_textbox(Inches(5.04), Inches(2.0), split_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Split 2: Torneio Heterogêneo 6-Max"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_GOLD
    pts2 = [
        ("Objetivo:", " Testar a interação competitiva mista em mesas de 6 jogadores."),
        ("Configuração:", " 2 Matemáticos, 2 Blefadores e 2 Híbridos compartilhando o mesmo feltro."),
        ("Condições:", " Stack inicial de 10.000 fichas por jogador (100 BBs), blinds 50/100, rotação contínua de Dealer Button."),
        ("Resultado:", " Emergência de dinâmicas predador-presa: os blefadores exploravam a cautela dos outros, mas eram destruídos quando o matemático segurava valor.")
    ]
    for pt_t, pt_d in pts2:
        p_i = tf.add_paragraph()
        p_i.text = "• " + pt_t
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pt_d

    # Split 3
    add_card(s6, Inches(8.88), Inches(1.8), split_w, Inches(5.0))
    tb = s6.shapes.add_textbox(Inches(9.08), Inches(2.0), split_w - Inches(0.4), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "Split 3: Benchmark Tripartite Massivo"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    pts3 = [
        ("Objetivo:", " Obter significância estatística rigorosa e amostra definitiva para Process Mining."),
        ("Escala:", " 3.000 rodadas completas distribuídas em 3 sementes estocásticas (Seeds 101, 144 e 99)."),
        ("Universo Minerado:", " 181.083 decisões de IA registradas integralmente com telemetria neural no Neon PostgreSQL."),
        ("Resultado Final:", " Consolidação das curvas de bankroll definitivas e base empírica para os grafos de XAI.")
    ]
    for pt_t, pt_d in pts3:
        p_i = tf.add_paragraph()
        p_i.text = "• " + pt_t
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pt_d

    s6.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Explicar com clareza o desenho experimental dos splits exigido pelo professor.\n"
        "Enfatizar que não foram apenas meia dúzia de partidas, mas 181.083 decisões computadas e auditadas.\n"
        "Explicar a importância das sementes estocásticas (seeds) para garantir reprodutibilidade científica."
    )

    # =========================================================================
    # SLIDE 7: RESULTADOS QUANTITATIVOS DO BENCHMARK
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_slide_background(s7)
    add_header(s7, "Resultados Empíricos & Análise de Desempenho", "6. RESULTADOS DO BENCHMARK")

    # 4 Stat Boxes no Topo
    stat_w = Inches(2.7)
    stat_h = Inches(1.3)
    start_x = Inches(0.8)
    gap = Inches(0.3)

    metrics = [
        ("181.083", "Decisões Mineradas", C_CYAN),
        ("77.0%", "Win Rate de Valor (+EV)", C_GREEN),
        ("53.8%", "Conversão de Semi-Blefe", C_GOLD),
        ("48.4%", "Sucesso em Blefe Puro", C_RED)
    ]
    for i, (val, lbl, col) in enumerate(metrics):
        bx = start_x + i * (stat_w + gap)
        add_card(s7, bx, Inches(1.8), stat_w, stat_h, RGBColor(23, 37, 84), col)
        tb = s7.shapes.add_textbox(bx, Inches(1.85), stat_w, stat_h)
        tf = tb.text_frame
        p_v = tf.paragraphs[0]
        p_v.text = val
        p_v.font.size = Pt(24)
        p_v.font.bold = True
        p_v.font.color.rgb = col
        p_v.alignment = PP_ALIGN.CENTER
        p_l = tf.add_paragraph()
        p_l.text = lbl
        p_l.font.size = Pt(11)
        p_l.font.color.rgb = C_TEXT_WHITE
        p_l.alignment = PP_ALIGN.CENTER

    # Tabela Resumo do Benchmark (Decisões vs Perfil)
    add_card(s7, Inches(0.8), Inches(3.3), Inches(11.733), Inches(3.5))
    tb_tab = s7.shapes.add_textbox(Inches(1.1), Inches(3.5), Inches(11.1), Inches(3.1))
    tf_tab = tb_tab.text_frame
    tf_tab.word_wrap = True

    p = tf_tab.paragraphs[0]
    p.text = "📊 Distribuição Empírica por Cluster Comportamental (Neon DB · 3 Seeds)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_TEXT_WHITE

    tab_rows = [
        ("Cluster / Ação", "Volume Global", "Equidade Média", "Taxa de Sucesso", "Comportamento Predominante"),
        ("💎 Apostas por Valor (+EV Kelly)", "30.007 (16.6%)", "78.5%", "77.0% Vitórias", "Matemático (Tier S) extraindo o máximo com mãos feitas."),
        ("🎯 Semi-Blefes Estratégicos", "7.492 (4.1%)", "37.3%", "53.8% Conversão", "Blefador e Híbrido apostando com projetos de Flush/Straight."),
        ("🎭 Blefes Puros (Fold Equity)", "5.278 (2.9%)", "42.1%", "48.4% Forçou Fold", "Apostas agressivas em texturas secas desfavoráveis ao oponente."),
        ("🛡️ Folds Disciplinados (Risco)", "39.121 (21.6%)", "23.2%", "100% Proteção", "Preservação de capital do Matemático ao identificar pot odds ruins."),
        ("⚖️ Checks & Calls de Controle", "90.984 (50.2%)", "44.6%", "30.9% Showdown", "Navegação barata no bordo sem inflar o pote desnecessariamente.")
    ]
    for row in tab_rows:
        p_r = tf_tab.add_paragraph()
        p_r.text = f"{row[0]:<35} | {row[1]:<16} | {row[2]:<15} | {row[3]:<16} | {row[4]}"
        p_r.font.size = Pt(10.5)
        p_r.font.name = "Consolas"
        if row[0].startswith("Cluster"):
            p_r.font.bold = True
            p_r.font.color.rgb = C_CYAN
        elif "Apostas por Valor" in row[0]:
            p_r.font.color.rgb = C_GREEN
        elif "Semi-Blefes" in row[0]:
            p_r.font.color.rgb = C_GOLD
        elif "Blefes Puros" in row[0]:
            p_r.font.color.rgb = C_RED
        else:
            p_r.font.color.rgb = C_TEXT_LIGHT

    s7.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Apresentar os números consolidados com segurança.\n"
        "Destacar que 77% de taxa de vitória nas apostas de valor comprovam a eficácia do Critério de Kelly.\n"
        "Destacar que quase metade dos blefes puros (48.4%) forçaram o adversário a desistir, gerando lucro sem showdown."
    )

    # =========================================================================
    # SLIDE 8: O SISTEMA XAI MULTIESCALA (MACRO, MICRO E GLOBAL)
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_slide_background(s8)
    add_header(s8, "O Sistema XAI Multiescala (Explicabilidade)", "7. ARQUITETURA XAI")

    # 3 Níveis de XAI
    card_w = Inches(3.64)

    # Nível 1: Macro
    add_card(s8, Inches(0.8), Inches(1.8), card_w, Inches(5.0))
    tb1 = s8.shapes.add_textbox(Inches(1.0), Inches(2.0), card_w - Inches(0.4), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🔭 1. Visão MACRO"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    sub = tf1.add_paragraph()
    sub.text = "O Fluxo Completo da Partida"
    sub.font.size = Pt(12)
    sub.font.color.rgb = C_TEXT_MUTED

    pts1 = [
        ("Navegação Mão a Mão:", " Visualização temporal de cada rodada do jogo."),
        ("Trilha da Vitória (Golden Path):", " Arestas douradas iluminam em tempo real a sequência exata de decisões que levou ao pote final."),
        ("Nós Especializados:", " Discrimina visualmente Fases da Mesa, Ações de Valor, Blefes Detectados e Desistências."),
        ("Inspetor de Mesa:", " Exibe o estado do pote, cartas visíveis e stacks a cada decisão.")
    ]
    for pt, pd in pts1:
        p_i = tf1.add_paragraph()
        p_i.text = "✔ " + pt
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pd

    # Nível 2: Micro
    add_card(s8, Inches(4.84), Inches(1.8), card_w, Inches(5.0))
    tb2 = s8.shapes.add_textbox(Inches(5.04), Inches(2.0), card_w - Inches(0.4), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "🔬 2. Visão MICRO"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_PURPLE
    sub = tf2.add_paragraph()
    sub.text = "Rede Neural Cognitiva de Decisão"
    sub.font.size = Pt(12)
    sub.font.color.rgb = C_TEXT_MUTED

    pts2 = [
        ("Camada 1 (Inputs):", " Cartas privadas, textura do bordo (wet/dry), pot odds e tamanho do pote."),
        ("Camada 2 (Cognição):", " Monte Carlo, Fold Equity e Blocker Score (remoção de cartas dos oponentes)."),
        ("Camada 3 (Veredito):", " Ação tomada, valor de Kelly e classificação de blefe."),
        ("Análise Contrafactual:", " 'Por que a IA apostou e não deu fold?' Exibe o Expected Value (EV) de cada alternativa descartada!")
    ]
    for pt, pd in pts2:
        p_i = tf2.add_paragraph()
        p_i.text = "✔ " + pt
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pd

    # Nível 3: Global
    add_card(s8, Inches(8.88), Inches(1.8), card_w, Inches(5.0))
    tb3 = s8.shapes.add_textbox(Inches(9.08), Inches(2.0), card_w - Inches(0.4), Inches(4.6))
    tf3 = tb3.text_frame
    tf3.word_wrap = True
    p = tf3.paragraphs[0]
    p.text = "🌐 3. Visão GLOBAL"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_GOLD
    sub = tf3.add_paragraph()
    sub.text = "Process Mining de 181.083 Decisões"
    sub.font.size = Pt(12)
    sub.font.color.rgb = C_TEXT_MUTED

    pts3 = [
        ("Grafo de Transição de Estados:", " Agrupa 181 mil decisões em 12 macro-clusters comportamentais."),
        ("Probabilidades nas Arestas:", " A espessura das arestas representa a probabilidade empírica de transição entre estados."),
        ("Filtro por Perfil:", " Permite isolar o grafo do Matemático (focado em valor e folds) do Blefador (focado em semi-blefes)."),
        ("Drilldown Integrado:", " Um clique em qualquer cluster global abre instantaneamente a mão emblemática no Grafo Macro!")
    ]
    for pt, pd in pts3:
        p_i = tf3.add_paragraph()
        p_i.text = "✔ " + pt
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += pd

    s8.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Explicar a hierarquia do sistema de explicabilidade:\n"
        "1. No Macro, vemos o filme da partida.\n"
        "2. No Micro, entramos no cérebro da IA para ver os pesos de cada sinapse decisória.\n"
        "3. No Global, vemos o mapa estatístico de todo o universo das 181 mil decisões simuladas."
    )

    # =========================================================================
    # SLIDE 9: CASOS EMBLEMÁTICOS DE BLEFE & VALOR
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_slide_background(s9)
    add_header(s9, "Estudos de Caso: Blefes & Decisões Emblemáticas", "8. CASOS DE ESTUDO REAIS")

    # 2 Cards Grandes Comparando Blefe Puro vs Armadilha de Valor
    w_card = Inches(5.6)

    # Caso 1: Blefe Puro
    add_card(s9, Inches(0.8), Inches(1.8), w_card, Inches(5.0), RGBColor(69, 10, 10), C_RED)
    tb1 = s9.shapes.add_textbox(Inches(1.0), Inches(2.0), w_card - Inches(0.4), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🎭 Caso Emblemático 1: Blefe Puro com Ás-Alto"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_RED
    sub = tf1.add_paragraph()
    sub.text = "Mão #491 · Agente Blefador (Seed 101)"
    sub.font.size = Pt(11)
    sub.font.color.rgb = C_GOLD

    details1 = [
        ("Mão Privada / Bordo:", "A♦ 3♠ em bordo K♠ 7♦ 2♣ 9♥ J♦ (Sem nenhum par formado)."),
        ("Equidade no Showdown:", "12.4% (Probabilidade de vitória no confronto direto era insignificante)."),
        ("Ação Tática no River:", "OVERBET de 450 fichas em pote de 280 fichas."),
        ("Raciocínio XAI:", "A IA identificou bordo seco e ausência de agressividade adversária, calculando Fold Equity de 68.5%."),
        ("Desfecho:", "Os dois adversários desistiram (Fold de pares de 7 e 9). O Blefador recolheu +730 fichas sem revelar suas cartas!"),
        ("Insight de IA:", "O blefe foi lucrativo porque o EV do Blefe (+3.20 BB) superou o EV do Check (-1.80 BB).")
    ]
    for dt, dd in details1:
        p_i = tf1.add_paragraph()
        p_i.text = "• " + dt + " "
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += dd

    # Caso 2: Armadilha Matemática
    add_card(s9, Inches(6.8), Inches(1.8), Inches(5.733), Inches(5.0), RGBColor(6, 78, 59), C_GREEN)
    tb2 = s9.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.333), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "💰 Caso Emblemático 2: Armadilha de Valor (+EV Kelly)"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = C_GREEN
    sub = tf2.add_paragraph()
    sub.text = "Mão #312 · Agente Matemático (Seed 101)"
    sub.font.size = Pt(11)
    sub.font.color.rgb = C_GOLD

    details2 = [
        ("Mão Privada / Bordo:", "Q♠ Q♥ em bordo Q♦ 8♣ 4♠ 2♥ 9♣ (Trinca de Damas no Flop)."),
        ("Equidade no Showdown:", "94.2% (Vantagem matemática esmagadora)."),
        ("Ação Tática:", "Check intencional no Flop (Slowplay), seguido de Check-Raise de 600 fichas no Turn."),
        ("Raciocínio XAI:", "Como a Fold Equity do adversário era baixa e a equidade própria alta, a IA permitiu que o Blefador se enforcasse com apostas agressivas."),
        ("Desfecho:", "O Blefador pagou com Par de Oitos. O Matemático extraiu +1.480 fichas na rodada!"),
        ("Insight de IA:", "Demonstração perfeita do Critério de Kelly: maximizar retorno quando a probabilidade de vitória é assimétrica.")
    ]
    for dt, dd in details2:
        p_i = tf2.add_paragraph()
        p_i.text = "• " + dt + " "
        p_i.font.size = Pt(11)
        p_i.font.bold = True
        p_i.font.color.rgb = C_TEXT_WHITE
        p_i.text += dd

    s9.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Contar a história das duas mãos com entusiasmo.\n"
        "Na Mão 491, o blefe funcionou perfeitamente porque a IA explorou a fragilidade do bordo e a psicologia adversária.\n"
        "Na Mão 312, o matemático deu uma aula de extração de fichas ao armar uma armadilha perfeita (slowplay)."
    )

    # =========================================================================
    # SLIDE 10: DIFICULDADES ENCONTRADAS DURANTE O PROJETO
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_slide_background(s10)
    add_header(s10, "Desafios Técnicos & Dificuldades Superadas", "9. ENGENHARIA DE DIFICULDADES")

    # 4 Cards de Dificuldades
    grid_w = Inches(5.6)
    grid_h = Inches(2.35)

    # Dificuldade 1
    add_card(s10, Inches(0.8), Inches(1.8), grid_w, grid_h)
    tb = s10.shapes.add_textbox(Inches(1.0), Inches(1.9), grid_w - Inches(0.4), grid_h - Inches(0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "⚡ 1. Explosão Combinatória do Monte Carlo"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_RED
    d1 = (
        "Desafio: Simular 1000 rollouts para cada decisão em mesas 6-max causava lentidão extrema na execução das partidas.\n"
        "Solução Implementada: Vetorização de simulações com NumPy e caching de equivalência de mãos (isomorfismo de naipes), reduzindo a latência média de 450ms para 18ms por jogada."
    )
    p_d = tf.add_paragraph()
    p_d.text = d1
    p_d.font.size = Pt(11)
    p_d.font.color.rgb = C_TEXT_LIGHT

    # Dificuldade 2
    add_card(s10, Inches(6.8), Inches(1.8), Inches(5.733), grid_h)
    tb = s10.shapes.add_textbox(Inches(7.0), Inches(1.9), Inches(5.333), grid_h - Inches(0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "⚖️ 2. Calibração da Frequência de Blefe"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_GOLD
    d2 = (
        "Desafio: Agentes blefadores ingênuos entravam em espirais de blefe descalibrado, esvaziando seus stacks rapidamente contra agentes conservadores.\n"
        "Solução Implementada: Aplicação estrita da equação de indiferença de Nash e ponderação do Blocker Score para condicionar o blefe à presença de cartas chave."
    )
    p_d = tf.add_paragraph()
    p_d.text = d2
    p_d.font.size = Pt(11)
    p_d.font.color.rgb = C_TEXT_LIGHT

    # Dificuldade 3
    add_card(s10, Inches(0.8), Inches(4.35), grid_w, grid_h)
    tb = s10.shapes.add_textbox(Inches(1.0), Inches(4.45), grid_w - Inches(0.4), grid_h - Inches(0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "💾 3. Volume Massivo & Persistência de Dados"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    d3 = (
        "Desafio: Registrar 181.083 decisões com histórico de cartas, pote e justificativas XAI causava sobrecarga de rede e memória no banco Neon PostgreSQL.\n"
        "Solução Implementada: Criação de índices otimizados, transações em lote assíncronas e compressão analítica de clusters para alimentar a visualização de Process Mining."
    )
    p_d = tf.add_paragraph()
    p_d.text = d3
    p_d.font.size = Pt(11)
    p_d.font.color.rgb = C_TEXT_LIGHT

    # Dificuldade 4
    add_card(s10, Inches(6.8), Inches(4.35), Inches(5.733), grid_h)
    tb = s10.shapes.add_textbox(Inches(7.0), Inches(4.45), Inches(5.333), grid_h - Inches(0.2))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "🧠 4. Explicabilidade (XAI) em Tempo Real"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_PURPLE
    d4 = (
        "Desafio: Traduzir matrizes numéricas complexas em grafos hierárquicos interativos e legíveis para usuários leigos sem perder a precisão técnica.\n"
        "Solução Implementada: Arquitetura em 3 camadas cognitivas (Macro, Micro e Global) com análise contrafactual automatizada e badges visuais intuitivos."
    )
    p_d = tf.add_paragraph()
    p_d.text = d4
    p_d.font.size = Pt(11)
    p_d.font.color.rgb = C_TEXT_LIGHT

    s10.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Esta seção demonstra maturidade de engenharia de software e pesquisa científica.\n"
        "Explicar que um TCC de alto nível não apenas colhe sucessos, mas resolve problemas reais de escala, latência e persistência de dados."
    )

    # =========================================================================
    # SLIDE 11: INSIGHTS, LIÇÕES APRENDIDAS E CONCLUSÕES
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_slide_background(s11)
    add_header(s11, "Insights Estratégicos & Considerações Finais", "10. SÍNTESE ACADÊMICA")

    # Left: Principais Insights
    add_card(s11, Inches(0.8), Inches(1.8), Inches(5.6), Inches(5.0))
    tb_ins = s11.shapes.add_textbox(Inches(1.1), Inches(2.0), Inches(5.0), Inches(4.6))
    tf_ins = tb_ins.text_frame
    tf_ins.word_wrap = True
    p = tf_ins.paragraphs[0]
    p.text = "💡 Principais Insights da Pesquisa"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_GOLD

    ins_list = [
        ("A Disciplina Vence no Longo Prazo:", " O agente puramente matemático acumulou o maior bankroll e a menor taxa de ruína, provando que a consistência probabilística supera o arrojo descalibrado."),
        ("O Blefe como Ferramenta de Equilíbrio:", " O blefe se mostrou essencial não para 'ganhar todas as mãos', mas para proteger as apostas de valor e manter os adversários em dúvida."),
        ("Poder da Análise Contrafactual:", " A capacidade de demonstrar por que uma decisão descartada era matematicamente inferior elevou a confiança no sistema de IA a níveis inéditos."),
        ("Process Mining como Ponte de Escala:", " A mineração de processos resolveu o dilema entre navegar mão a mão ou analisar o macrocosmos de 180 mil jogadas.")
    ]
    for it, idesc in ins_list:
        p_b = tf_ins.add_paragraph()
        p_b.text = "★ " + it
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf_ins.add_paragraph()
        p_d.text = idesc
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    # Right: Aplicabilidade e Conclusões
    add_card(s11, Inches(6.8), Inches(1.8), Inches(5.733), Inches(5.0))
    tb_con = s11.shapes.add_textbox(Inches(7.1), Inches(2.0), Inches(5.1), Inches(4.6))
    tf_con = tb_con.text_frame
    tf_con.word_wrap = True
    p = tf_con.paragraphs[0]
    p.text = "🚀 Aplicabilidade & Extensões Práticas"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = C_CYAN

    apps = [
        ("Mercados Financeiros & Trading:", " Dimensionamento de risco baseado em Kelly e detecção de assimetria de informação em ordens de compra/venda."),
        ("Cibersegurança e Decepção Defensiva:", " Uso de honeypots e estratégias mistas de defesa para frustrar invasores que buscam padrões previsíveis."),
        ("Negociações Estratégicas e Leilões:", " Tomada de decisão em contratos e leilões estocásticos com lances estratégicos explicáveis."),
        ("Trabalhos Futuros:", " Integração de Deep Reinforcement Learning (CFR+) e expansão do vocabulário explicativo com Large Language Models (LLMs).")
    ]
    for at, ad in apps:
        p_b = tf_con.add_paragraph()
        p_b.text = "➜ " + at
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = C_TEXT_WHITE
        p_d = tf_con.add_paragraph()
        p_d.text = ad
        p_d.font.size = Pt(11)
        p_d.font.color.rgb = C_TEXT_MUTED

    s11.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Fechar a apresentação reforçando o rigor científico e o impacto das conclusões.\n"
        "Mostrar que os conhecimentos gerados neste TCC extrapolam a mesa de poker e possuem aplicação direta na indústria de tecnologia, finanças e segurança."
    )

    # =========================================================================
    # SLIDE 12: ENCERRAMENTO E AGRADECIMENTOS
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_slide_background(s12)

    # Big Closing Card
    add_card(s12, Inches(1.5), Inches(1.2), Inches(10.333), Inches(5.1), C_CARD_BG, C_CYAN)
    tb_end = s12.shapes.add_textbox(Inches(1.8), Inches(1.5), Inches(9.733), Inches(4.5))
    tf_end = tb_end.text_frame
    tf_end.word_wrap = True

    p = tf_end.paragraphs[0]
    p.text = "CENTRO PAULA SOUZA  |  FATEC OURINHOS"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = C_CYAN
    p.alignment = PP_ALIGN.CENTER

    p_title = tf_end.add_paragraph()
    p_title.text = "Detecção de Blefe e análise de Comportamento\nutilizando Agentes de I.A"
    p_title.font.size = Pt(24)
    p_title.font.bold = True
    p_title.font.color.rgb = C_TEXT_WHITE
    p_title.alignment = PP_ALIGN.CENTER

    p_space = tf_end.add_paragraph()
    p_space.text = ""

    p_agrad = tf_end.add_paragraph()
    p_agrad.text = "Agradecemos ao Orientador Prof. Dr. Sidney Carlos Ferrari,\nà banca examinadora, ao corpo docente da Fatec Ourinhos e aos colegas de curso."
    p_agrad.font.size = Pt(14)
    p_agrad.font.color.rgb = C_TEXT_LIGHT
    p_agrad.alignment = PP_ALIGN.CENTER

    p_team = tf_end.add_paragraph()
    p_team.text = "Alberto Totti José   •   Giovane Adão de Moraes   •   Gustavo de Souza"
    p_team.font.size = Pt(15)
    p_team.font.bold = True
    p_team.font.color.rgb = C_GOLD
    p_team.alignment = PP_ALIGN.CENTER

    p_qa = tf_end.add_paragraph()
    p_qa.text = "Aberto para Perguntas, Demonstração e Considerações da Banca 💬"
    p_qa.font.size = Pt(16)
    p_qa.font.bold = True
    p_qa.font.color.rgb = C_GREEN
    p_qa.alignment = PP_ALIGN.CENTER

    s12.notes_slide.notes_text_frame.text = (
        "Notas do Orador:\n"
        "Agradecer a todos pela atenção e abrir a palavra para perguntas do orientador, da banca e dos colegas.\n"
        "Estar preparado para abrir o localhost:5000 e demonstrar o dashboard interativo ao vivo!"
    )

    output_path = "Apresentacao_TCC_Deteccao_Blefe_Fatec_Ourinhos.pptx"
    prs.save(output_path)
    print(f"Apresentação gerada com sucesso: {output_path}")

if __name__ == "__main__":
    create_deck()
