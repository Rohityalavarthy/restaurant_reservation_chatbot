"""Application settings and configuration"""
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Application configuration"""
    
    # API Configuration
    TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "together")
    MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct-Turbo")
    
    # Application Configuration
    APP_TITLE = "GoodFoods AI Reservation Assistant"
    APP_ICON = "🍝"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    
    # Database Paths
    RESTAURANTS_DB = "data/restaurants.json"
    RESERVATIONS_DB = "data/reservations.json"
    CONSTRAINTS_DB = "data/booking_constraints.json"
    
    # Conversation Settings
    MAX_CONTEXT_TURNS = 10
    RESPONSE_TIMEOUT = 30
    
    # Business Rules
    MAX_PARTY_SIZE = 20
    ADVANCE_BOOKING_DAYS = 30
    SAME_DAY_CUTOFF_HOURS = 2
    
    @classmethod
    def validate(cls):
        """Validate required settings"""
        if not cls.TOGETHER_API_KEY:
            raise ValueError("TOGETHER_API_KEY not set in environment")
        return True

settings = Settings()
