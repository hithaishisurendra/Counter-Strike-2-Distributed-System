from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = Flask(__name__)
CORS(app)

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('CRDB_HOST', 'crdb1'),
        port=os.getenv('CRDB_PORT', '26257'),
        database=os.getenv('CRDB_DATABASE', 'cs2analytics'),
        user=os.getenv('CRDB_USER', 'root'),
        options='-c sslmode=disable'
    )

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': 'read-api'}), 200

@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Get all matches"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        limit = request.args.get('limit', 50, type=int)
        
        cur.execute("""
            SELECT 
                match_id, 
                file_name, 
                map_name, 
                game_mode,
                ct_score, 
                t_score, 
                winner_team,
                processed_at
            FROM matches
            ORDER BY processed_at DESC
            LIMIT %s
        """, (limit,))
        
        matches = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(matches),
            'matches': matches
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/match/<match_id>', methods=['GET'])
def get_match_details(match_id):
    """Get detailed match information"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get match info
        cur.execute("""
            SELECT * FROM matches WHERE match_id = %s
        """, (match_id,))
        match = cur.fetchone()
        
        if not match:
            return jsonify({'success': False, 'error': 'Match not found'}), 404
        
        # Get player stats
        cur.execute("""
            SELECT * FROM player_stats 
            WHERE match_id = %s
            ORDER BY kills DESC
        """, (match_id,))
        players = cur.fetchall()
        
        # Get rounds
        cur.execute("""
            SELECT * FROM rounds 
            WHERE match_id = %s
            ORDER BY round_number
        """, (match_id,))
        rounds = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'match': match,
            'players': players,
            'rounds': rounds
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/players', methods=['GET'])
def get_players():
    """Get all players with aggregated stats"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            SELECT 
                player_id,
                player_name,
                COUNT(DISTINCT match_id) as matches_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                ROUND(AVG(kd_ratio), 2) as avg_kd_ratio,
                ROUND(AVG(headshot_percentage), 2) as avg_hs_pct
            FROM player_stats
            GROUP BY player_id, player_name
            ORDER BY total_kills DESC
        """)
        
        players = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(players),
            'players': players
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/player/<player_id>/stats', methods=['GET'])
def get_player_stats(player_id):
    """Get detailed stats for a specific player"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Overall stats
        cur.execute("""
            SELECT 
                player_id,
                player_name,
                COUNT(DISTINCT match_id) as matches_played,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths,
                SUM(assists) as total_assists,
                SUM(headshot_kills) as total_headshots,
                ROUND(AVG(kd_ratio), 2) as avg_kd_ratio,
                ROUND(AVG(headshot_percentage), 2) as avg_hs_pct
            FROM player_stats
            WHERE player_id = %s
            GROUP BY player_id, player_name
        """, (player_id,))
        
        stats = cur.fetchone()
        
        if not stats:
            return jsonify({'success': False, 'error': 'Player not found'}), 404
        
        # Match history
        cur.execute("""
            SELECT 
                ps.*,
                m.map_name,
                m.ct_score,
                m.t_score,
                m.winner_team,
                m.processed_at
            FROM player_stats ps
            JOIN matches m ON ps.match_id = m.match_id
            WHERE ps.player_id = %s
            ORDER BY m.processed_at DESC
        """, (player_id,))
        
        match_history = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'match_history': match_history
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats/summary', methods=['GET'])
def get_stats_summary():
    """Get overall platform statistics"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Total matches
        cur.execute("SELECT COUNT(*) as total FROM matches")
        total_matches = cur.fetchone()['total']
        
        # Total players
        cur.execute("SELECT COUNT(DISTINCT player_id) as total FROM player_stats")
        total_players = cur.fetchone()['total']
        
        # Total kills
        cur.execute("SELECT COUNT(*) as total FROM kills")
        total_kills = cur.fetchone()['total']
        
        # Total rounds
        cur.execute("SELECT COUNT(*) as total FROM rounds")
        total_rounds = cur.fetchone()['total']
        
        # Top player
        cur.execute("""
            SELECT player_name, SUM(kills) as total_kills
            FROM player_stats
            GROUP BY player_name
            ORDER BY total_kills DESC
            LIMIT 1
        """)
        top_player = cur.fetchone()
        
        # Map distribution
        cur.execute("""
            SELECT map_name, COUNT(*) as count
            FROM matches
            GROUP BY map_name
            ORDER BY count DESC
        """)
        maps = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_matches': total_matches,
                'total_players': total_players,
                'total_kills': total_kills,
                'total_rounds': total_rounds,
                'top_player': top_player,
                'map_distribution': maps
            }
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)