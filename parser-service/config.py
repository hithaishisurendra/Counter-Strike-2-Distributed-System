import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
    KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'match_queue')
    KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'parser-group')
    
    # CockroachDB
    CRDB_HOST = os.getenv('CRDB_HOST', 'crdb1')
    CRDB_PORT = int(os.getenv('CRDB_PORT', '26257'))
    CRDB_DATABASE = os.getenv('CRDB_DATABASE', 'cs2analytics')
    CRDB_USER = os.getenv('CRDB_USER', 'root')
    
    # Shared Volume
    SHARED_VOLUME_PATH = os.getenv('SHARED_VOLUME_PATH', '/shared/uploads')
    
    @staticmethod
    def get_db_connection_string():
        return (
            f"postgresql://{Config.CRDB_USER}@{Config.CRDB_HOST}:{Config.CRDB_PORT}/"
            f"{Config.CRDB_DATABASE}?sslmode=disable"
        )