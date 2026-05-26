from pathlib import Path

YARA_DEFAULT_CONFIDENCE: float = 0.8
YARA_CONFIDENCE_BOOST: float = 0.1
SPACY_DEFAULT_CONFIDENCE: float = 0.85
DEFAULT_LOCALE: str = "nl_NL"
SPACY_MODEL: str = "en_core_web_lg"
FAKE_EMAIL_DOMAIN: str = "example.com"
LEGEND_MODEL_DIR_ENV: str = "LEGEND_MODEL_PATH"
DEFAULT_MODEL_DIR: Path = Path.home() / ".legend" / "models"
