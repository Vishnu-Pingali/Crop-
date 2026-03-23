import re
from dataclasses import dataclass, field
from typing import Dict, Optional


TELUGU_NUMBER_WORDS = {
    'సున్నా': 0,
    'ఒకటి': 1,
    'రెండు': 2,
    'మూడు': 3,
    'నాలుగు': 4,
    'ఐదు': 5,
    'ఆరు': 6,
    'ఏడు': 7,
    'ఎనిమిది': 8,
    'తొమ్మిది': 9,
    'పది': 10,
}

PARAMETER_PATTERNS = {
    'N': [r'(?:nitrogen|నైట్రోజన్|n)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)'],
    'P': [r'(?:phosphorus|ఫాస్ఫరస్|p)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)'],
    'K': [r'(?:potassium|పొటాషియం|k)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)'],
    'temperature': [r'(?:temperature|ఉష్ణోగ్రత|temp)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)'],
    'humidity': [r'(?:humidity|ఆర్ద్రత)\s*(?:is|=|:|value|విలువ|ఉంది|శాతం)?\s*(-?\d+(?:\.\d+)?)'],
    'ph': [
        r'(?:soil\s*)?ph\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)',
        r'(?:పీహెచ్)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)',
    ],
    'rainfall': [r'(?:rainfall|వర్షపాతం)\s*(?:is|=|:|value|విలువ|ఉంది)?\s*(-?\d+(?:\.\d+)?)'],
}

FIELD_LABELS = {
    'N': 'నైట్రోజన్',
    'P': 'ఫాస్ఫరస్',
    'K': 'పొటాషియం',
    'temperature': 'ఉష్ణోగ్రత',
    'humidity': 'ఆర్ద్రత',
    'ph': 'మట్టి pH',
    'rainfall': 'వర్షపాతం',
}


@dataclass
class LanguageAnalysis:
    raw_text: str
    normalized_text: str
    intent: str
    parameters: Dict[str, float] = field(default_factory=dict)
    asks_prediction: bool = False
    language: str = 'te-IN'


class LanguageProcessingService:
    prediction_keywords = (
        'crop', 'recommend', 'prediction', 'suggest', 'పంట', 'సిఫారసు', 'ఏ పంట', 'సూచన'
    )
    guidance_keywords = (
        'soil', 'fertilizer', 'weather', 'disease', 'market', 'ఎరువు', 'మట్టి', 'పంట సంరక్షణ'
    )

    def normalize_text(self, text: str) -> str:
        cleaned = text.strip()
        for telugu_word, number in TELUGU_NUMBER_WORDS.items():
            cleaned = re.sub(telugu_word, str(number), cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned

    def extract_parameters(self, text: str) -> Dict[str, float]:
        parameters: Dict[str, float] = {}
        for key, patterns in PARAMETER_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    try:
                        parameters[key] = float(match.group(1))
                        break
                    except (TypeError, ValueError):
                        continue

        # Fallback: if the sentence contains exactly seven numeric values, map them in model order.
        if len(parameters) < 7:
            numbers = [float(value) for value in re.findall(r'-?\d+(?:\.\d+)?', text)]
            if len(numbers) == 7:
                ordered_keys = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
                parameters = dict(zip(ordered_keys, numbers))
        return parameters

    def infer_intent(self, text: str, parameters: Dict[str, float]) -> str:
        lowered = text.lower()
        if parameters:
            return 'crop_prediction'
        if any(keyword in lowered for keyword in self.prediction_keywords):
            return 'crop_prediction'
        if any(keyword in lowered for keyword in self.guidance_keywords):
            return 'farming_guidance'
        return 'general_conversation'

    def analyze(self, text: str, language: str = 'te-IN') -> LanguageAnalysis:
        normalized = self.normalize_text(text)
        parameters = self.extract_parameters(normalized)
        intent = self.infer_intent(normalized, parameters)
        return LanguageAnalysis(
            raw_text=text,
            normalized_text=normalized,
            intent=intent,
            parameters=parameters,
            asks_prediction=intent == 'crop_prediction',
            language=language,
        )

    def missing_parameter_labels(self, parameters: Dict[str, float]) -> list[str]:
        ordered_keys = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
        return [FIELD_LABELS[key] for key in ordered_keys if key not in parameters]

    def is_complete_parameter_set(self, parameters: Dict[str, float]) -> bool:
        return len(self.missing_parameter_labels(parameters)) == 0
