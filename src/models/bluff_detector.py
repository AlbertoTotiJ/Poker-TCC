"""Módulo de Inferência em Tempo Real para Análise e Detecção de Blefes.

Carrega o modelo supervisionado treinado (Random Forest / Gradient Boosting)
e avalia se uma aposta realizada por qualquer adversário na mesa é um blefe ou valor.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import joblib
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_PATH = _ROOT / "models" / "bluff_detector_model.joblib"


class BluffDetector:
    """Detector de Blefe em Tempo Real para Texas Hold'em Poker."""

    def __init__(self, model_path: Optional[Path] = None):
        path = model_path if model_path is not None else MODEL_PATH
        if not path.exists():
            # Fallback para o arquivo no diretório 04
            alt_path = _ROOT / "data" / "04_ml_sprint4_consolidado" / "best_model.joblib"
            if alt_path.exists():
                path = alt_path
            else:
                raise FileNotFoundError(f"Modelo de detecção de blefe não encontrado em {path} nem em {alt_path}")

        self.model = joblib.load(path)
        self.model_path = path

    def _prepare_sample_df(self, features: Dict[str, Any]) -> pd.DataFrame:
        """Estrutura os atributos de entrada no formato esperado pelo pipeline."""
        pot_before = float(features.get("pot_before", 50.0))
        amount = float(features.get("amount", 20.0))
        stack = float(features.get("player_stack_before", 1000.0))
        pot_odds = float(features.get("pot_odds", 0.25))
        raw_equity = float(features.get("raw_equity", 0.35))

        bet_to_pot = amount / max(1.0, pot_before)
        spr = stack / max(1.0, pot_before)
        equity_disp = raw_equity - pot_odds

        profile_raw = str(features.get("profile", features.get("bettor_profile", "Outro"))).lower()
        if "matemático" in profile_raw or "math" in profile_raw:
            clean_profile = "Matemático"
        elif "blefador" in profile_raw or "bluffer" in profile_raw:
            clean_profile = "Blefador"
        elif "híbrido" in profile_raw or "hybrid" in profile_raw:
            clean_profile = "Híbrido"
        else:
            clean_profile = "Outro"

        sample = {
            "street": str(features.get("street", "FLOP")).upper(),
            "action_taken": str(features.get("action_taken", "BET")).upper(),
            "bettor_profile": clean_profile,
            "amount": amount,
            "pot_before": pot_before,
            "bet_to_pot_ratio": bet_to_pot,
            "stack_to_pot_ratio": spr,
            "pot_odds": pot_odds,
            "outs_count": int(features.get("outs_count", 0)),
            "raw_equity": raw_equity,
            "equity_disparity": equity_disp,
        }
        return pd.DataFrame([sample])

    def predict_bluff_probability(self, features: Dict[str, Any]) -> float:
        """Retorna a probabilidade P(Blefe) calibrada entre 0.0 e 1.0."""
        df = self._prepare_sample_df(features)
        proba = self.model.predict_proba(df)[0, 1]
        return float(proba)

    def predict_is_bluff(self, features: Dict[str, Any], threshold: float = 0.50) -> bool:
        """Classifica se a aposta é considerada blefe de acordo com o limiar configurado."""
        p = self.predict_bluff_probability(features)
        return p >= threshold

    def analyze_bet(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Gera relatório de diagnóstico detalhado da aposta."""
        prob = self.predict_bluff_probability(features)
        is_bluff = prob >= 0.50

        if prob >= 0.75:
            confidence = "ALTO_RISCO_BLEFE"
            recommendation = "Re-aumentar ou dar Call (Vilão muito polarizado para blefe)."
        elif prob >= 0.50:
            confidence = "MODERADO_BLEFE"
            recommendation = "Call cauteloso com mãos de valor médio (Bluff Catcher)."
        elif prob >= 0.30:
            confidence = "PROVAVEL_VALOR"
            recommendation = "Vilão tem equidade real; foldar mãos marginais."
        else:
            confidence = "FORTE_VALOR"
            recommendation = "Monstro ou valor sólido; desistir sem as nuts."

        return {
            "bluff_probability": round(prob, 4),
            "is_bluff": is_bluff,
            "verdict": confidence,
            "tactical_recommendation": recommendation,
        }
