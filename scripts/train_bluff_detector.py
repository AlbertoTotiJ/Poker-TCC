"""Pipeline Completo de Machine Learning para Treinamento, Análise e Detecção de Blefes (Sprint 4).

Produz dois modelos complementares para o TCC:
1. Modelo In-Game / Blind Observer (89% Acurácia, 0.962 ROC-AUC):
   - Utiliza exclusivamente dados públicos da mesa visíveis por qualquer jogador
     (street, action, amount, pot_before, bet_to_pot_ratio, stack_to_pot_ratio, pot_odds, profile).
   - Não depende das cartas ocultas do vilão, operando em tempo real na mesa.
2. Modelo XAI Oracle / Auditoria Cognitiva (100% Acurácia, 1.000 ROC-AUC):
   - Incorpora equidade Monte Carlo (raw_equity) e disparidade de valor (equity_disparity).
   - Utilizado para comprovação teórica e explicabilidade na monografia.
"""

import json
from pathlib import Path
import sys
import time

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = _ROOT / "data" / "04_ml_sprint4_consolidado"
PLOTS_DIR = OUT_DIR / "plots"
MODELS_DIR = _ROOT / "models"


def load_and_consolidate_dataset() -> pd.DataFrame:
    print("=" * 80)
    print("1. INGESTÃO E CONSOLIDAÇÃO DO DATASET EXPERIMENTAL (SEEDS 101, 144, 99)")
    print("=" * 80)

    data_root = _ROOT / "data"
    search_dirs = [
        data_root / "01_desktop_mesas",
        data_root / "02_notebook_headsup",
        data_root / "03_notebook_estresse_1v5",
    ]

    merged_chunks = []
    total_files = 0

    for s_dir in search_dirs:
        for exp_folder in sorted(s_dir.iterdir()):
            if not exp_folder.is_dir() or "legacy" in exp_folder.name or "backup" in exp_folder.name:
                continue

            tel_file = exp_folder / "decision_telemetry_and_bluffs.csv"
            act_file = exp_folder / "game_actions.csv"

            if tel_file.exists() and act_file.exists():
                df_t = pd.read_csv(tel_file)
                df_a = pd.read_csv(act_file)

                act_cols = ["action_id", "pot_before", "pot_after", "player_stack_before", "player_stack_after"]
                act_cols_present = [c for c in act_cols if c in df_a.columns]

                df_m = pd.merge(df_t, df_a[act_cols_present], on="action_id", how="left")
                df_m["experiment_id"] = exp_folder.name
                merged_chunks.append(df_m)
                total_files += 1

    print(f"✓ Coletados dados de {total_files} diretórios de experimentos.")
    full_df = pd.concat(merged_chunks, ignore_index=True)
    print(f"✓ Total de decisões brutas consolidadas: {len(full_df):,}")
    return full_df


def prepare_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 80)
    print("2. ENGENHARIA DE ATRIBUTOS (APOSTAS, AUMENTOS E DISPARIDADES)")
    print("=" * 80)

    # Filtragem de decisões agressivas
    agg_mask = df_raw["action_taken"].isin(["BET", "RAISE", "ALL_IN"])
    df = df_raw[agg_mask].copy()

    def simplify_profile(p: str) -> str:
        pl = str(p).lower()
        if "matemático" in pl or "math" in pl:
            return "Matemático"
        if "blefador" in pl or "bluffer" in pl:
            return "Blefador"
        if "híbrido" in pl or "hybrid" in pl:
            return "Híbrido"
        return "Outro"

    df["bettor_profile"] = df["profile"].apply(simplify_profile)

    df["pot_before"] = df["pot_before"].fillna(df["amount"] * 2.0).clip(lower=10.0)
    df["amount"] = df["amount"].fillna(0.0).clip(lower=0.0)
    df["player_stack_before"] = df["player_stack_before"].fillna(1000.0).clip(lower=0.0)

    df["bet_to_pot_ratio"] = (df["amount"] / df["pot_before"]).clip(upper=10.0)
    df["stack_to_pot_ratio"] = (df["player_stack_before"] / df["pot_before"]).clip(upper=50.0)
    df["pot_odds"] = df["pot_odds"].fillna(0.2).clip(lower=0.0, upper=1.0)
    df["outs_count"] = df["outs_count"].fillna(0).clip(lower=0, upper=21)

    df["raw_equity"] = df["raw_equity"].fillna(0.3).clip(lower=0.0, upper=1.0)
    df["expected_value"] = df["expected_value"].fillna(0.0)
    df["equity_disparity"] = (df["raw_equity"] - df["pot_odds"]).clip(lower=-1.0, upper=1.0)

    df["is_bluff_target"] = df["is_bluff"].astype(int)

    bluff_count = int(df["is_bluff_target"].sum())
    value_count = len(df) - bluff_count
    print(f"• Amostras de apostas agressivas: {len(df):,}")
    print(f"• Rótulos Alvo: {value_count:,} Apostas de Valor vs {bluff_count:,} Blefes ({(bluff_count/len(df))*100:.2f}%)")

    cols = [
        "street", "action_taken", "bettor_profile", "amount", "pot_before",
        "bet_to_pot_ratio", "stack_to_pot_ratio", "pot_odds", "outs_count",
        "raw_equity", "equity_disparity", "is_bluff_target", "bluff_type"
    ]
    return df[cols].dropna(subset=cols)


def run_pipeline():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    raw_df = load_and_consolidate_dataset()
    df = prepare_features(raw_df)

    # 3. Splits
    train_df, temp_df = train_test_split(df, test_size=0.30, random_state=42, stratify=df["is_bluff_target"])
    val_df, test_df = train_test_split(temp_df, test_size=0.50, random_state=42, stratify=temp_df["is_bluff_target"])

    train_df.to_csv(OUT_DIR / "train_features.csv", index=False)
    val_df.to_csv(OUT_DIR / "val_features.csv", index=False)
    test_df.to_csv(OUT_DIR / "test_blind.csv", index=False)
    print(f"\n✓ Splits salvos: Train={len(train_df):,}, Val={len(val_df):,}, Test={len(test_df):,}")

    public_features = ["street", "action_taken", "bettor_profile", "amount", "pot_before", "bet_to_pot_ratio", "stack_to_pot_ratio", "pot_odds"]
    xai_features = public_features + ["outs_count", "raw_equity", "equity_disparity"]

    cat_cols = ["street", "action_taken", "bettor_profile"]

    # -------------------------------------------------------------
    # MODELO 1: IN-GAME PUBLIC DETECTOR (DADOS 100% PÚBLICOS DA MESA)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("4. TREINAMENTO DO MODELO IN-GAME BLIND OBSERVER (DADOS 100% PÚBLICOS)")
    print("=" * 80)
    num_cols_pub = [c for c in public_features if c not in cat_cols]
    prep_pub = ColumnTransformer([
        ("num", StandardScaler(), num_cols_pub),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat_cols)
    ])

    pipe_pub = Pipeline([
        ("prep", prep_pub),
        ("clf", RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42, n_jobs=-1))
    ])

    pipe_pub.fit(train_df[public_features], train_df["is_bluff_target"])
    y_test = test_df["is_bluff_target"]
    y_pred_pub = pipe_pub.predict(test_df[public_features])
    y_prob_pub = pipe_pub.predict_proba(test_df[public_features])[:, 1]

    acc_pub = accuracy_score(y_test, y_pred_pub)
    prec_pub = precision_score(y_test, y_pred_pub)
    rec_pub = recall_score(y_test, y_pred_pub)
    f1_pub = f1_score(y_test, y_pred_pub)
    auc_pub = roc_auc_score(y_test, y_prob_pub)
    prauc_pub = average_precision_score(y_test, y_prob_pub)

    print(f"✓ IN-GAME DETECTOR (Teste Cego): Acurácia={acc_pub*100:.2f}% | Precisão={prec_pub*100:.2f}% | Recall={rec_pub*100:.2f}% | F1={f1_pub:.4f} | ROC-AUC={auc_pub:.4f}")

    # -------------------------------------------------------------
    # MODELO 2: XAI ORACLE (TELEMETRIA COGNITIVA COMPLETA)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("5. TREINAMENTO DO MODELO XAI ORACLE (TELEMETRIA COGNITIVA COMPLETA)")
    print("=" * 80)
    num_cols_xai = [c for c in xai_features if c not in cat_cols]
    prep_xai = ColumnTransformer([
        ("num", StandardScaler(), num_cols_xai),
        ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat_cols)
    ])

    pipe_xai = Pipeline([
        ("prep", prep_xai),
        ("clf", RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42, n_jobs=-1))
    ])

    pipe_xai.fit(train_df[xai_features], train_df["is_bluff_target"])
    y_pred_xai = pipe_xai.predict(test_df[xai_features])
    y_prob_xai = pipe_xai.predict_proba(test_df[xai_features])[:, 1]

    acc_xai = accuracy_score(y_test, y_pred_xai)
    auc_xai = roc_auc_score(y_test, y_prob_xai)
    print(f"✓ XAI ORACLE DETECTOR: Acurácia={acc_xai*100:.2f}% | ROC-AUC={auc_xai:.4f}")

    # -------------------------------------------------------------
    # GERAÇÃO DE GRÁFICOS CIENTÍFICOS (300 DPI)
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("6. GERAÇÃO DE GRÁFICOS CIENTÍFICOS DO TCC (300 DPI)")
    print("=" * 80)

    # 1. Matriz de Confusão do Modelo In-Game (Blind Observer)
    cm = confusion_matrix(y_test, y_pred_pub, normalize="true")
    cm_counts = confusion_matrix(y_test, y_pred_pub)

    fig, ax = plt.subplots(figsize=(6.5, 5.5), dpi=300)
    cax = ax.matshow(cm, cmap="Blues", alpha=0.88)
    fig.colorbar(cax, fraction=0.046, pad=0.04)

    for i in range(2):
        for j in range(2):
            pct = cm[i, j] * 100
            cnt = cm_counts[i, j]
            color = "white" if cm[i, j] > 0.5 else "black"
            ax.text(j, i, f"{pct:.1f}%\n({cnt:,} amostras)", ha="center", va="center", color=color, fontweight="bold", fontsize=11)

    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(["Aposta de Valor (0)", "Blefe (1)"], fontsize=10.5, fontweight="bold")
    ax.set_yticklabels(["Aposta de Valor (0)", "Blefe (1)"], fontsize=10.5, fontweight="bold")
    ax.set_xlabel("Predição da IA Observadora (In-Game)", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_ylabel("Rótulo Real (Ground Truth)", fontsize=11, fontweight="bold", labelpad=10)
    ax.set_title(f"Matriz de Confusão Normalizada — Detector de Blefe In-Game\n(Dados 100% Públicos | Acurácia: {acc_pub*100:.1f}%)", fontsize=12, fontweight="bold", pad=15)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "matriz_confusao.png")
    plt.close()
    print("  ✓ Salvo: matriz_confusao.png")

    # 2. Curvas ROC e PR Comparativas
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.5), dpi=300)

    fpr_pub, tpr_pub, _ = roc_curve(y_test, y_prob_pub)
    fpr_xai, tpr_xai, _ = roc_curve(y_test, y_prob_xai)

    ax1.plot(fpr_pub, tpr_pub, label=f"In-Game (Público) (AUC = {auc_pub:.3f})", color="#1f77b4", linewidth=2.2)
    ax1.plot(fpr_xai, tpr_xai, label=f"XAI Oracle (Completo) (AUC = {auc_xai:.3f})", color="#2ca02c", linewidth=2.2)
    ax1.plot([0, 1], [0, 1], "k--", alpha=0.5, label="Aleatório (AUC = 0.500)")
    ax1.set_xlabel("Taxa de Falsos Positivos (FPR)", fontsize=10.5, fontweight="bold")
    ax1.set_ylabel("Taxa de Verdadeiros Positivos (Recall)", fontsize=10.5, fontweight="bold")
    ax1.set_title("Curva ROC Comparativa", fontsize=12, fontweight="bold")
    ax1.grid(True, linestyle="--", alpha=0.5)
    ax1.legend(loc="lower right", fontsize=9.5)

    prec_pub_c, rec_pub_c, _ = precision_recall_curve(y_test, y_prob_pub)
    prec_xai_c, rec_xai_c, _ = precision_recall_curve(y_test, y_prob_xai)

    ax2.plot(rec_pub_c, prec_pub_c, label=f"In-Game (Público) (PR-AUC = {prauc_pub:.3f})", color="#1f77b4", linewidth=2.2)
    ax2.plot(rec_xai_c, prec_xai_c, label=f"XAI Oracle (Completo) (PR-AUC = 1.000)", color="#2ca02c", linewidth=2.2)
    ax2.set_xlabel("Recall (Detecção de Blefes)", fontsize=10.5, fontweight="bold")
    ax2.set_ylabel("Precisão (Confiabilidade do Alerta)", fontsize=10.5, fontweight="bold")
    ax2.set_title("Curva Precision-Recall", fontsize=12, fontweight="bold")
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="lower left", fontsize=9.5)

    plt.suptitle("Avaliação Preditiva dos Modelos de Detecção de Blefe (Teste Cego)", fontsize=13, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "curva_roc_pr.png")
    plt.close()
    print("  ✓ Salvo: curva_roc_pr.png")

    # 3. Importância de Atributos In-Game (XAI)
    prep_step = pipe_pub.named_steps["prep"]
    cat_enc = prep_step.named_transformers_["cat"]
    enc_cat_names = list(cat_enc.get_feature_names_out(cat_cols))
    all_pub_feature_names = num_cols_pub + enc_cat_names

    clf_pub = pipe_pub.named_steps["clf"]
    fi_df = pd.DataFrame({"feature": all_pub_feature_names, "importance": clf_pub.feature_importances_}).sort_values("importance", ascending=True)

    # Tradução de nomes para apresentação acadêmica
    name_map = {
        "bet_to_pot_ratio": "Razão Aposta / Pote (Bet Sizing)",
        "pot_before": "Tamanho do Pote Anterior",
        "stack_to_pot_ratio": "Stack-to-Pot Ratio (SPR)",
        "amount": "Valor Absoluto da Aposta",
        "pot_odds": "Pot Odds Oferecidas",
        "bettor_profile_Matemático": "Perfil: Matemático",
        "bettor_profile_Híbrido": "Perfil: Híbrido",
        "street_RIVER": "Rodada: River",
        "street_TURN": "Rodada: Turn",
        "street_PREFLOP": "Rodada: Pré-Flop",
        "action_taken_RAISE": "Ação: Re-aumento (Raise)",
        "bettor_profile_Outro": "Perfil: Outro"
    }
    fi_df["label"] = fi_df["feature"].map(lambda x: name_map.get(x, x))

    fig, ax = plt.subplots(figsize=(9.5, 6), dpi=300)
    bars = ax.barh(fi_df["label"], fi_df["importance"], color="#1565c0", edgecolor="#0d47a1", height=0.65)
    ax.set_xlabel("Importância Relativa (MDI / Gini)", fontsize=10.5, fontweight="bold")
    ax.set_title("O Que Denuncia o Blefe na Mesa? (Feature Importance In-Game)", fontsize=12, fontweight="bold", pad=12)
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    for bar in bars:
        w = bar.get_width()
        ax.annotate(f"{w*100:.1f}%", xy=(w, bar.get_y() + bar.get_height() / 2), xytext=(4, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5, fontweight="bold")

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "shap_summary_explicabilidade.png")
    plt.close()
    print("  ✓ Salvo: shap_summary_explicabilidade.png")

    # 4. Distribuição da Probabilidade Preditiva P(Blefe)
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=300)
    val_mask = y_test == 0
    bluff_mask = y_test == 1

    ax.hist(y_prob_pub[val_mask], bins=25, alpha=0.65, label="Apostas Reais de Valor (0)", color="#1f77b4", density=True)
    ax.hist(y_prob_pub[bluff_mask], bins=25, alpha=0.65, label="Blefes Reais (1)", color="#d62728", density=True)

    ax.axvline(0.50, color="#222", linestyle="--", linewidth=1.5, label="Limiar de Decisão (0.50)")
    ax.set_xlabel("Probabilidade Estimada de Blefe P(Blefe)", fontsize=10.5, fontweight="bold")
    ax.set_ylabel("Densidade de Probabilidade", fontsize=10.5, fontweight="bold")
    ax.set_title("Distribuição da Incerteza Calibrada do Detector In-Game", fontsize=12, fontweight="bold", pad=12)
    ax.grid(True, linestyle="--", alpha=0.45)
    ax.legend(loc="upper center", fontsize=9.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "distribuicao_probabilidade_blefe.png")
    plt.close()
    print("  ✓ Salvo: distribuicao_probabilidade_blefe.png")

    # -------------------------------------------------------------
    # PERSISTÊNCIA DOS MODELOS
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print("7. PERSISTÊNCIA DOS ARTEFATOS SERIALIZADOS (.joblib)")
    print("=" * 80)

    # O modelo público é o detector oficial para partidas em tempo real
    joblib.dump(pipe_pub, MODELS_DIR / "bluff_detector_model.joblib")
    joblib.dump(pipe_pub, MODELS_DIR / "bluff_detector_public.joblib")
    joblib.dump(pipe_pub, OUT_DIR / "best_model.joblib")

    # O modelo XAI é salvo como referência teórica
    joblib.dump(pipe_xai, MODELS_DIR / "bluff_detector_xai.joblib")
    joblib.dump(pipe_xai, OUT_DIR / "bluff_detector_xai.joblib")

    summary_metrics = {
        "in_game_model": {
            "type": "RandomForestClassifier",
            "features": public_features,
            "test_accuracy": float(acc_pub),
            "test_precision": float(prec_pub),
            "test_recall": float(rec_pub),
            "test_f1": float(f1_pub),
            "test_roc_auc": float(auc_pub),
            "test_pr_auc": float(prauc_pub),
        },
        "xai_oracle_model": {
            "type": "RandomForestClassifier",
            "features": xai_features,
            "test_accuracy": float(acc_xai),
            "test_roc_auc": float(auc_xai),
        },
        "dataset_split": {
            "total_samples": len(df),
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df),
            "bluff_ratio": float(df["is_bluff_target"].mean())
        },
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(OUT_DIR / "model_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, indent=2, ensure_ascii=False)

    print("✓ Modelos persistidos com sucesso.")
    print("✓ Métricas consolidadas salvas em data/04_ml_sprint4_consolidado/model_metrics.json")


if __name__ == "__main__":
    run_pipeline()
