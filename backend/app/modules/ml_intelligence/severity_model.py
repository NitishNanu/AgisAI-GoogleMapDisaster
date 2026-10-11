"""
AegisAI ML Intelligence — XGBoost Disaster Severity Scoring Model.

Provides real Machine Learning severity classification and confidence scoring:
- Maps incident dynamics (casualties, radius, weather, disaster type) to severity classes:
  LOW (0), MEDIUM (1), HIGH (2), CRITICAL (3).
- Dynamically computes priority cost weight for Kuhn-Munkres multi-resource allocation.
- Auto-trains and serializes a high-accuracy gradient-boosted tree model if no saved model exists.
"""

from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger("aegis_ai.ml.severity")

SEVERITY_CLASSES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
DISASTER_TYPE_MAP = {
    "FIRE": 0,
    "FLOOD": 1,
    "EARTHQUAKE": 2,
    "HAZMAT": 3,
    "INDUSTRIAL": 4,
    "MEDICAL": 5,
    "OTHER": 6,
}

MODEL_PATH = Path(__file__).parent / "disaster_severity_xgb.json"


class DisasterSeverityModel:
    _instance: Any = None
    _model: Any = None

    def __init__(self):
        self._initialize_model()

    @classmethod
    def get_instance(cls) -> "DisasterSeverityModel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_model(self) -> None:
        """Load pre-trained model or train synthetic disaster benchmark model."""
        try:
            import xgboost as xgb

            self._model = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.08,
                objective="multi:softprob",
                num_class=4,
                random_state=42,
            )

            if MODEL_PATH.exists():
                try:
                    self._model.load_model(str(MODEL_PATH))
                    logger.info("xgboost_severity_model_loaded", path=str(MODEL_PATH))
                    return
                except Exception as load_err:
                    logger.warning("xgboost_model_load_failed_retraining", error=str(load_err))

            # Train synthetic training dataset
            self._train_initial_model()
            try:
                self._model.save_model(str(MODEL_PATH))
                logger.info("xgboost_severity_model_trained_and_saved", path=str(MODEL_PATH))
            except Exception as save_err:
                logger.warning("xgboost_model_save_failed", error=str(save_err))

        except ImportError:
            logger.warning("xgboost_not_installed_using_heuristic_fallback")
            self._model = None

    def _train_initial_model(self) -> None:
        """Generate realistic synthetic disaster training samples and fit XGBoost."""
        np.random.seed(42)
        n_samples = 2000

        # Features: [casualties, critical, radius_m, wind_kmh, rain_mm, type_code, priority]
        casualties = np.random.exponential(scale=12.0, size=n_samples)
        critical = np.random.binomial(n=np.maximum(1, casualties.astype(int)), p=0.25)
        radius = np.random.uniform(50, 3000, size=n_samples)
        wind = np.random.uniform(0, 80, size=n_samples)
        rain = np.random.uniform(0, 100, size=n_samples)
        dtype = np.random.choice(list(DISASTER_TYPE_MAP.values()), size=n_samples)
        priority = np.random.uniform(1.0, 5.0, size=n_samples)

        X = np.column_stack([casualties, critical, radius, wind, rain, dtype, priority])

        # Target classification logic:
        # Score combining life threat, expansion potential, and environmental multiplier
        threat_score = (
            casualties * 2.5
            + critical * 5.0
            + (radius / 500.0)
            + (wind / 20.0)
            + (priority * 4.0)
        )

        y = np.zeros(n_samples, dtype=int)
        y[threat_score >= 15] = 1  # MEDIUM
        y[threat_score >= 35] = 2  # HIGH
        y[threat_score >= 65] = 3  # CRITICAL

        self._model.fit(X, y)

    def extract_features(self, payload: dict[str, Any]) -> np.ndarray:
        """Extract normalized numeric feature vector from incident or request payload."""
        casualties_raw = payload.get("estimated_casualties")
        if casualties_raw is None:
            casualties_raw = payload.get("casualties", 0)
        casualties = float(casualties_raw if casualties_raw is not None else 0)

        critical_raw = payload.get("critical_patients", 0)
        critical = float(critical_raw if critical_raw is not None else 0)

        radius_raw = payload.get("affected_radius_meters")
        if radius_raw is None:
            radius_raw = payload.get("radius_meters", 100)
        radius = float(radius_raw if radius_raw is not None else 100)

        wind_raw = payload.get("wind_speed_kmh", 15.0)
        wind = float(wind_raw if wind_raw is not None else 15.0)

        rain_raw = payload.get("rainfall_mm", 0.0)
        rain = float(rain_raw if rain_raw is not None else 0.0)

        raw_type = str(payload.get("disaster_type") or "OTHER").upper()
        dtype_code = DISASTER_TYPE_MAP.get(raw_type, 6)
        priority_raw = payload.get("priority", 3.0)
        priority = float(priority_raw if priority_raw is not None else 3.0)

        return np.array([[casualties, critical, radius, wind, rain, dtype_code, priority]], dtype=np.float32)

    def predict_severity(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Perform real ML inference on disaster features.
        Returns:
            predicted_severity: str (LOW | MEDIUM | HIGH | CRITICAL)
            confidence: float (0.0 - 1.0)
            probabilities: dict of class -> probability
            severity_multiplier: float (multiplier for Kuhn-Munkres weight allocation)
        """
        features = self.extract_features(payload)

        if self._model is None:
            # Fallback if xgboost is unavailable
            cas = float(payload.get("estimated_casualties", 0))
            crit = float(payload.get("critical_patients", 0))
            if crit > 5 or cas > 30:
                sev, conf, mult = "CRITICAL", 0.90, 1.8
            elif crit > 2 or cas > 15:
                sev, conf, mult = "HIGH", 0.85, 1.4
            elif cas > 5:
                sev, conf, mult = "MEDIUM", 0.75, 1.1
            else:
                sev, conf, mult = "LOW", 0.70, 0.9
            return {
                "predicted_severity": sev,
                "confidence": conf,
                "probabilities": {c: (0.7 if c == sev else 0.1) for c in SEVERITY_CLASSES},
                "severity_multiplier": mult,
                "model_version": "heuristic_fallback",
            }

        probs = self._model.predict_proba(features)[0]
        pred_idx = int(np.argmax(probs))
        pred_severity = SEVERITY_CLASSES[pred_idx]
        confidence = float(probs[pred_idx])

        # Multipliers for Kuhn-Munkres optimizer priority matrix:
        # Higher multiplier increases urgency of matching top rescue resources
        multipliers = {"LOW": 0.85, "MEDIUM": 1.10, "HIGH": 1.45, "CRITICAL": 1.95}

        return {
            "predicted_severity": pred_severity,
            "confidence": round(confidence, 4),
            "probabilities": {
                SEVERITY_CLASSES[i]: round(float(probs[i]), 4) for i in range(len(SEVERITY_CLASSES))
            },
            "severity_multiplier": multipliers[pred_severity],
            "model_version": "xgboost-disaster-v1",
        }
