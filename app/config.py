import os

class Settings:
    PROJECT_NAME: str = "おバカ人狼 (Obaka Jinro)"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

settings = Settings()
