import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
    KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'match_queue')
    
    # File Upload
    SHARED_VOLUME_PATH = os.getenv('SHARED_VOLUME_PATH', '/shared/uploads')
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'dem'}
    
    # Create upload directory if it doesn't exist
    os.makedirs(SHARED_VOLUME_PATH, exist_ok=True)