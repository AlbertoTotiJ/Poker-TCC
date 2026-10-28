"""Módulo de Visualização Científica e Gráficos de Resultados para o TCC.

Gera gráficos em alta resolução (300 DPI) a partir de:
- `data/game_actions.csv`
- `data/decision_telemetry_and_bluffs.csv`

Gráficos produzidos:
1. `1_vitorias_por_agente.png`           : Taxa de vitórias e potes ganhos.
2. `2_evolucao_bankroll.png`            : Evolução de saldo de fichas mão a mão.
3. `3_matriz_confronto_direto.png`      : Heatmap de quem mais ganhou fichas de quem.
4. `4_analise_blefes.png`               : Detecção de blefes, aceitação vs recusa e desfechos.
5. `dashboard_consolidado_tcc.png`      : Painel executivo consolidado 2x2 para a banca.
"""

from collections import defaultdict
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Garante resolução de caminhos
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Paleta de cores oficial para os perfis dos agentes no TCC
PROFILE_COLORS = {
    "Matemático Treinado (Tier S)": "#1f77b4",  # Azul sólido
    "Blefador Treinado (Tier S)": "#d62728",    # Vermelho tático
    "Híbrido": "#2ca02c",                      # Verde adaptativo
    "Matemático": "#17becf",
    "Blefador": "#ff7f0e",
    "Agressivo": "#9467bd",
    "Conservador": "#8c564b",
    "Equilibrado": "#7f7f7f",
    "Desconhecido": "#bcbd22",
}


def get_profile_color(profile_name: str) -> str:
    """Retorna cor consistente associada ao perfil do agente."""
    for key, color in PROFILE_COLORS.items():
        if key.lower() in profile_name.lower():
            return color
    return "#333333"


def plot_win_rates(df_actions: pd.DataFrame, df_telemetry: pd.DataFrame, output_dir: Path) -> Path:
    """Gráfico 1: Potes Vencidos e Taxa de Vitória por Perfil de Agente."""
    # Identifica o vencedor de cada mão única
    won_hands = df_telemetry[df_telemetry["hand_result"].isin(["WON_HAND", "SPLIT_POT"])][
        ["hand_id", "profile", "player_name"]
    ].drop_duplicates(subset=["hand_id", "player_name"])

    profile_counts = won_hands["profile"].value_counts()
    total_hands = df_telemetry["hand_id"].nunique()

    fig, ax = plt.subplots(figsize=(9, 5), dpi=300)
    bars = ax.bar(
        profile_counts.index,
        profile_counts.values,
        color=[get_profile_color(p) for p in profile_counts.index],
        edgecolor="#222",
        linewidth=1.2,
        width=0.55,
    )

    for bar in bars:
        h = bar.get_height()
        pct = (h / total_hands) * 100
        ax.annotate(
            f"{int(h)} vitórias\n({pct:.1f}%)",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
        )

    ax.set_title(
        f"Distribuição de Vitórias por Perfil de Agente ({total_hands} Mãos)",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.set_ylabel("Quantidade de Mãos Vencidas", fontsize=11, labelpad=10)
    ax.set_ylim(0, max(profile_counts.values) * 1.25)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.xticks(rotation=10, ha="right", fontsize=10, fontweight="bold")
    plt.tight_layout()

    out_file = output_dir / "1_vitorias_por_agente.png"
    plt.savefig(out_file)
    plt.close()
    return out_file


def plot_bankroll_evolution(df_actions: pd.DataFrame, df_telemetry: pd.DataFrame, output_dir: Path) -> Path:
    """Gráfico 2: Curva de Evolução de Saldo Acumulado de Fichas (Bankroll Curve)."""
    # Para cada mão e cada jogador, calcula o saldo líquido da mão
    # Pega o último registro de cada mão por jogador
    last_action_per_hand = df_telemetry.drop_duplicates(subset=["hand_id", "player_name"], keep="last")

    # Mapeamento do perfil de cada jogador
    player_profiles = df_telemetry[["player_name", "profile"]].drop_duplicates().set_index("player_name")["profile"].to_dict()

    hands = sorted(df_telemetry["hand_id"].unique())
    players = sorted(df_telemetry["player_name"].unique())

    # Constrói o histórico acumulado
    cumulative_chips = {p: [0] for p in players}

    for h in hands:
        sub_h = last_action_per_hand[last_action_per_hand["hand_id"] == h]
        chips_delta_map = dict(zip(sub_h["player_name"], sub_h["net_bluff_chips"]))

        for p in players:
            delta = chips_delta_map.get(p, 0)
            cumulative_chips[p].append(cumulative_chips[p][-1] + delta)

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)

    for p in players:
        prof = player_profiles.get(p, "")
        color = get_profile_color(prof)
        ls = "-"
        if "2" in p:
            ls = "--"
        elif "3" in p:
            ls = ":"
        ax.plot(
            range(len(cumulative_chips[p])),
            cumulative_chips[p],
            label=f"{p} ({prof.split('(')[0].strip()})",
            color=color,
            linestyle=ls,
            linewidth=2.0,
            alpha=0.88,
        )

    ax.axhline(0, color="#444444", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.set_title(
        "Evolução Temporal do Saldo de Fichas (Bankroll Curve)",
        fontsize=13,
        fontweight="bold",
        pad=15,
    )
    ax.set_xlabel("Mãos Simuladas", fontsize=11, labelpad=10)
    ax.set_ylabel("Saldo Líquido Acumulado (Fichas)", fontsize=11, labelpad=10)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=8.5, frameon=True)
    plt.tight_layout()

    out_file = output_dir / "2_evolucao_bankroll.png"
    plt.savefig(out_file)
    plt.close()
    return out_file


def plot_head_to_head_matrix(df_actions: pd.DataFrame, df_telemetry: pd.DataFrame, output_dir: Path) -> Path:
    """Gráfico 3: Matriz de Confronto Direto - Quem Mais Ganhou Fichas de Quem (Transfer Matrix)."""
    # Extrai perfis únicos
    profiles = sorted(df_actions["profile"].unique())
    n = len(profiles)
    matrix = pd.DataFrame(0, index=profiles, columns=profiles, dtype=int)

    # Identifica o fluxo de fichas por mão
    hands = df_actions["hand_id"].unique()
    for h in hands:
        sub_act = df_actions[df_actions["hand_id"] == h]
        sub_tel = df_telemetry[df_telemetry["hand_id"] == h]

        # Vencedor(es) da mão
        winners = sub_tel[sub_tel["hand_result"].isin(["WON_HAND", "SPLIT_POT"])]["profile"].unique()
        if len(winners) == 0:
            continue

        # Calcula quanto cada perfil apostou nesta mão
        contrib_by_profile = sub_act.groupby("profile")["amount"].sum()

        for win_prof in winners:
            for loser_prof, amt in contrib_by_profile.items():
                if loser_prof != win_prof and amt > 0:
                    # O perfil perdedor cedeu fichas para o vencedor
                    matrix.loc[loser_prof, win_prof] += int(amt / len(winners))

    fig, ax = plt.subplots(figsize=(8.5, 6.5), dpi=300)
    cax = ax.matshow(matrix.values, cmap="YlOrRd", alpha=0.85)

    # Rótulos dos eixos
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(profiles, rotation=25, ha="left", fontsize=9.5, fontweight="bold")
    ax.set_yticklabels(profiles, fontsize=9.5, fontweight="bold")

    # Valores anotados dentro das células
    for i in range(n):
        for j in range(n):
            val = matrix.iloc[i, j]
            text_color = "white" if val > matrix.values.max() * 0.6 else "black"
            ax.text(
                j,
                i,
                f"{val:,}\nfichas" if val > 0 else "-",
                ha="center",
                va="center",
                color=text_color,
                fontsize=9.5,
                fontweight="bold",
            )

    fig.colorbar(cax, fraction=0.046, pad=0.04, label="Total de Fichas Transferidas")
    ax.set_title(
        "Matriz de Confronto Direto (Quem Mais Cedeu Fichas Para Quem)",
        fontsize=12,
        fontweight="bold",
        pad=30,
    )
    ax.set_ylabel("Cedeu Fichas (Perdedor) ➔", fontsize=10.5, fontweight="bold")
    ax.set_xlabel("➔ Ganhou Fichas (Vencedor)", fontsize=10.5, fontweight="bold")
    plt.tight_layout()

    out_file = output_dir / "3_matriz_confronto_direto.png"
    plt.savefig(out_file)
    plt.close()
    return out_file


def plot_bluff_analysis(df_telemetry: pd.DataFrame, output_dir: Path) -> Path:
    """Gráfico 4: Painel Anatômico de Blefes (Taxonomia, Aceitação e Desfecho)."""
    df_bluffs = df_telemetry[df_telemetry["is_bluff"] == True]  # noqa: E712
    if len(df_bluffs) == 0:
        return output_dir / "4_analise_blefes.png"

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

    # Subplot A: Frequência por Tipo de Blefe
    type_counts = df_bluffs["bluff_type"].value_counts()
    type_labels = {
        "PURE_BLUFF": "Blefe Puro",
        "SEMI_BLUFF": "Semi-Blefe (Draws)",
        "CBET_BLUFF": "C-Bet (Continuação)",
        "STEAL_BLUFF": "Roubo de Blinds",
        "BLOCKER_BLUFF": "Blocker",
    }
    clean_labels = [type_labels.get(k, k) for k in type_counts.index]
    colors_types = ["#e74c3c", "#3498db", "#f39c12", "#9b59b6", "#1abc9c"]

    bars1 = ax1.bar(clean_labels, type_counts.values, color=colors_types[: len(clean_labels)], edgecolor="#222")
    for bar in bars1:
        h = bar.get_height()
        ax1.annotate(
            f"{int(h)} ({h / len(df_bluffs):.1%})",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    ax1.set_title("A. Frequência por Tipo de Blefe", fontsize=11, fontweight="bold", pad=12)
    ax1.set_ylabel("Quantidade de Tentativas", fontsize=10)
    ax1.set_ylim(0, max(type_counts.values) * 1.25)
    ax1.grid(axis="y", linestyle="--", alpha=0.45)
    ax1.tick_params(axis="x", rotation=15)

    # Subplot B: Reação do Oponente (Aceitou Fold vs Recusou Call/Raise)
    resp_counts = df_bluffs["opponent_response"].value_counts()
    resp_labels = {
        "ACCEPTED_ALL_FOLD": "Aceito (Vilão Fold)",
        "REFUSED_CALLED": "Recusado (Vilão Call)",
        "REFUSED_RAISED": "Recusado (Vilão Raise)",
    }
    clean_resp_labels = [resp_labels.get(k, k) for k in resp_counts.index]
    colors_resp = ["#2ecc71", "#e67e22", "#c0392b"]

    wedges, texts, autotexts = ax2.pie(
        resp_counts.values,
        labels=clean_resp_labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=colors_resp[: len(clean_resp_labels)],
        wedgeprops=dict(edgecolor="#222", linewidth=1.2),
        textprops=dict(fontweight="bold", fontsize=9.5),
    )
    for at in autotexts:
        at.set_color("white")

    ax2.set_title("B. Reação dos Adversários aos Blefes", fontsize=11, fontweight="bold", pad=12)

    plt.suptitle(
        f"Análise Anatômica de Blefes ({len(df_bluffs)} Ações Identificadas)",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )
    plt.tight_layout()

    out_file = output_dir / "4_analise_blefes.png"
    plt.savefig(out_file)
    plt.close()
    return out_file


def plot_consolidated_dashboard(
    df_actions: pd.DataFrame,
    df_telemetry: pd.DataFrame,
    output_dir: Path,
) -> Path:
    """Gráfico 5: Dashboard Consolidado 2x2 para a Apresentação do TCC."""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12), dpi=300)

    # 1. Vitórias (Superior Esquerdo)
    won_hands = df_telemetry[df_telemetry["hand_result"].isin(["WON_HAND", "SPLIT_POT"])][
        ["hand_id", "profile", "player_name"]
    ].drop_duplicates(subset=["hand_id", "player_name"])
    profile_counts = won_hands["profile"].value_counts()
    total_hands = df_telemetry["hand_id"].nunique()

    axes[0, 0].bar(
        profile_counts.index,
        profile_counts.values,
        color=[get_profile_color(p) for p in profile_counts.index],
        edgecolor="#222",
        width=0.5,
    )
    for bar in axes[0, 0].patches:
        h = bar.get_height()
        axes[0, 0].annotate(
            f"{int(h)} ({h / total_hands:.1%})",
            xy=(bar.get_x() + bar.get_width() / 2, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontweight="bold",
            fontsize=9,
        )
    axes[0, 0].set_title("1. Taxa de Vitória por Perfil", fontsize=11.5, fontweight="bold")
    axes[0, 0].set_ylabel("Mãos Vencidas")
    axes[0, 0].grid(axis="y", linestyle="--", alpha=0.45)
    axes[0, 0].tick_params(axis="x", rotation=10)

    # 2. Bankroll Curve (Superior Direito)
    last_action_per_hand = df_telemetry.drop_duplicates(subset=["hand_id", "player_name"], keep="last")
    player_profiles = df_telemetry[["player_name", "profile"]].drop_duplicates().set_index("player_name")["profile"].to_dict()
    hands = sorted(df_telemetry["hand_id"].unique())
    players = sorted(df_telemetry["player_name"].unique())
    cumulative_chips = {p: [0] for p in players}

    for h in hands:
        sub_h = last_action_per_hand[last_action_per_hand["hand_id"] == h]
        chips_delta_map = dict(zip(sub_h["player_name"], sub_h["net_bluff_chips"]))
        for p in players:
            delta = chips_delta_map.get(p, 0)
            cumulative_chips[p].append(cumulative_chips[p][-1] + delta)

    for p in players:
        prof = player_profiles.get(p, "")
        axes[0, 1].plot(
            range(len(cumulative_chips[p])),
            cumulative_chips[p],
            label=f"{p}",
            color=get_profile_color(prof),
            linewidth=1.8,
            alpha=0.85,
        )
    axes[0, 1].axhline(0, color="#555", linestyle="--", alpha=0.6)
    axes[0, 1].set_title("2. Curva de Bankroll (Saldo de Fichas)", fontsize=11.5, fontweight="bold")
    axes[0, 1].set_xlabel("Mãos")
    axes[0, 1].set_ylabel("Fichas Acumuladas")
    axes[0, 1].grid(True, linestyle="--", alpha=0.45)
    axes[0, 1].legend(fontsize=8, loc="upper left")

    # 3. Tipos de Blefe (Inferior Esquerdo)
    df_bluffs = df_telemetry[df_telemetry["is_bluff"] == True]  # noqa: E712
    if len(df_bluffs) > 0:
        type_counts = df_bluffs["bluff_type"].value_counts()
        type_labels = {
            "PURE_BLUFF": "Puro",
            "SEMI_BLUFF": "Semi-Blefe",
            "CBET_BLUFF": "C-Bet",
            "STEAL_BLUFF": "Roubo",
        }
        clean_lbls = [type_labels.get(k, k) for k in type_counts.index]
        axes[1, 0].bar(clean_lbls, type_counts.values, color="#e67e22", edgecolor="#222", width=0.5)
        for bar in axes[1, 0].patches:
            h = bar.get_height()
            axes[1, 0].annotate(
                f"{int(h)}",
                xy=(bar.get_x() + bar.get_width() / 2, h),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=9,
            )
    axes[1, 0].set_title("3. Frequência por Tipo de Blefe", fontsize=11.5, fontweight="bold")
    axes[1, 0].set_ylabel("Tentativas")
    axes[1, 0].grid(axis="y", linestyle="--", alpha=0.45)

    # 4. Aceitação vs Recusa (Inferior Direito)
    if len(df_bluffs) > 0:
        resp_counts = df_bluffs["opponent_response"].value_counts()
        resp_labels = {
            "ACCEPTED_ALL_FOLD": "Aceito (Fold)",
            "REFUSED_CALLED": "Recusado (Call)",
            "REFUSED_RAISED": "Recusado (Raise)",
        }
        clean_resp = [resp_labels.get(k, k) for k in resp_counts.index]
        axes[1, 1].pie(
            resp_counts.values,
            labels=clean_resp,
            autopct="%1.1f%%",
            startangle=140,
            colors=["#2ecc71", "#e74c3c", "#f39c12"][: len(clean_resp)],
            wedgeprops=dict(edgecolor="#222", linewidth=1.2),
            textprops=dict(fontweight="bold", fontsize=9),
        )
    axes[1, 1].set_title("4. Resposta aos Blefes (Aceito vs Recusado)", fontsize=11.5, fontweight="bold")

    plt.suptitle(
        f"PAINEL CONSOLIDADO DE RESULTADOS - EXPERIMENTO TCC ({total_hands} Mãos)",
        fontsize=14,
        fontweight="bold",
        y=0.99,
    )
    plt.tight_layout()

    out_file = output_dir / "dashboard_consolidado_tcc.png"
    plt.savefig(out_file)
    plt.close()
    return out_file


def generate_all_plots(data_dir: str = "data", output_dir: str = "data/plots") -> List[Path]:
    """Lê os CSVs gerados e produz todos os gráficos para o TCC."""
    d_dir = Path(data_dir)
    o_dir = Path(output_dir)
    o_dir.mkdir(parents=True, exist_ok=True)

    actions_file = d_dir / "game_actions.csv"
    telemetry_file = d_dir / "decision_telemetry_and_bluffs.csv"

    if not actions_file.exists() or not telemetry_file.exists():
        raise FileNotFoundError(
            f"Arquivos CSV não encontrados em {data_dir}. Execute antes o gerador de telemetria."
        )

    df_actions = pd.read_csv(actions_file)
    df_telemetry = pd.read_csv(telemetry_file)

    print("=" * 80)
    print("📈 GERADOR DE GRÁFICOS CIENTÍFICOS DO CAMPEONATO (TCC POKER IA)")
    print("=" * 80)
    print(f"• Arquivo de Ações      : {actions_file} ({len(df_actions):,} linhas)")
    print(f"• Arquivo de Telemetria : {telemetry_file} ({len(df_telemetry):,} linhas)")
    print(f"• Diretório de Saída    : {o_dir}/")
    print("-" * 80)

    generated: List[Path] = []

    print("▶ 1/5 Gerando gráfico de vitórias por agente...")
    f1 = plot_win_rates(df_actions, df_telemetry, o_dir)
    generated.append(f1)
    print(f"  ✓ Salvo em: {f1}")

    print("▶ 2/5 Gerando curva de evolução de bankroll...")
    f2 = plot_bankroll_evolution(df_actions, df_telemetry, o_dir)
    generated.append(f2)
    print(f"  ✓ Salvo em: {f2}")

    print("▶ 3/5 Gerando matriz de confronto direto (quem ganhou de quem)...")
    f3 = plot_head_to_head_matrix(df_actions, df_telemetry, o_dir)
    generated.append(f3)
    print(f"  ✓ Salvo em: {f3}")

    print("▶ 4/5 Gerando análise anatômica de blefes...")
    f4 = plot_bluff_analysis(df_telemetry, o_dir)
    generated.append(f4)
    print(f"  ✓ Salvo em: {f4}")

    print("▶ 5/5 Gerando painel consolidado para a banca (Dashboard 2x2)...")
    f5 = plot_consolidated_dashboard(df_actions, df_telemetry, o_dir)
    generated.append(f5)
    print(f"  ✓ Salvo em: {f5}")

    print("=" * 80)
    print(f"✨ Sucesso! {len(generated)} gráficos gerados com sucesso em 300 DPI.")
    print("=" * 80)
    return generated


if __name__ == "__main__":
    generate_all_plots()
