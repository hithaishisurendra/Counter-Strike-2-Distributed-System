import os
import pandas as pd
import numpy as np
import pickle
from psycopg2 import connect
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# --- Configuration ---
DB_HOST = os.getenv("CRDB_HOST", "crdb1")
DB_PORT = os.getenv("CRDB_PORT", "26257")
DB_DATABASE = os.getenv("CRDB_DATABASE", "cs2analytics")
DB_USER = os.getenv("CRDB_USER", "root")
MODEL_PATH = "trained_models/model.pkl"
FEATURES_PATH = "trained_models/features.pkl"

def get_db_connection():
    """Establishes a connection to CockroachDB."""
    try:
        conn = connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_DATABASE,
            user=DB_USER,
            sslmode="disable"
        )
        return conn
    except Exception as e:
        print(f"Error connecting to CockroachDB: {e}")
        return None

def fetch_data_and_engineer_features(conn):
    """
    Fetches match and player data and calculates team-level features.
    Uses Team1 vs Team2 instead of CT vs T for flexibility.
    """
    print("Fetching data from the database...")
    
    # SQL to join matches and player_stats
    QUERY = """
    SELECT 
        m.match_id, 
        m.map_name,
        m.winner_team, 
        ps.player_id, 
        ps.team, 
        ps.kd_ratio, 
        ps.adr
    FROM matches m
    JOIN player_stats ps ON m.match_id = ps.match_id;
    """
    
    df = pd.read_sql(QUERY, conn)
    
    if df.empty:
        print("No data found in database. Cannot train model.")
        return None, None
    
    print(f"Fetched {len(df['match_id'].unique())} matches and {len(df)} player records.")
    
    # Map teams to Team1 and Team2 for each match
    # Team1 = first team alphabetically, Team2 = second team
    team_mapping = {}
    for match_id in df['match_id'].unique():
        teams = sorted(df[df['match_id'] == match_id]['team'].unique())
        if len(teams) < 2:
            print(f" Warning: Match {match_id} only has {len(teams)} team(s)")
            continue
        team_mapping[match_id] = {teams[0]: 'Team1', teams[1]: 'Team2'}
    
    # Apply mapping
    df['team_mapped'] = df.apply(
        lambda row: team_mapping.get(row['match_id'], {}).get(row['team'], None), 
        axis=1
    )
    
    # Filter out matches without proper team mapping
    df = df[df['team_mapped'].notna()]
    valid_matches = df['match_id'].unique()
    
    if len(valid_matches) == 0:
        print(" Error: No matches have both teams!")
        return None, None
    
    print(f"Using {len(valid_matches)} matches with both teams")
    
    # Calculate team-level averages
    team_features = df.groupby(['match_id', 'team_mapped']).agg(
        avg_kd=('kd_ratio', 'mean'),
        avg_adr=('adr', 'mean'),
        player_count=('player_id', 'count')
    ).reset_index()
    
    # Pivot the data to get Team1 and Team2 features side-by-side
    pivot_features = team_features.pivot(
        index='match_id', 
        columns='team_mapped', 
        values=['avg_kd', 'avg_adr']
    )
    
    # Flatten column names
    pivot_features.columns = ['_'.join(col).strip() for col in pivot_features.columns.values]
    pivot_features = pivot_features.reset_index()
    
    print(f"Feature columns created: {pivot_features.columns.tolist()}")
    
    # Merge with match winner info and map winner to Team1/Team2
    match_winners = df[['match_id', 'winner_team', 'team', 'team_mapped']].drop_duplicates()
    
    # Create winner_mapped column
    winner_map = {}
    for _, row in match_winners.iterrows():
        if row['winner_team'] == row['team']:
            winner_map[row['match_id']] = row['team_mapped']
    
    final_df = pivot_features.copy()
    final_df['winner_team_mapped'] = final_df['match_id'].map(winner_map)
    
    # Filter out matches without clear winner mapping
    final_df = final_df[final_df['winner_team_mapped'].notna()]
    
    # Target Variable Encoding (1=Team1 Wins, 0=Team2 Wins)
    final_df['target'] = np.where(final_df['winner_team_mapped'] == 'Team1', 1, 0)
    
    # Select final features (X) and target (y)
    X = final_df[[
        'avg_kd_Team1', 'avg_adr_Team1', 
        'avg_kd_Team2', 'avg_adr_Team2'
    ]].fillna(0)
    
    y = final_df['target']
    
    print(f"\n Training Data Summary:")
    print(f"   Total samples: {len(X)}")
    print(f"   Team1 wins: {sum(y == 1)}")
    print(f"   Team2 wins: {sum(y == 0)}")
    print(f"   Features: {X.columns.tolist()}")
    
    return X, y

def train_and_save_model(X, y):
    """
    Trains a Random Forest Classifier and saves the model.
    """
    print("\n Starting model training...")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"   Training samples: {len(X_train)}")
    print(f"   Test samples: {len(X_test)}")
    
    # Train model
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n Model Training Complete. Test Accuracy: {accuracy:.4f}")
    
    # Save the model
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, 'wb') as file:
        pickle.dump(model, file)
    print(f" Model successfully saved to {MODEL_PATH}")
    
    # Save feature names
    with open(FEATURES_PATH, 'wb') as file:
        pickle.dump(X.columns.tolist(), file)
    print(f" Feature names saved to {FEATURES_PATH}")
    
    return model

if __name__ == "__main__":
    conn = get_db_connection()
    if conn:
        X, y = fetch_data_and_engineer_features(conn)
        if X is not None and not X.empty:
            if len(X) > 1:
                train_and_save_model(X, y)
            else:
                print(" Need at least 2 matches in the database to train the model.")
        conn.close()