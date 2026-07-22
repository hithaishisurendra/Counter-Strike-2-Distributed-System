from kafka import KafkaConsumer
import json
import os
import time
from config import Config
from parser import CS2DemoParser
from db_writer import DatabaseWriter

class DemoConsumer:
    def __init__(self):
        self.consumer = self._create_consumer()
        self.db_writer = DatabaseWriter()
    
    def _create_consumer(self):
        """Create Kafka consumer with retry logic"""
        max_retries = 10
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                consumer = KafkaConsumer(
                    Config.KAFKA_TOPIC,
                    bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                    group_id=Config.KAFKA_GROUP_ID,
                    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                    auto_offset_reset='earliest',
                    enable_auto_commit=False,
                    max_poll_records=1,
                    max_poll_interval_ms=1200000,
                    session_timeout_ms=120000
                )
                print(f"Connected to Kafka topic '{Config.KAFKA_TOPIC}'")
                return consumer
            except Exception as e:
                print(f"Kafka consumer connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise Exception("Failed to connect to Kafka after multiple attempts")
    
    def process_message(self, message):
        """Process a single demo file"""
        try:
            data = message.value
            job_id = data['job_id']
            file_path = data['file_path']
            file_name = data['file_name']
            
            print(f"\n{'='*60}")
            print(f"Processing Job: {job_id}")
            print(f"File: {file_name}")
            print(f"{'='*60}")
            
            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Demo file not found: {file_path}")
            
            # Parse demo
            parser = CS2DemoParser(file_path)
            parsed_data = parser.parse()
            
            # Add file name to match data
            parsed_data['match']['file_name'] = file_name
            
            # Write to database
            print(f"\nWriting to database...")
            match_id = self.db_writer.insert_match(parsed_data['match'])
            
            # Insert stats
            if parsed_data['players']:
                self.db_writer.insert_player_stats(match_id, parsed_data['players'])
            
            if parsed_data['rounds']:
                self.db_writer.insert_rounds(match_id, parsed_data['rounds'])
            
            if parsed_data['kills']:
                self.db_writer.insert_kills(match_id, parsed_data['kills'])

            if parsed_data.get('movement'):
                self.db_writer.insert_movement_stats(match_id, parsed_data['movement'])
            
            if parsed_data.get('aim'):
                self.db_writer.insert_aim_stats(match_id, parsed_data['aim'])
            
            if parsed_data.get('positioning'):
                self.db_writer.insert_positioning_stats(match_id, parsed_data['positioning'])
            
            if parsed_data.get('death_locations'):
                self.db_writer.insert_death_locations(match_id, parsed_data['death_locations'])
            
            if parsed_data.get('utility'):
                self.db_writer.insert_utility_stats(match_id, parsed_data['utility'])
            
            if parsed_data.get('economy'):
                self.db_writer.insert_economy_stats(match_id, parsed_data['economy'])
            
            if parsed_data.get('combat'):
                self.db_writer.insert_combat_stats(match_id, parsed_data['combat'])
            
            # Commit transaction
            self.db_writer.commit()
     
            # Commit Kafka offset
            self.consumer.commit()
            
            print(f"\nSUCCESS! Match {match_id} processed and saved")
            print(f"{'='*60}\n")
            
            # Delete demo file
            print(f"\nDeleting demo file: {file_path}")
            if os.path.exists(file_path):
                os.remove(file_path)
            
        except Exception as e:
            print(f"\nERROR processing message: {e}")
            print(f"{'='*60}\n")
            
            # Rollback database transaction
            self.db_writer.rollback()
            
            # Don't commit Kafka offset - message will be redelivered
            raise
    
    def start(self):
        """Start consuming messages"""
        print(f"Parser service started")
        print(f"Waiting for demo files to process...")
        print(f"{'='*60}\n")
        
        try:
            for message in self.consumer:
                try:
                    self.process_message(message)
                except Exception as e:
                    print(f"Failed to process message, will retry: {e}")
                    # Message will be redelivered by Kafka
                    time.sleep(5)
        except KeyboardInterrupt:
            print("\nShutting down parser service...")
        finally:
            self.consumer.close()
            self.db_writer.close()
            print("Parser service stopped")

if __name__ == '__main__':
    consumer = DemoConsumer()
    consumer.start()