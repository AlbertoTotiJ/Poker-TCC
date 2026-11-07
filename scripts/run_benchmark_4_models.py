import time
from pathlib import Path
import json
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score
)

out_dir = Path("data/04_ml_sprint4_consolidado")
train_df = pd.read_csv(out_dir / "train_features.csv")
test_df = pd.read_csv(out_dir / "test_blind.csv")

public_features = [
    "street", "action_taken", "bettor_profile", "amount", "pot_before",
    "bet_to_pot_ratio", "stack_to_pot_ratio", "pot_odds"
]
cat_cols = ["street", "action_taken", "bettor_profile"]
num_cols = [c for c in public_features if c not in cat_cols]

prep = ColumnTransformer([
    ("num", StandardScaler(), num_cols),
    ("cat", OneHotEncoder(drop="first", handle_unknown="ignore"), cat_cols)
])

models = {
    "Random Forest": RandomForestClassifier(n_estimators=150, max_depth=12, random_state=42, n_jobs=-1),
    "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=150, max_depth=10, random_state=42),
    "Regressão Logística": LogisticRegression(max_iter=1000, random_state=42, C=1.0),
    "Rede Neural MLP": MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=200, random_state=42, early_stopping=True)
}

y_train = train_df["is_bluff_target"]
y_test = test_df["is_bluff_target"]

res = {}
for name, clf in models.items():
    t0 = time.time()
    pipe = Pipeline([("prep", prep), ("clf", clf)])
    pipe.fit(train_df[public_features], y_train)
    t_train = time.time() - t0

    y_pred = pipe.predict(test_df[public_features])
    y_prob = pipe.predict_proba(test_df[public_features])[:, 1]

    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "f1": float(f1_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_prob)),
        "pr_auc": float(average_precision_score(y_test, y_prob)),
        "training_time_sec": float(t_train)
    }
    res[name] = metrics
    print(f"✓ {name:22s} | Acc: {metrics['accuracy']*100:6.2f}% | Prec: {metrics['precision']*100:6.2f}% | Rec: {metrics['recall']*100:6.2f}% | F1: {metrics['f1']:.4f} | ROC-AUC: {metrics['roc_auc']:.4f} | Tempo: {t_train:5.2f}s")

with open(out_dir / "benchmark_4_models.json", "w", encoding="utf-8") as f:
    json.dump(res, f, indent=2, ensure_ascii=False)
print("Benchmark salvo com sucesso em benchmark_4_models.json")
