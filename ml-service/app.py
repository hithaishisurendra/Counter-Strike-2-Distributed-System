from flask import Flask, jsonify, request
from flask_cors import CORS
import pickle
import os
import pandas as pd
from psycopg2 import connect
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)

# Config
DB_HOST = os.getenv("CRDB_HOST", "crdb1")
DB_PORT = os.getenv("CRDB_PORT", "26257")
DB_DATABASE = os.getenv("CRDB_DATABASE", "cs2analytics")
DB_USER = os.getenv("CRDB_USER", "root")
MODEL_PATH = "trained_models/model.pkl"
FEATURES_PATH = "trained_models/features.pkl"

# Load model at startup
model = None
feature_names = None

def load_model():
    global model, feature_names
    try:
        if os.path.exists(MODEL_PATH):
            with open(MODEL_PATH, 'rb') as f:
                model = pickle.load(f)
            with open(FEATURES_PATH, 'rb') as f:
                feature_names = pickle.load(f)
            print(f"Model loaded from {MODEL_PATH}")
            return True
        else:
            print(f"Model not found at {MODEL_PATH}. Train first!")
            return False
    except Exception as e:
        print(f"Error loading model: {e}")
        return False

def get_db_connection():
    return connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_DATABASE,
        user=DB_USER,
        sslmode="disable"
    )

@app.route('/', methods=['GET'])
def home():
    status = "Model loaded" if model else "Model not trained yet"
    return jsonify({
        'service': 'ML Prediction Service',
        'status': status,
        'model_path': MODEL_PATH
    }), 200

@app.route('/train', methods=['POST'])
def train():
    """Trigger model training"""
    try:
        import train_model
        conn = get_db_connection()
        X, y = train_model.fetch_data_and_engineer_features(conn)
        
        if X is not None and len(X) > 1:
            train_model.train_and_save_model(X, y)
            load_model()
            conn.close()
            return jsonify({
                'success': True,
                'message': 'Model trained successfully',
                'samples': len(X)
            }), 200
        else:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Not enough data (need at least 2 matches)'
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/predict/<match_id>', methods=['GET'])
def predict(match_id):
    """Predict winner for a specific match"""
    if not model:
        return jsonify({
            'success': False,
            'error': 'Model not trained yet. POST to /train first'
        }), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT team, AVG(kd_ratio) as avg_kd, AVG(adr) as avg_adr
            FROM player_stats
            WHERE match_id = %s
            GROUP BY team
        """, (match_id,))
        
        team_stats = cur.fetchall()
        cur.close()
        conn.close()
        
        if len(team_stats) < 2:
            return jsonify({
                'success': False,
                'error': 'Match needs both teams to have player stats'
            }), 400
        
        # Map teams to Team1 and Team2 (alphabetically)
        teams = sorted([t['team'] for t in team_stats])
        team1_name = teams[0]
        team2_name = teams[1]
        
        team1_stats = next((t for t in team_stats if t['team'] == team1_name), None)
        team2_stats = next((t for t in team_stats if t['team'] == team2_name), None)
        
        if not team1_stats or not team2_stats:
            return jsonify({
                'success': False,
                'error': 'Missing team statistics'
            }), 400
        
        features = pd.DataFrame([{
            'avg_kd_Team1': float(team1_stats['avg_kd']),
            'avg_adr_Team1': float(team1_stats['avg_adr']),
            'avg_kd_Team2': float(team2_stats['avg_kd']),
            'avg_adr_Team2': float(team2_stats['avg_adr'])
        }])
        
        prediction = model.predict(features)[0]
        probabilities = model.predict_proba(features)[0]
        
        predicted_winner_mapped = 'Team1' if prediction == 1 else 'Team2'
        predicted_winner_actual = team1_name if prediction == 1 else team2_name
        confidence = float(max(probabilities))
        
        # Handle edge case where model only learned one class
        if len(probabilities) == 1:
            team1_prob = probabilities[0] * 100 if prediction == 1 else 0
            team2_prob = probabilities[0] * 100 if prediction == 0 else 0
        else:
            team1_prob = probabilities[1] * 100
            team2_prob = probabilities[0] * 100
        
        # Save prediction to database
        conn_save = get_db_connection()
        cur_save = conn_save.cursor()
        
        cur_save.execute("""
            INSERT INTO ml_predictions (match_id, predicted_winner, confidence)
            VALUES (%s, %s, %s)
        """, (match_id, predicted_winner_actual, confidence))
        
        conn_save.commit()
        cur_save.close()
        conn_save.close()
        
        return jsonify({
            'success': True,
            'match_id': match_id,
            'team1': team1_name,
            'team2': team2_name,
            'predicted_winner': predicted_winner_actual,
            'confidence': round(confidence * 100, 2),
            'team1_win_probability': round(team1_prob, 2),
            'team2_win_probability': round(team2_prob, 2),
            'saved_to_database': True
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/stats', methods=['GET'])
def stats():
    """Get model statistics"""
    if not model:
        return jsonify({
            'success': False,
            'error': 'Model not trained yet'
        }), 400
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("SELECT COUNT(*) as total FROM ml_predictions")
        total_predictions = cur.fetchone()['total']
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_evaluated,
                SUM(CASE WHEN prediction_correct THEN 1 ELSE 0 END) as correct_predictions
            FROM ml_predictions
            WHERE actual_winner IS NOT NULL
        """)
        accuracy_data = cur.fetchone()
        
        cur.close()
        conn.close()
        
        accuracy = 0
        if accuracy_data['total_evaluated'] and accuracy_data['total_evaluated'] > 0:
            accuracy = (accuracy_data['correct_predictions'] / accuracy_data['total_evaluated']) * 100
        
        return jsonify({
            'success': True,
            'total_predictions': total_predictions,
            'evaluated_predictions': accuracy_data['total_evaluated'] or 0,
            'correct_predictions': accuracy_data['correct_predictions'] or 0,
            'accuracy_percentage': round(accuracy, 2),
            'model_path': MODEL_PATH
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/feedback/<player_id>', methods=['GET'])
def feedback(player_id):
    """Get personalized feedback for a player"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                player_name,
                AVG(kd_ratio) as avg_kd,
                AVG(adr) as avg_adr,
                AVG(headshot_percentage) as avg_hs_pct,
                COUNT(*) as matches_played
            FROM player_stats
            WHERE player_id = %s
            GROUP BY player_name
        """, (player_id,))
        
        player_data = cur.fetchone()
        
        if not player_data:
            cur.close()
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Player not found'
            }), 404
        
        cur.execute("""
            SELECT 
                AVG(kd_ratio) as avg_kd,
                AVG(adr) as avg_adr,
                AVG(headshot_percentage) as avg_hs_pct
            FROM player_stats
        """)
        
        overall_avg = cur.fetchone()
        cur.close()
        conn.close()
        
        feedback_items = []
        
        if player_data['avg_kd'] < overall_avg['avg_kd']:
            feedback_items.append({
                'metric': 'K/D Ratio',
                'your_value': round(float(player_data['avg_kd']), 2),
                'average_value': round(float(overall_avg['avg_kd']), 2),
                'status': 'below_average',
                'advice': 'Focus on positioning and crosshair placement to improve kill/death ratio'
            })
        else:
            feedback_items.append({
                'metric': 'K/D Ratio',
                'your_value': round(float(player_data['avg_kd']), 2),
                'average_value': round(float(overall_avg['avg_kd']), 2),
                'status': 'above_average',
                'advice': 'Great work! Maintain your aggressive playstyle'
            })
        
        if player_data['avg_adr'] < overall_avg['avg_adr']:
            feedback_items.append({
                'metric': 'ADR',
                'your_value': round(float(player_data['avg_adr']), 2),
                'average_value': round(float(overall_avg['avg_adr']), 2),
                'status': 'below_average',
                'advice': 'Work on spray control and weapon accuracy'
            })
        else:
            feedback_items.append({
                'metric': 'ADR',
                'your_value': round(float(player_data['avg_adr']), 2),
                'average_value': round(float(overall_avg['avg_adr']), 2),
                'status': 'above_average',
                'advice': 'Excellent damage output!'
            })
        
        if player_data['avg_hs_pct'] and player_data['avg_hs_pct'] < overall_avg['avg_hs_pct']:
            feedback_items.append({
                'metric': 'Headshot %',
                'your_value': round(float(player_data['avg_hs_pct']), 2),
                'average_value': round(float(overall_avg['avg_hs_pct']), 2),
                'status': 'below_average',
                'advice': 'Practice headshot aim'
            })
        elif player_data['avg_hs_pct']:
            feedback_items.append({
                'metric': 'Headshot %',
                'your_value': round(float(player_data['avg_hs_pct']), 2),
                'average_value': round(float(overall_avg['avg_hs_pct']), 2),
                'status': 'above_average',
                'advice': 'Sharp aim!'
            })
        
        return jsonify({
            'success': True,
            'player_id': player_id,
            'player_name': player_data['player_name'],
            'matches_played': player_data['matches_played'],
            'feedback': feedback_items
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    load_model()
    app.run(host='0.0.0.0', port=5002, debug=True)