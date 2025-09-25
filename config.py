import os

class Config:
    PORT = 8014
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"
    SECRET_KEY = os.environ.get("SECRET_KEY", "super-secret-theme-key")

    # Redis Configuration for theme settings
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/2") # Using DB 2 for theme settings

    # Default theme settings (can be overridden by user choices)
    DEFAULT_THEME = os.environ.get("DEFAULT_THEME", "light")
    AVAILABLE_THEMES = ["light", "dark", "blue", "green"]

    # CORS settings
    CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*").split(",")

class DevelopmentConfig(Config):
    DEBUG = True
    FLASK_ENV = "development"

class ProductionConfig(Config):
    DEBUG = False
    FLASK_ENV = "production"

def get_config():
    if os.environ.get("FLASK_ENV") == "production":
        return ProductionConfig
    return DevelopmentConfig

