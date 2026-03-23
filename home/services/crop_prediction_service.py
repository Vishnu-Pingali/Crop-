import os
import pickle
from dataclasses import dataclass, field
from typing import Dict

import pandas as pd
from django.conf import settings


@dataclass
class CropPredictionResult:
    prediction: str = ''
    class_probabilities: Dict[str, float] = field(default_factory=dict)
    ready: bool = False


class CropPredictionService:
    feature_order = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']

    def model_path(self) -> str:
        return os.path.join(settings.MEDIA_ROOT, 'crop_model.pkl')

    def is_ready(self) -> bool:
        return os.path.exists(self.model_path())

    def predict(self, parameters: Dict[str, float]) -> CropPredictionResult:
        if not self.is_ready():
            return CropPredictionResult(ready=False)

        with open(self.model_path(), 'rb') as file_obj:
            model = pickle.load(file_obj)

        input_data = pd.DataFrame([[parameters[key] for key in self.feature_order]], columns=self.feature_order)
        prediction = str(model.predict(input_data)[0])
        probabilities: Dict[str, float] = {}
        if hasattr(model, 'predict_proba'):
            raw_probabilities = model.predict_proba(input_data)[0]
            probabilities = {
                str(label): round(float(prob) * 100, 2)
                for label, prob in zip(model.classes_, raw_probabilities)
            }

        return CropPredictionResult(
            prediction=prediction,
            class_probabilities=probabilities,
            ready=True,
        )

