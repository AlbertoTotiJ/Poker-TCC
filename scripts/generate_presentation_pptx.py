"""Script de Geração da Apresentação em PowerPoint (.pptx) para a Aula / Prévia de Defesa do TCC.

Instituição: Centro Paula Souza - Fatec Ourinhos
Título: Detecção de Blefe e Análise de Comportamento utilizando Agentes de I.A
Autores: Alberto Totti José, Giovane Adão de Moraes, Gustavo de Souza
Orientador: Prof. Dr. Sidney Carlos Ferrari

Gera uma apresentação completa widescreen 16:9 de 16 slides incluindo:
- Capa com logos oficiais do CPS e Fatec Ourinhos.
- Arquitetura de agentes, motor e equipe no Maestri.
- Simulações massivas nas Seeds 101, 144 e 99 (181.083 decisões).
- Splits estratificados (Treino 70%, Validação 15%, Teste Cego 15%).
- Benchmark dos 4 modelos supervisionados (RF, HistGradientBoosting, MLP, Regressão Logística).
- 4 Gráficos científicos em alta resolução (300 DPI) embutidos.
- Dificuldades enfrentadas, soluções de engenharia e insights científicos.
"""

from pathlib import Path
import sys

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = _ROOT / "data"
PLOTS_DIR = DATA_DIR / "04_ml_sprint4_consolidado" / "plots"
OUTPUT_PPTX = _ROOT / "Apresentacao_Poker_TCC_Fatec.pptx"
OUTPUT_PPTX_DATA = DATA_DIR / "Apresentacao_Poker_TCC_Fatec.pptx"

# Cores da Paleta Institucional e Tecnológica
COLOR_PRIMARY_DARK = RGBColor(13, 71, 161)     # Azul Escuro Profundo #0D47A1
COLOR_PRIMARY_BLUE = RGBColor(21, 101, 192)    # Azul Real #1565C0
COLOR_ACCENT_RED = RGBColor(183, 28, 28)       # Vermelho Fatec/CPS #B71C1C
COLOR_DARK_TEXT = RGBColor(33, 33, 33)         # Texto Escuro #212121
COLOR_MUTED_TEXT = RGBColor(100, 116, 139)     # Texto Suave #64748B
COLOR_LIGHT_BG = RGBColor(248, 249, 250)       # Fundo Leve #F8F9FA
COLOR_CARD_BG = RGBColor(255, 255, 255)        # Branco Card
COLOR_CARD_BORDER = RGBColor(226, 232, 240)    # Borda Card
COLOR_GREEN_SUCCESS = RGBColor(46, 125, 50)    # Verde Sucesso #2E7D32
COLOR_CARD_BLUE_BG = RGBColor(237, 244, 255)   # Fundo Azul Claro


def create_header(slide, title_text, category_text="CENTRO PAULA SOUZA • FATEC OURINHOS — TCC EM IA"):
    """Cria cabeçalho padronizado e elegante em slides internos."""
    # Faixa superior sutil
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.1))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p_cat = tf.paragraphs[0]
    p_cat.text = category_text.upper()
    p_cat.font.size = Pt(9.5)
    p_cat.font.bold = True
    p_cat.font.color.rgb = COLOR_ACCENT_RED

    p_title = tf.add_paragraph()
    p_title.text = title_text
    p_title.font.size = Pt(22)
    p_title.font.bold = True
    p_title.font.color.rgb = COLOR_PRIMARY_DARK
    p_title.space_before = Pt(3)

    # Linha divisória fina
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.7), Inches(0.02))
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_CARD_BORDER
    line.line.color.rgb = COLOR_CARD_BORDER

    # Logo no canto superior direito
    logo_path = DATA_DIR / "logo_cps_fatec.png"
    if logo_path.exists():
        slide.shapes.add_picture(str(logo_path), Inches(10.5), Inches(0.35), height=Inches(0.95))


def add_card(slide, left, top, width, height, bg_color=COLOR_CARD_BG, border_color=COLOR_CARD_BORDER):
    """Adiciona um card retangular com cantos arredondados de fundo."""
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg_color
    card.line.color.rgb = border_color
    card.line.width = Pt(1)
    return card


def build_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: CAPA OFICIAL
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)

    # Faixa lateral decorativa azul
    strip = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.5), Inches(7.5))
    strip.fill.solid()
    strip.fill.fore_color.rgb = COLOR_PRIMARY_DARK
    strip.line.fill.background()

    strip2 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(0), Inches(0.15), Inches(7.5))
    strip2.fill.solid()
    strip2.fill.fore_color.rgb = COLOR_ACCENT_RED
    strip2.line.fill.background()

    # Inserção do Logo CPS / Fatec Ourinhos
    logo_path = DATA_DIR / "logo_cps_fatec.png"
    if logo_path.exists():
        slide1.shapes.add_picture(str(logo_path), Inches(1.2), Inches(0.8), height=Inches(1.2))

    # Título Principal
    t_box = slide1.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11.2), Inches(2.3))
    tf1 = t_box.text_frame
    tf1.word_wrap = True

    p0 = tf1.paragraphs[0]
    p0.text = "TRABALHO DE CONCLUSÃO DE CURSO — INTELIGÊNCIA ARTIFICIAL"
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_ACCENT_RED

    p1 = tf1.add_paragraph()
    p1.text = "Detecção de Blefe e Análise de Comportamento\nutilizando Agentes de I.A"
    p1.font.size = Pt(32)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_PRIMARY_DARK
    p1.space_before = Pt(8)

    p2 = tf1.add_paragraph()
    p2.text = "Modelagem Multiagente, Simulações Massivas e Machine Learning Supervisionado no Texas Hold'em Poker"
    p2.font.size = Pt(14)
    p2.font.color.rgb = COLOR_MUTED_TEXT
    p2.space_before = Pt(10)

    # Card com Autores e Orientador
    add_card(slide1, Inches(1.2), Inches(4.8), Inches(11.0), Inches(1.8), bg_color=COLOR_LIGHT_BG)
    info_box = slide1.shapes.add_textbox(Inches(1.5), Inches(4.9), Inches(10.4), Inches(1.6))
    tfi = info_box.text_frame
    tfi.word_wrap = True

    pi1 = tfi.paragraphs[0]
    pi1.text = "EQUIPE DE DESENVOLVEDORES (DISCENTES):"
    pi1.font.size = Pt(10)
    pi1.font.bold = True
    pi1.font.color.rgb = COLOR_PRIMARY_DARK

    pi2 = tfi.add_paragraph()
    pi2.text = "• Alberto Totti José   |   • Giovane Adão de Moraes   |   • Gustavo de Souza"
    pi2.font.size = Pt(13)
    pi2.font.bold = True
    pi2.font.color.rgb = COLOR_DARK_TEXT
    pi2.space_before = Pt(4)

    pi3 = tfi.add_paragraph()
    pi3.text = "ORIENTAÇÃO ACADÊMICA: Prof. Dr. Sidney Carlos Ferrari"
    pi3.font.size = Pt(11.5)
    pi3.font.bold = True
    pi3.font.color.rgb = COLOR_ACCENT_RED
    pi3.space_before = Pt(8)

    pi4 = tfi.add_paragraph()
    pi4.text = "Faculdade de Tecnologia de Ourinhos (Fatec) — Centro Estadual de Educação Tecnológica Paula Souza"
    pi4.font.size = Pt(9.5)
    pi4.font.color.rgb = COLOR_MUTED_TEXT
    pi4.space_before = Pt(3)

    # =========================================================================
    # SLIDE 2: CONTEXTO E O PROBLEMA DO BLEFE NO POKER
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    create_header(slide2, "Contexto Científico: O Desafio dos Jogos de Informação Imperfeita")

    # Card 1: Informação Imperfeita
    add_card(slide2, Inches(0.8), Inches(1.8), Inches(3.6), Inches(5.0))
    tb = slide2.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(3.2), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "🃏 O Texas Hold'em Poker"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK
    bullets = [
        "Ao contrário do Xadrez ou Go (jogos determinísticos de informação perfeita), o Poker esconde as cartas fechadas dos adversários.",
        "Existe alto componente estocástico (sorteio aleatório do baralho) e assimetria informacional contínua.",
        "Requer raciocínio probabilístico sob incerteza e modelagem de crenças adversárias."
    ]
    for b in bullets:
        p = tf.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(11)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(8)

    # Card 2: A Natureza do Blefe
    add_card(slide2, Inches(4.8), Inches(1.8), Inches(3.6), Inches(5.0))
    tb = slide2.shapes.add_textbox(Inches(5.0), Inches(2.0), Inches(3.2), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "🎭 A Teoria do Blefe"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_RED
    bullets = [
        "Blefar não é 'apostar por sorte': segundo a Teoria dos Jogos (John von Neumann), o blefe é obrigatório para atingir o Equilíbrio de Nash.",
        "Se um jogador nunca blefa, seus oponentes foldam facilmente sempre que ele aposta forte (tornando-o explorável).",
        "Porém, se blefar em excesso, é punido severamente por jogadores conservadores ('Sheriffs')."
    ]
    for b in bullets:
        p = tf.add_paragraph()
        p.text = "• " + b
        p.font.size = Pt(11)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(8)

    # Card 3: A Pergunta de Pesquisa
    add_card(slide2, Inches(8.8), Inches(1.8), Inches(3.7), Inches(5.0), bg_color=COLOR_CARD_BLUE_BG, border_color=COLOR_PRIMARY_BLUE)
    tb = slide2.shapes.add_textbox(Inches(9.0), Inches(2.0), Inches(3.3), Inches(4.6))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "🎯 A Pergunta Central do TCC"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    p_quote = tf.add_paragraph()
    p_quote.text = "“É possível prever e classificar com alta precisão se uma aposta é um blefe antes do showdown, utilizando estritamente dados públicos da mesa e sem violar as cartas fechadas do adversário?”"
    p_quote.font.size = Pt(12)
    p_quote.font.italic = True
    p_quote.font.bold = True
    p_quote.font.color.rgb = COLOR_PRIMARY_BLUE
    p_quote.space_before = Pt(12)

    p_sub = tf.add_paragraph()
    p_sub.text = "✓ Demonstração experimental e empírica com mais de 181 mil decisões gravadas e validadas por Machine Learning."
    p_sub.font.size = Pt(11)
    p_sub.font.bold = True
    p_sub.font.color.rgb = COLOR_GREEN_SUCCESS
    p_sub.space_before = Pt(14)

    # =========================================================================
    # SLIDE 3: OBJETIVOS E METODOLOGIA GERAL
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    create_header(slide3, "Objetivos e Escopo do Trabalho")

    objs = [
        ("1. Modelagem Multiagente Autônoma", "Construir e calibrar 3 arquétipos fundamentais de agentes (Matemático, Blefador e Híbrido) sem vícios ou ações ilegais, simulando confrontos com tomada de decisão determinística e estocástica.", COLOR_PRIMARY_BLUE),
        ("2. Simulações Massivas e Coleta de Dados", "Executar 42 ensaios controlados por 3 seeds pseudoaleatórias (101, 144, 99) em formatos 9-Max, Heads-Up e Estresse 1v5, capturando telemetria detalhada de mais de 181.000 decisões.", COLOR_PRIMARY_DARK),
        ("3. Detecção Supervisionada de Blefe (ML)", "Treinar e submeter a benchmark 4 famílias de modelos (Random Forest, HistGradientBoosting, Redes Neurais e Regressão Logística) baseando-se exclusivamente em sinais públicos da mesa.", COLOR_ACCENT_RED),
        ("4. Explicabilidade Cognitiva (XAI)", "Descobrir matematicamente através de Feature Importance o que denuncia o blefe (razão aposta/pote, tamanho do pote e profundidade de stack) e disponibilizar inferência em tempo real.", COLOR_GREEN_SUCCESS),
    ]

    for idx, (title, desc, color) in enumerate(objs):
        x = Inches(0.8 + (idx % 2) * 5.9)
        y = Inches(1.8 + (idx // 2) * 2.6)
        add_card(slide3, x, y, Inches(5.7), Inches(2.4))
        tb = slide3.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), Inches(5.3), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = color
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(10.5)
        p2.font.color.rgb = COLOR_DARK_TEXT
        p2.space_before = Pt(6)

    # =========================================================================
    # SLIDE 4: ARQUITETURA E EQUIPE MAESTRI
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    create_header(slide4, "Arquitetura da Solução e Especialização da Equipe no Maestri")

    team = [
        ("Croupier", "Engine Specialist", "Regras do Texas Hold'em, embaralhamento criptográfico, combinatória de 7 cartas, potes principais e side pots múltiplos.", COLOR_PRIMARY_BLUE),
        ("Tactician", "Agent Strategist", "Modelagem da IA dos 3 agentes: Teoria dos Jogos e EV (Matemático), Fold Equity (Blefador) e equilíbrio adaptativo (Híbrido).", COLOR_ACCENT_RED),
        ("Lens", "Telemetry Analyst", "Extração contínua da disparidade cognitiva (equidade Monte Carlo vs pot odds) e rotulagem precisa de blefe puro vs semi-bluff.", COLOR_PRIMARY_DARK),
        ("Rigor", "Performance & Data", "Auditoria de dados e consistência experimental (Win Rate, ROI, BB/100, VPIP/PFR) e prevenção de data leakage.", RGBColor(0, 150, 136)),
        ("Vigil", "QA & Code Reviewer", "Garantia de Qualidade com 154 testes unitários e de integração em pytest (100% de aprovação e zero regressões).", RGBColor(230, 81, 0)),
        ("Harbor", "DevOps & Cloud DB", "Sincronização em nuvem com o banco de dados Neon PostgreSQL (181k registros) e versionamento semântico no GitHub.", COLOR_GREEN_SUCCESS),
    ]

    for idx, (name, role, desc, color) in enumerate(team):
        col = idx % 3
        row = idx // 3
        x = Inches(0.8 + col * 4.0)
        y = Inches(1.8 + row * 2.6)
        add_card(slide4, x, y, Inches(3.8), Inches(2.4))
        tb = slide4.shapes.add_textbox(x + Inches(0.15), y + Inches(0.15), Inches(3.5), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"{name} • {role}"
        p.font.size = Pt(12.5)
        p.font.bold = True
        p.font.color.rgb = color
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(10)
        p2.font.color.rgb = COLOR_DARK_TEXT
        p2.space_before = Pt(6)

    # =========================================================================
    # SLIDE 5: A TRÍADE DOS AGENTES DEFINITIVOS
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    create_header(slide5, "Modelagem Conceitual dos 3 Agentes Definitivos")

    agents = [
        ("📐 Agente Matemático Definitivo", "Fundamentado em Teoria dos Jogos Estrita (+EV)", COLOR_PRIMARY_BLUE, [
            "Cálculo de Pot Odds em tempo real versus Equidade de mão simulada via Monte Carlo.",
            "Aposta e paga apenas quando o Valor Esperado (EV) é positivo.",
            "VPIP ultra-seletivo (~10,7%), PFR contido (~0,7%) e frequência de blefe residual (~1,3%).",
            "Perfil 'Pedra / Tight-Passive': extremamente resiliente e disciplinado."
        ]),
        ("🎭 Agente Blefador Definitivo", "Maximização de Fold Equity e Pressão de Stack", COLOR_ACCENT_RED, [
            "Agressividade contínua no Turn e River contra adversários que demonstraram fraqueza.",
            "Aplica 'overbets' para forçar o fold adversário em potes médios e abandonados.",
            "VPIP agressivo (~29,3%), PFR elevado (~3,4%) e alta frequência de blefe (~174 blefes/500 mãos).",
            "Perfil 'LAG / Loose-Aggressive': coleta potes sem showdown, mas vulnerável a calls fortes."
        ]),
        ("⚡ Agente Híbrido Definitivo", "Equilíbrio Adaptativo Nash-Exploitative & Semi-Bluffs", COLOR_PRIMARY_DARK, [
            "Alterna dinamicamente entre jogo de valor sólido e blefes oportunistas.",
            "Especialista em 'Semi-Bluffs': aposta agressivamente quando possui cartas de compra (Flush e Straight draws).",
            "VPIP intermediário (~17,9%) e PFR balanceado (~6,9%).",
            "Perfil 'TAG / Tight-Aggressive': imprevisível e de difícil leitura na mesa."
        ])
    ]

    for idx, (title, sub, color, items) in enumerate(agents):
        x = Inches(0.8 + idx * 4.0)
        add_card(slide5, x, Inches(1.8), Inches(3.8), Inches(5.1))
        tb = slide5.shapes.add_textbox(x + Inches(0.15), Inches(1.95), Inches(3.5), Inches(4.8))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = color
        p_sub = tf.add_paragraph()
        p_sub.text = sub
        p_sub.font.size = Pt(9.5)
        p_sub.font.color.rgb = COLOR_MUTED_TEXT
        p_sub.space_before = Pt(2)
        for it in items:
            p = tf.add_paragraph()
            p.text = "• " + it
            p.font.size = Pt(10)
            p.font.color.rgb = COLOR_DARK_TEXT
            p.space_before = Pt(6)

    # =========================================================================
    # SLIDE 6: PROTOCOLO EXPERIMENTAL E AS 3 SEEDS
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    create_header(slide6, "Protocolo Experimental: As 3 Seeds e os Três Cenários de Teste")

    # Topologia dos Cenários
    scenarios = [
        ("01. Desktop Mesas Completas (Full-Ring 9-Max)", "Ambiente Tripartite com 3 Matemáticos, 3 Blefadores e 3 Híbridos sentados na mesma mesa (500 mãos). Equilíbrio neutro de posições.", COLOR_PRIMARY_BLUE),
        ("02. Notebook Heads-Up (Duelos 1v1 Isolados)", "Confronto direto sem interferência externa: Matemático vs Blefador, Híbrido vs Blefador e Híbrido vs Matemático.", COLOR_PRIMARY_DARK),
        ("03. Notebook Estresse Extremo (1 Hero vs 5 Clones)", "Cenário de hostilidade máxima: 1 jogador solitário enfrenta 5 oponentes do mesmo perfil antagônico (simulando cerco ou conluio).", COLOR_ACCENT_RED)
    ]

    for idx, (title, desc, color) in enumerate(scenarios):
        x = Inches(0.8 + idx * 4.0)
        add_card(slide6, x, Inches(1.8), Inches(3.8), Inches(2.2))
        tb = slide6.shapes.add_textbox(x + Inches(0.15), Inches(1.9), Inches(3.5), Inches(2.0))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = color
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(10)
        p2.font.color.rgb = COLOR_DARK_TEXT
        p2.space_before = Pt(4)

    # Bloco Inferior: O Volume Consolidado das 3 Seeds
    add_card(slide6, Inches(0.8), Inches(4.3), Inches(11.7), Inches(2.6), bg_color=COLOR_CARD_BLUE_BG, border_color=COLOR_PRIMARY_BLUE)
    tb_b = slide6.shapes.add_textbox(Inches(1.0), Inches(4.45), Inches(11.3), Inches(2.3))
    tf_b = tb_b.text_frame
    tf_b.word_wrap = True

    p = tf_b.paragraphs[0]
    p.text = "📊 Consolidação Estatística Multissemente (Reprodutibilidade Científica Estrita)"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    p_body = tf_b.add_paragraph()
    p_body.text = (
        "Para afastar qualquer interferência de 'sorte' do baralho, todos os cenários foram gerados em 3 seeds independentes:\n"
        "• Seed 101: 59.247 decisões registradas  |  • Seed 144: 61.884 decisões registradas  |  • Seed 99: 59.952 decisões registradas\n"
        "Totalizando 42 experimentos executados e 181.083 decisões brutas auditadas na nuvem do Neon PostgreSQL."
    )
    p_body.font.size = Pt(11)
    p_body.font.color.rgb = COLOR_DARK_TEXT
    p_body.space_before = Pt(6)

    p_badge = tf_b.add_paragraph()
    p_badge.text = "✓ 181.083 DECISÕES TOTAIS  •  50.978 APOSTAS AGRESSIVAS  •  100% AUDITADO E SOBERANO"
    p_badge.font.size = Pt(11.5)
    p_badge.font.bold = True
    p_badge.font.color.rgb = COLOR_GREEN_SUCCESS
    p_badge.space_before = Pt(8)

    # =========================================================================
    # SLIDE 7: RESULTADOS FINANCEIROS NA MESA 9-MAX
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    create_header(slide7, "Desempenho Financeiro e Comportamental na Mesa Tripartite (9-Max)")

    # Tabela com as médias das 3 seeds
    rows, cols = 4, 6
    left, top, width, height = Inches(0.8), Inches(1.8), Inches(11.7), Inches(2.2)
    table_shape = slide7.shapes.add_table(rows, cols, left, top, width, height)
    tbl = table_shape.table

    tbl.columns[0].width = Inches(2.8)
    tbl.columns[1].width = Inches(1.8)
    tbl.columns[2].width = Inches(1.7)
    tbl.columns[3].width = Inches(1.7)
    tbl.columns[4].width = Inches(1.7)
    tbl.columns[5].width = Inches(2.0)

    headers = ["Agente Definitivo", "Lucro Médio (Fichas)", "Win Rate (% Mãos)", "VPIP Médio", "PFR Médio", "Blefes / 500 Mãos"]
    for c_idx, h in enumerate(headers):
        cell = tbl.cell(0, c_idx)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_PRIMARY_DARK
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(10.5)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment = PP_ALIGN.CENTER

    data = [
        ("Matemático Definitivo", "+7.076,11 fichas", "9,19%", "10,69%", "0,68%", "6,33 blefes"),
        ("Blefador Definitivo", "-303,33 fichas", "10,79%", "29,27%", "3,40%", "174,00 blefes"),
        ("Híbrido Definitivo", "-7.497,11 fichas", "8,76%", "17,91%", "6,94%", "133,89 blefes"),
    ]

    for r_idx, row in enumerate(data, 1):
        for c_idx, val in enumerate(row):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_LIGHT_BG if r_idx % 2 == 1 else RGBColor(255, 255, 255)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(10)
                p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
                if c_idx == 1:
                    p.font.bold = True
                    p.font.color.rgb = COLOR_GREEN_SUCCESS if "+" in val else COLOR_ACCENT_RED
                else:
                    p.font.color.rgb = COLOR_DARK_TEXT

    # Card com Análise Crítica dos Resultados
    add_card(slide7, Inches(0.8), Inches(4.3), Inches(11.7), Inches(2.6))
    tb_c = slide7.shapes.add_textbox(Inches(1.0), Inches(4.45), Inches(11.3), Inches(2.3))
    tf_c = tb_c.text_frame
    tf_c.word_wrap = True

    p = tf_c.paragraphs[0]
    p.text = "💡 Conclusões do Confronto de Mesa Completa:"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    points = [
        "Supremacia da Teoria dos Jogos: O Matemático venceu com folga absoluta (+7.076 fichas), confirmando que a disciplina estrita em Pot Odds supera qualquer tentativa de manipulação psicológica.",
        "O Paradoxo do Win Rate: O Blefador ganhou mais mãos em número absoluto (10,79% contra 9,19% do Matemático), mas fechou no prejuízo financeiro. Ele vence muitos potes pequenos (quando todos foldam), mas perde potes gigantescos quando é pego.",
        "O Custo do Híbrido: O Híbrido sofreu o maior prejuízo (-7.497 fichas) devido ao custo de 'semi-bluffs' não concretizados em potes com múltiplos vilões (multiway)."
    ]
    for pt in points:
        p = tf_c.add_paragraph()
        p.text = "• " + pt
        p.font.size = Pt(10.5)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(5)

    # =========================================================================
    # SLIDE 8: ESTRESSE 1V5 E RESILIÊNCIA A COLUSÃO
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    create_header(slide8, "Testes de Estresse Extremo (1 Hero vs 5 Clones Adversários)")

    stress_cases = [
        ("Matemático Solitário vs 5 Clones", "Resiliência Absoluta (+20.014 fichas contra 5 Híbridos)", COLOR_GREEN_SUCCESS, [
            "Mesmo cercado por 5 oponentes agressivos tentando forçar folds coordenados, o Matemático manteve lucro astronômico.",
            "Como ele só joga com Pot Odds a favor e não tem apego emocional a fichas já apostadas, os blefadores não conseguem extrair valor de suas mãos fracas."
        ]),
        ("Blefador Solitário vs 5 Matemáticos", "O 'Efeito Xerife' e a Punição Sistemática (-5.223 fichas)", COLOR_ACCENT_RED, [
            "Ao tentar blefar contra 5 jogadores ultra-seletivos, a probabilidade conjunta de pelo menos um deles ter acertado uma mão de topo é altíssima.",
            "O blefe sistemático contra múltiplos 'Sheriffs' resulta em quebra rápida de stack."
        ]),
        ("Híbrido Solitário vs 5 Clones", "Vulnerabilidade ao Desequilíbrio Estrutural", COLOR_PRIMARY_DARK, [
            "O agente híbrido depende de uma dinâmica de mesa equilibrada para explorar tendências.",
            "Em mesas homogêneas e polarizadas (só matemáticos ou só blefadores), sua taxa de adaptação sofre com variações de curto prazo."
        ])
    ]

    for idx, (title, sub, color, items) in enumerate(stress_cases):
        y = Inches(1.8 + idx * 1.75)
        add_card(slide8, Inches(0.8), y, Inches(11.7), Inches(1.6))
        tb = slide8.shapes.add_textbox(Inches(1.0), y + Inches(0.1), Inches(11.3), Inches(1.4))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title + "  —  " + sub
        p.font.size = Pt(12.5)
        p.font.bold = True
        p.font.color.rgb = color
        for it in items:
            p = tf.add_paragraph()
            p.text = "• " + it
            p.font.size = Pt(10)
            p.font.color.rgb = COLOR_DARK_TEXT
            p.space_before = Pt(3)

    # =========================================================================
    # SLIDE 9: ENGENHARIA DE FEATURES E SPLITS DE DADOS
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    create_header(slide9, "Engenharia de Atributos e Divisão Estratificada (Splits de ML)")

    # Card 1: Filtragem e Rótulos
    add_card(slide9, Inches(0.8), Inches(1.8), Inches(5.7), Inches(5.0))
    tb1 = slide9.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf1 = tb1.text_frame
    tf1.word_wrap = True
    p = tf1.paragraphs[0]
    p.text = "🎯 Filtragem das Decisões e Ground Truth"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    bullets1 = [
        "Universo Amostral: 181.083 decisões brutas (incluindo folds e checks que não arriscam fichas).",
        "Amostras Alvo Filtradas: 50.978 apostas agressivas (BET, RAISE e ALL-IN), que representam as disputas ativas de pote.",
        "Distribuição de Rótulos Reais:",
        "  • 28.886 Apostas Reais de Valor (56,66% - Classe 0)",
        "  • 22.092 Blefes Reais Detectados (43,34% - Classe 1)",
        "Divisão Estratificada (Garantindo Mesma Proporção):",
        "  • Conjunto de Treino (70%): 35.684 amostras",
        "  • Conjunto de Validação (15%): 7.647 amostras",
        "  • Teste Cego Independente (15%): 7.647 amostras inéditas"
    ]
    for b in bullets1:
        p = tf1.add_paragraph()
        p.text = b
        p.font.size = Pt(10.5)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(4)

    # Card 2: Features Públicas In-Game
    add_card(slide9, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.0), bg_color=COLOR_CARD_BLUE_BG, border_color=COLOR_PRIMARY_BLUE)
    tb2 = slide9.shapes.add_textbox(Inches(7.0), Inches(2.0), Inches(5.3), Inches(4.6))
    tf2 = tb2.text_frame
    tf2.word_wrap = True
    p = tf2.paragraphs[0]
    p.text = "👁️ Features Públicas In-Game (Blind Observer)"
    p.font.size = Pt(14)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_BLUE

    bullets2 = [
        "Premissa Ética e Operacional: O modelo não pode trapacear (não vê as cartas fechadas de ninguém). Ele atua como um jogador humano observando a mesa.",
        "Variáveis Públicas Utilizadas:",
        "  1. Street: Rodada da aposta (Pré-Flop, Flop, Turn, River).",
        "  2. Action Taken: Tipo de agressão (BET, RAISE, ALL_IN).",
        "  3. Bettor Profile: Perfil histórico observado do agressor.",
        "  4. Amount: Valor absoluto da aposta em fichas.",
        "  5. Pot Before: Tamanho do pote acumulado até o momento.",
        "  6. Bet-to-Pot Ratio: Razão proporcional da aposta em relação ao pote (Bet Sizing fundamental).",
        "  7. Stack-to-Pot Ratio (SPR): Risco relativo do stack restante.",
        "  8. Pot Odds: Custo percentual imposto para o adversário pagar."
    ]
    for b in bullets2:
        p = tf2.add_paragraph()
        p.text = b
        p.font.size = Pt(10.5)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(4)

    # =========================================================================
    # SLIDE 10: BENCHMARK DOS 4 MODELOS DE MACHINE LEARNING
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    create_header(slide10, "Benchmark de Machine Learning: Comparativo dos 4 Modelos Testados")

    # Tabela com as métricas auditadas
    rows, cols = 5, 8
    left, top, width, height = Inches(0.8), Inches(1.8), Inches(11.7), Inches(2.6)
    table_shape = slide10.shapes.add_table(rows, cols, left, top, width, height)
    tbl10 = table_shape.table

    tbl10.columns[0].width = Inches(2.6)
    tbl10.columns[1].width = Inches(1.3)
    tbl10.columns[2].width = Inches(1.3)
    tbl10.columns[3].width = Inches(1.3)
    tbl10.columns[4].width = Inches(1.3)
    tbl10.columns[5].width = Inches(1.4)
    tbl10.columns[6].width = Inches(1.3)
    tbl10.columns[7].width = Inches(1.2)

    headers10 = ["Algoritmo Testado", "Acurácia", "Precisão", "Recall Blefe", "F1-Score", "ROC-AUC", "PR-AUC", "Tempo"]
    for c_idx, h in enumerate(headers10):
        cell = tbl10.cell(0, c_idx)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_PRIMARY_DARK
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(9.5)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 255, 255)
            p.alignment = PP_ALIGN.CENTER

    data10 = [
        ("HistGradientBoosting", "89,43%", "85,54%", "91,01%", "0,8819", "0,9704 (97,0%)", "0,9635", "3,31s"),
        ("Random Forest (150 Árvores)", "89,25%", "84,71%", "91,76%", "0,8809", "0,9665 (96,7%)", "0,9589", "1,09s"),
        ("Rede Neural MLP (64x32)", "86,86%", "80,60%", "91,76%", "0,8582", "0,9499 (95,0%)", "0,9387", "5,99s"),
        ("Regressão Logística (L2)", "76,00%", "70,67%", "76,28%", "0,7337", "0,8574 (85,7%)", "0,7866", "0,15s"),
    ]

    for r_idx, row in enumerate(data10, 1):
        for c_idx, val in enumerate(row):
            cell = tbl10.cell(r_idx, c_idx)
            cell.text = val
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_LIGHT_BG if r_idx % 2 == 1 else RGBColor(255, 255, 255)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(9.5)
                p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
                if c_idx in [1, 3, 5] and r_idx in [1, 2]:
                    p.font.bold = True
                    p.font.color.rgb = COLOR_GREEN_SUCCESS
                else:
                    p.font.color.rgb = COLOR_DARK_TEXT

    # Discussão
    add_card(slide10, Inches(0.8), Inches(4.7), Inches(11.7), Inches(2.2))
    tb_d = slide10.shapes.add_textbox(Inches(1.0), Inches(4.85), Inches(11.3), Inches(1.9))
    tf_d = tb_d.text_frame
    tf_d.word_wrap = True

    p = tf_d.paragraphs[0]
    p.text = "🔬 Análise Comparativa dos Algoritmos:"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    bullets_d = [
        "1. Domínio dos Ensembles (Árvores): O HistGradientBoosting e o Random Forest alcançaram os melhores resultados (~89,4% acurácia e 97,0% ROC-AUC), pois capturam com perfeição limiares numéricos contínuos (thresholds de overbet).",
        "2. Alta Sensibilidade da Rede Neural: A Rede Neural MLP empatou no topo da sensibilidade com 91,76% de Recall, detectando com sucesso mais de 9 em cada 10 blefes reais na mesa.",
        "3. Comprovação da Não-Linearidade: A Regressão Logística ficou 13,4 pontos percentuais atrás (76%), provando que o blefe não pode ser modelado linearmente; ele depende da interação combinada entre o Bet Sizing e o Pote.",
        "4. Modelo XAI Oracle (Auditoria): Ao incluir os dados cognitivos internos (equidade Monte Carlo), o modelo atinge 100% de acurácia, comprovando que o algoritmo de rotulagem do simulador é matematicamente perfeito."
    ]
    for bd in bullets_d:
        p = tf_d.add_paragraph()
        p.text = bd
        p.font.size = Pt(10)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(3)

    # =========================================================================
    # SLIDE 11: EVIDÊNCIAS EXPERIMENTAIS (MATRIZ DE CONFUSÃO E ROC)
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    create_header(slide11, "Evidências Experimentais: Matriz de Confusão e Curvas ROC/PR")

    # Inserir Imagem 1: Matriz de Confusão
    img_cm = PLOTS_DIR / "matriz_confusao.png"
    if img_cm.exists():
        slide11.shapes.add_picture(str(img_cm), Inches(0.8), Inches(1.8), width=Inches(5.7))

    # Inserir Imagem 2: Curva ROC e PR
    img_roc = PLOTS_DIR / "curva_roc_pr.png"
    if img_roc.exists():
        slide11.shapes.add_picture(str(img_roc), Inches(6.8), Inches(1.8), width=Inches(5.7))

    # Legenda explicativa inferior
    add_card(slide11, Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.2), bg_color=COLOR_LIGHT_BG)
    tb_l = slide11.shapes.add_textbox(Inches(1.0), Inches(5.9), Inches(11.3), Inches(1.0))
    tf_l = tb_l.text_frame
    tf_l.word_wrap = True
    p = tf_l.paragraphs[0]
    p.text = "Interpretação dos Gráficos (Teste Cego Independente — 7.647 Amostras Inéditas):"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK
    p2 = tf_l.add_paragraph()
    p2.text = (
        "• Esquerda: Matriz de confusão comprovando 91,8% de acerto na classe de blefes reais e 87,3% em apostas de valor legítimas.\n"
        "• Direita: Curvas ROC (AUC = 0,967) e Precision-Recall (PR-AUC = 0,959), demonstrando separabilidade quase perfeita das classes."
    )
    p2.font.size = Pt(9.5)
    p2.font.color.rgb = COLOR_DARK_TEXT
    p2.space_before = Pt(2)

    # =========================================================================
    # SLIDE 12: EXPLICABILIDADE (XAI) E HISTOGRAMA DE PROBABILIDADE
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    create_header(slide12, "Explicabilidade (XAI): O Que Realmente Denuncia o Blefe na Mesa?")

    # Inserir Imagem 3: Feature Importance
    img_shap = PLOTS_DIR / "shap_summary_explicabilidade.png"
    if img_shap.exists():
        slide12.shapes.add_picture(str(img_shap), Inches(0.8), Inches(1.8), width=Inches(5.7))

    # Inserir Imagem 4: Distribuição de Probabilidade
    img_dist = PLOTS_DIR / "distribuicao_probabilidade_blefe.png"
    if img_dist.exists():
        slide12.shapes.add_picture(str(img_dist), Inches(6.8), Inches(1.8), width=Inches(5.7))

    # Legenda explicativa inferior
    add_card(slide12, Inches(0.8), Inches(5.8), Inches(11.7), Inches(1.2), bg_color=COLOR_LIGHT_BG)
    tb_l2 = slide12.shapes.add_textbox(Inches(1.0), Inches(5.9), Inches(11.3), Inches(1.0))
    tf_l2 = tb_l2.text_frame
    tf_l2.word_wrap = True
    p = tf_l2.paragraphs[0]
    p.text = "Descobertas Científicas de Explicabilidade Cognitiva:"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK
    p2 = tf_l2.add_paragraph()
    p2.text = (
        "• Esquerda: A Razão Aposta/Pote (Bet Sizing) responde por 34,8% da separação, seguida pelo Tamanho do Pote Anterior (23,2%) e SPR (18,5%).\n"
        "• Direita: O histograma bimodal comprova que o modelo classifica com alta convicção (probabilidades próximas a 0 ou 1, com mínima incerteza central)."
    )
    p2.font.size = Pt(9.5)
    p2.font.color.rgb = COLOR_DARK_TEXT
    p2.space_before = Pt(2)

    # =========================================================================
    # SLIDE 13: MÓDULO DE INFERÊNCIA E DEMONSTRAÇÃO WEB
    # =========================================================================
    slide13 = prs.slides.add_slide(blank_layout)
    create_header(slide13, "Aplicação Prática: Inferência em Tempo Real e Demonstração Web")

    # Card 1: Código de Inferência
    add_card(slide13, Inches(0.8), Inches(1.8), Inches(6.0), Inches(5.0))
    tb_inf = slide13.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.6), Inches(4.6))
    tf_inf = tb_inf.text_frame
    tf_inf.word_wrap = True
    p = tf_inf.paragraphs[0]
    p.text = "⚡ Módulo BluffDetector (src/models/bluff_detector.py)"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    code_snippet = (
        "from src.models.bluff_detector import BluffDetector\n\n"
        "detector = BluffDetector()\n"
        "# Vilão fez aumento forte no River:\n"
        "veredito = detector.analyze_bet({\n"
        "    'street': 'RIVER',\n"
        "    'action_taken': 'RAISE',\n"
        "    'bettor_profile': 'Blefador',\n"
        "    'amount': 250.0,\n"
        "    'pot_before': 100.0,\n"
        "    'player_stack_before': 800.0,\n"
        "    'pot_odds': 0.35\n"
        "})\n\n"
        "# Retorno em milissegundos:\n"
        "{\n"
        "  'bluff_probability': 0.8842,\n"
        "  'is_bluff': True,\n"
        "  'verdict': 'ALTO_RISCO_BLEFE',\n"
        "  'recommendation': 'Call ou Re-aumento'\n"
        "}"
    )
    p_code = tf_inf.add_paragraph()
    p_code.text = code_snippet
    p_code.font.size = Pt(9.5)
    p_code.font.name = "Consolas"
    p_code.font.color.rgb = RGBColor(0, 51, 102)
    p_code.space_before = Pt(8)

    # Card 2: Aplicação Web
    add_card(slide13, Inches(7.1), Inches(1.8), Inches(5.4), Inches(5.0), bg_color=COLOR_CARD_BLUE_BG, border_color=COLOR_PRIMARY_BLUE)
    tb_web = slide13.shapes.add_textbox(Inches(7.3), Inches(2.0), Inches(5.0), Inches(4.6))
    tf_web = tb_web.text_frame
    tf_web.word_wrap = True
    p = tf_web.paragraphs[0]
    p.text = "🌐 Mesa Virtual Interativa e Deploy"
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_BLUE

    bullets_web = [
        "Interface Web Interativa (Flask + HTML5 Canvas):",
        "  • Modos de jogo: Humano vs IA ou Simulação Multiagente Tripartite autônoma.",
        "  • Configuração em tempo real de stacks, número de jogadores (2 a 9) e tipos de agentes.",
        "  • Conexão ativa no canvas do Maestri via browser portal.",
        "Gravação e Persistência Cloud:",
        "  • Gravação automática de mãos com código de autenticação (TCC2026).",
        "  • Sincronização direta com a nuvem do Neon PostgreSQL.",
        "Prontidão para Apresentação em Sala de Aula:",
        "  • O sistema pode ser executado ao vivo com a turma assistindo a decisões tomadas rodada a rodada."
    ]
    for bw in bullets_web:
        p = tf_web.add_paragraph()
        p.text = bw
        p.font.size = Pt(10)
        p.font.color.rgb = COLOR_DARK_TEXT
        p.space_before = Pt(4)

    # =========================================================================
    # SLIDE 14: DIFICULDADES E DESAFIOS ENFRENTADOS
    # =========================================================================
    slide14 = prs.slides.add_slide(blank_layout)
    create_header(slide14, "Desafios de Engenharia e Dificuldades Superadas")

    challenges = [
        ("1. Explosão de Volume e Latência de Rede", "Desafio: Tentar gravar 180.000 decisões simultaneamente em banco na nuvem travava as simulações.\nSolução: Criamos gravação local em CSV de alta velocidade e um sincronizador dedicado em lotes (Bulk Insert com execute_values) que transmitiu todas as 181k linhas ao Neon em apenas 32 segundos."),
        ("2. Calibração Sem Vícios dos Agentes (Sprint 1 e 2)", "Desafio: O Blefador inicial sofria de 'raise infinito' e o Matemático dava folds excessivos no River.\nSolução: Implementamos o Critério de Kelly Fracionário no Matemático e limites de polarização por fold equity no Blefador, atingindo equilíbrio perfeito."),
        ("3. Prevenção de Vazamento de Dados (Data Leakage)", "Desafio: Garantir que o modelo de Machine Learning não recebesse dados ocultos (como cartas do vilão) e não avaliasse decisões da mesma mão em treino e teste.\nSolução: Divisão estratificada rigorosa e isolamento estrito entre features públicas In-Game e telemetria interna Oracle."),
        ("4. Confiabilidade e Orquestração Multiagente", "Desafio: Manter múltiplos processos (servidor web, simuladores e scripts) executando de forma coordenada.\nSolução: Criação de suíte com 154 testes unitários e de integração em pytest garantindo 100% de estabilidade."),
    ]

    for idx, (title, desc) in enumerate(challenges):
        col = idx % 2
        row = idx // 2
        x = Inches(0.8 + col * 5.9)
        y = Inches(1.8 + row * 2.6)
        add_card(slide14, x, y, Inches(5.7), Inches(2.4))
        tb = slide14.shapes.add_textbox(x + Inches(0.2), y + Inches(0.15), Inches(5.3), Inches(2.1))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(13)
        p.font.bold = True
        p.font.color.rgb = COLOR_ACCENT_RED
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(10)
        p2.font.color.rgb = COLOR_DARK_TEXT
        p2.space_before = Pt(6)

    # =========================================================================
    # SLIDE 15: INSIGHTS E PRINCIPAIS APRENDIZADOS
    # =========================================================================
    slide15 = prs.slides.add_slide(blank_layout)
    create_header(slide15, "Principais Insights e Contribuições Científicas do Projeto")

    insights = [
        ("A Matemática Supera a Agressividade a Longo Prazo", "Mesmo em um jogo psicológico e imperfeito como o poker, a adesão estrita ao Valor Esperado (+EV) e Pot Odds garante lucro consistente (+7.076 fichas) e invulnerabilidade contra tentativas de conluio (como comprovado no teste de estresse 1v5).", COLOR_PRIMARY_BLUE),
        ("O Blefe Deixa Fortes Assinaturas Matemáticas Públicas", "Não é necessário ver as cartas do adversário para saber que ele está blefando. A relação entre a aposta e o pote (Bet Sizing), o SPR e o tamanho do pote acumulado entregam mais de 91% dos blefes antes do showdown.", COLOR_ACCENT_RED),
        ("Modelos de Árvore são Ideais para Jogos de Apostas", "O HistGradientBoosting e o Random Forest superaram redes neurais e modelos lineares porque apostas em poker são guiadas por limiares críticos discretos (ex: aposta superior a 75% do pote).", COLOR_PRIMARY_DARK),
        ("Viabilidade de Aplicação em Tempo Real", "O classificador treinado roda com latência sub-milissegundo, demonstrando viabilidade imediata para sistemas anti-fraude, plataformas de treinamento de jogadores profissionais e detecção de bots em salas virtuais.", COLOR_GREEN_SUCCESS),
    ]

    for idx, (title, desc, color) in enumerate(insights):
        y = Inches(1.8 + idx * 1.3)
        add_card(slide15, Inches(0.8), y, Inches(11.7), Inches(1.15))
        tb = slide15.shapes.add_textbox(Inches(1.0), y + Inches(0.08), Inches(11.3), Inches(1.0))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = f"{idx+1}. {title}"
        p.font.size = Pt(12)
        p.font.bold = True
        p.font.color.rgb = color
        p2 = tf.add_paragraph()
        p2.text = desc
        p2.font.size = Pt(9.5)
        p2.font.color.rgb = COLOR_DARK_TEXT
        p2.space_before = Pt(2)

    # =========================================================================
    # SLIDE 16: CONCLUSÃO E AGRADECIMENTOS
    # =========================================================================
    slide16 = prs.slides.add_slide(blank_layout)

    # Faixas decorativas
    strip_end = slide16.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.5), Inches(7.5))
    strip_end.fill.solid()
    strip_end.fill.fore_color.rgb = COLOR_PRIMARY_DARK
    strip_end.line.fill.background()

    strip_end2 = slide16.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(0), Inches(0.15), Inches(7.5))
    strip_end2.fill.solid()
    strip_end2.fill.fore_color.rgb = COLOR_ACCENT_RED
    strip_end2.line.fill.background()

    if logo_path.exists():
        slide16.shapes.add_picture(str(logo_path), Inches(1.2), Inches(0.8), height=Inches(1.1))

    tb_end = slide16.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11.0), Inches(2.0))
    tf_end = tb_end.text_frame
    tf_end.word_wrap = True

    p = tf_end.paragraphs[0]
    p.text = "MUITO OBRIGADO!"
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    p2 = tf_end.add_paragraph()
    p2.text = "Estamos abertos a dúvidas, perguntas e discussões com o Professor e a Turma."
    p2.font.size = Pt(16)
    p2.font.color.rgb = COLOR_MUTED_TEXT
    p2.space_before = Pt(8)

    # Card Final com Dados Institucionais e Repositório
    add_card(slide16, Inches(1.2), Inches(4.5), Inches(11.0), Inches(2.2), bg_color=COLOR_LIGHT_BG)
    tb_cred = slide16.shapes.add_textbox(Inches(1.5), Inches(4.65), Inches(10.4), Inches(1.9))
    tf_cred = tb_cred.text_frame
    tf_cred.word_wrap = True

    p = tf_cred.paragraphs[0]
    p.text = "CENTRO ESTADUAL DE EDUCAÇÃO TECNOLÓGICA PAULA SOUZA — FATEC OURINHOS"
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY_DARK

    p = tf_cred.add_paragraph()
    p.text = "Discentes: Alberto Totti José   |   Giovane Adão de Moraes   |   Gustavo de Souza"
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = COLOR_DARK_TEXT
    p.space_before = Pt(4)

    p = tf_cred.add_paragraph()
    p.text = "Docente Orientador: Prof. Dr. Sidney Carlos Ferrari"
    p.font.size = Pt(11.5)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT_RED
    p.space_before = Pt(4)

    p = tf_cred.add_paragraph()
    p.text = "Repositório do Projeto no GitHub: https://github.com/AlbertoTotiJ/Poker-TCC"
    p.font.size = Pt(10.5)
    p.font.color.rgb = COLOR_PRIMARY_BLUE
    p.space_before = Pt(6)

    # Salvar Apresentação
    prs.save(str(OUTPUT_PPTX))
    prs.save(str(OUTPUT_PPTX_DATA))
    print(f"✓ Apresentação PowerPoint gerada com sucesso em: {OUTPUT_PPTX}")
    print(f"✓ Cópia sincronizada em: {OUTPUT_PPTX_DATA}")


if __name__ == "__main__":
    build_presentation()
