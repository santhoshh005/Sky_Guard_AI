"""Autoencoder inference module for SkyGuard AI.
Implements reconstruction error scoring and per-parameter error decomposition.
Specified in /docs/HANDOFF.md §3.3, §14.2.
"""
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.services.feature_engineer import PARAMETERS

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


class AutoencoderInference:
    def __init__(self, model_dir: Optional[Path] = None):
        self.model_dir = model_dir or MODEL_DIR
        self.model = None
        self.scaler = None
        self.threshold = 1.0
        self.per_param_thresholds: Dict[str, float] = {}
        self.load_models()

    def load_models(self):
        model_path = self.model_dir / "autoencoder.pkl"
        scaler_path = self.model_dir / "ae_scaler.pkl"
        thresh_path = self.model_dir / "ae_threshold.pkl"

        if model_path.exists() and scaler_path.exists() and thresh_path.exists():
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)
            with open(scaler_path, "rb") as f:
                self.scaler = pickle.load(f)
            with open(thresh_path, "rb") as f:
                data = pickle.load(f)
                if isinstance(data, dict):
                    self.threshold = float(data.get("threshold", 1.0))
                    self.per_param_thresholds = data.get("per_param", {})
                else:
                    self.threshold = float(data)

    def score(self, compact_vector: np.ndarray) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Compute normalized Autoencoder reconstruction score [0, 1].
        
        Returns:
            Tuple of:
              - ae_score: float [0, 1]
              - scaled_original: 14-dim numpy array
              - reconstructed: 14-dim numpy array
        """
        if self.model is None or self.scaler is None:
            return 0.0, compact_vector, compact_vector

        vec_2d = compact_vector.reshape(1, -1)
        scaled_orig = self.scaler.transform(vec_2d)
        reconstructed = self.model.predict(scaled_orig)

        mse = float(np.mean((scaled_orig[0] - reconstructed[0]) ** 2))
        ae_score = float(min(1.0, mse / max(1e-6, self.threshold)))
        return ae_score, scaled_orig[0], reconstructed[0]

    def get_per_parameter_error(
        self,
        reconstructed: np.ndarray,
        original: np.ndarray,
        param: str
    ) -> float:
        """
        Compute per-parameter reconstruction error across its 2 dims (raw + delta).
        Specified in §14.2.
        """
        if param not in PARAMETERS:
            return 0.0
        i = PARAMETERS.index(param)
        raw_err = float((original[i] - reconstructed[i]) ** 2)
        delta_err = float((original[i + 7] - reconstructed[i + 7]) ** 2)
        mean_err = (raw_err + delta_err) / 2.0

        # Calibrated scaling using per-param threshold if available, otherwise 1/7 share
        thresh = self.per_param_thresholds.get(param, self.threshold / 7.0)
        scaled_err = float(min(1.0, mean_err / max(1e-6, thresh)))
        return scaled_err
