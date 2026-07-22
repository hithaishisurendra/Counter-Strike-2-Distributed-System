from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename
from kafka import KafkaProducer
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import json
import os
import time
import uuid
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
CORS(app)

# Prometheus metrics
REQUEST_COUNT = Counter('flask_http_request_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('flask_http_request_duration_seconds', 'HTTP request duration in seconds', ['method', 'endpoint'])
UPLOAD_COUNTER = Counter('demo_uploads_total', 'Total demo file uploads')
UPLOAD_SIZE = Histogram('demo_upload_size_bytes', 'Size of uploaded demo files')
PROCESSING_ERRORS = Counter('demo_processing_errors_total', 'Total processing errors')
KAFKA_CONNECTED = Gauge('kafka_connection_status', 'Kafka connection status (1=connected, 0=disconnected)')

# Before request handler to track timing
@app.before_request
def before_request():
    request._start_time = time.time()

# After request handler to record metrics
@app.after_request
def after_request(response):
    if hasattr(request, '_start_time'):
        request_duration = time.time() - request._start_time
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown'
        ).observe(request_duration)
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.endpoint or 'unknown',
        status=response.status_code
    ).inc()
    
    return response

# Initialize Kafka Producer (with retry logic)
def get_kafka_producer():
    max_retries = 10
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            producer = KafkaProducer(
                bootstrap_servers=app.config['KAFKA_BOOTSTRAP_SERVERS'],
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',  # Wait for all replicas
                retries=3
            )
            print(f"Connected to Kafka at {app.config['KAFKA_BOOTSTRAP_SERVERS']}")
            KAFKA_CONNECTED.set(1)
            return producer
        except Exception as e:
            print(f"Kafka connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                raise Exception("Failed to connect to Kafka after multiple attempts")

try:
    kafka_producer = get_kafka_producer()
except Exception as e:
    print(f"Failed to initialize Kafka producer: {e}")
    kafka_producer = None
    KAFKA_CONNECTED.set(0)

def allowed_file(filename):
    """Check if file has allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'upload-api',
        'kafka_connected': kafka_producer is not None
    }), 200

@app.route('/upload', methods=['POST'])
def upload_demo():
    """
    Upload a CS2 demo file
    Expects: multipart/form-data with 'file' field
    Returns: Job ID and status
    """
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file extension
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only .dem files allowed'}), 400
        
        # Generate unique filename to prevent collisions
        original_filename = secure_filename(file.filename)
        job_id = str(uuid.uuid4())
        timestamp = int(time.time())
        unique_filename = f"{timestamp}_{job_id}_{original_filename}"
        
        # Save file to shared volume
        file_path = os.path.join(app.config['SHARED_VOLUME_PATH'], unique_filename)
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        print(f"📁 File saved: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
        
        # Prepare Kafka message
        message = {
            'job_id': job_id,
            'file_name': unique_filename,
            'original_filename': original_filename,
            'file_path': file_path,
            'file_size': file_size,
            'uploaded_at': timestamp,
            'status': 'pending'
        }
        
        # Send message to Kafka
        future = kafka_producer.send(app.config['KAFKA_TOPIC'], value=message)
        
        # Wait for confirmation (with timeout)
        record_metadata = future.get(timeout=10)
        
        print(f"Message sent to Kafka topic '{app.config['KAFKA_TOPIC']}' "
              f"(partition: {record_metadata.partition}, offset: {record_metadata.offset})")
        
        # Track metrics
        UPLOAD_COUNTER.inc()
        UPLOAD_SIZE.observe(file_size)
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'file_name': original_filename,
            'file_size': file_size,
            'message': 'File uploaded successfully and queued for processing',
            'kafka_topic': app.config['KAFKA_TOPIC'],
            'kafka_partition': record_metadata.partition,
            'kafka_offset': record_metadata.offset
        }), 200
        
    except Exception as e:
        print(f"Upload failed: {str(e)}")
        
        # Track error
        PROCESSING_ERRORS.inc()
        
        # Clean up file if it was saved
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Get API status and configuration"""
    return jsonify({
        'status': 'running',
        'kafka_bootstrap_servers': app.config['KAFKA_BOOTSTRAP_SERVERS'],
        'kafka_topic': app.config['KAFKA_TOPIC'],
        'upload_path': app.config['SHARED_VOLUME_PATH'],
        'max_file_size_mb': app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024,
        'allowed_extensions': list(app.config['ALLOWED_EXTENSIONS'])
    }), 200

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=app.config['DEBUG'])