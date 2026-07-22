import psycopg2
from psycopg2.extras import execute_values
import uuid
from datetime import datetime
from config import Config

class DatabaseWriter:
    def __init__(self):
        self.connection_string = Config.get_db_connection_string()
        self.conn = None
        self.connect()
    
    def connect(self):
        """Connect to CockroachDB with retry logic"""
        max_retries = 10
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(self.connection_string)
                self.conn.autocommit = False
                print(f"Connected to CockroachDB at {Config.CRDB_HOST}:{Config.CRDB_PORT}")
                return
            except Exception as e:
                print(f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                else:
                    raise Exception("Failed to connect to database after multiple attempts")
    
    def insert_match(self, match_data):
        """Insert match metadata"""
        try:
            cursor = self.conn.cursor()
            
            match_id = str(uuid.uuid4())
            
            query = """
                INSERT INTO matches (
                    match_id, file_name, map_name, game_mode, 
                    duration_seconds, winner_team, ct_score, t_score
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING match_id
            """
            
            cursor.execute(query, (
                match_id,
                match_data.get('file_name'),
                match_data.get('map_name'),
                match_data.get('game_mode'),
                match_data.get('duration_seconds'),
                match_data.get('winner_team'),
                match_data.get('ct_score', 0),
                match_data.get('t_score', 0)
            ))
            
            result = cursor.fetchone()
            cursor.close()
            
            print(f"Inserted match: {match_id}")
            return result[0] if result else match_id
            
        except Exception as e:
            print(f"Error inserting match: {e}")
            raise
    
    def insert_player_stats(self, match_id, player_stats_list):
        """Batch insert player statistics"""
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_stats (
                    match_id, player_id, player_name, team,
                    kills, deaths, assists, mvps, score,
                    headshot_kills, total_damage, kd_ratio, adr, headshot_percentage
                )
                VALUES %s
            """
            
            values = []
            for stats in player_stats_list:
                kd_ratio = stats['kills'] / stats['deaths'] if stats['deaths'] > 0 else stats['kills']
                hs_pct = (stats['headshot_kills'] / stats['kills'] * 100) if stats['kills'] > 0 else 0
                
                values.append((
                    match_id,
                    stats['player_id'],
                    stats['player_name'],
                    stats['team'],
                    stats['kills'],
                    stats['deaths'],
                    stats['assists'],
                    stats.get('mvps', 0),
                    stats.get('score', 0),
                    stats['headshot_kills'],
                    stats.get('total_damage', 0),
                    round(kd_ratio, 2),
                    stats.get('adr', 0),
                    round(hs_pct, 2)
                ))
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} player stats")
            
        except Exception as e:
            print(f"Error inserting player stats: {e}")
            raise
    
    def insert_rounds(self, match_id, rounds_list):
        """Batch insert round information"""
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO rounds (
                    match_id, round_number, winner_team, end_reason,
                    duration_seconds, ct_equipment_value, t_equipment_value
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    r['round_number'],
                    r.get('winner_team'),
                    r.get('end_reason'),
                    r.get('duration_seconds'),
                    r.get('ct_equipment_value', 0),
                    r.get('t_equipment_value', 0)
                )
                for r in rounds_list
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} rounds")
            
        except Exception as e:
            print(f"Error inserting rounds: {e}")
            raise
    
    def insert_kills(self, match_id, kills_list):
        """Batch insert kill events"""
        try:
            if not kills_list:
                return
            
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO kills (
                    match_id, round_number, tick,
                    attacker_id, attacker_name, victim_id, victim_name,
                    weapon, is_headshot, assister_id, assister_name
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    k['round_number'],
                    k['tick'],
                    k.get('attacker_id'),
                    k.get('attacker_name'),
                    k.get('victim_id'),
                    k.get('victim_name'),
                    k.get('weapon'),
                    k.get('is_headshot', False),
                    k.get('assister_id'),
                    k.get('assister_name')
                )
                for k in kills_list
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} kills")
            
        except Exception as e:
            print(f"Error inserting kills: {e}")
            raise
    
    def insert_movement_stats(self, match_id, movement_stats):
        """Insert COMPLETE movement statistics"""
        if not movement_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_movement_stats (
                    match_id, player_id, player_name,
                    total_distance_traveled, avg_velocity,
                    time_walking_pct, time_running_pct, time_crouched_pct,
                    jump_count, time_airborne_pct, bhop_attempts, successful_bhops,
                    time_strafing_pct, strafe_efficiency, movement_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['total_distance_traveled'],
                    stat['avg_velocity'],
                    stat['time_walking_pct'],
                    stat['time_running_pct'],
                    stat['time_crouched_pct'],
                    stat['jump_count'],
                    stat['time_airborne_pct'],
                    stat['bhop_attempts'],
                    stat['successful_bhops'],
                    stat['time_strafing_pct'],
                    stat['strafe_efficiency'],
                    stat['movement_score']
                )
                for stat in movement_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} movement stats")
            
        except Exception as e:
            print(f"Error inserting movement stats: {e}")
            raise
    
    def insert_aim_stats(self, match_id, aim_stats):
        """Insert COMPLETE aim statistics"""
        if not aim_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_aim_stats (
                    match_id, player_id, player_name,
                    avg_crosshair_height, crosshair_on_enemy_pct, pre_aim_accuracy,
                    first_bullet_accuracy, spray_control_accuracy, burst_fire_pct,
                    avg_reaction_time_ms, avg_flick_distance, flick_accuracy,
                    one_tap_kills, spray_kills, avg_bullets_to_kill,
                    aim_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['avg_crosshair_height'],
                    stat['crosshair_on_enemy_pct'],
                    stat['pre_aim_accuracy'],
                    stat['first_bullet_accuracy'],
                    stat['spray_control_accuracy'],
                    stat['burst_fire_pct'],
                    stat['avg_reaction_time_ms'],
                    stat['avg_flick_distance'],
                    stat['flick_accuracy'],
                    stat['one_tap_kills'],
                    stat['spray_kills'],
                    stat['avg_bullets_to_kill'],
                    stat['aim_score']
                )
                for stat in aim_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} aim stats")
            
        except Exception as e:
            print(f"Error inserting aim stats: {e}")
            raise
    
    def insert_positioning_stats(self, match_id, positioning_stats):
        """Insert COMPLETE positioning statistics"""
        if not positioning_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_positioning_stats (
                    match_id, player_id, player_name, team,
                    deaths_to_peekers, deaths_while_moving, deaths_from_behind, deaths_in_open,
                    avg_time_to_contact, early_deaths_pct, entry_frag_success_pct, hold_success_pct,
                    time_in_safe_zone_pct, time_pushed_up_pct, rotations_count, late_rotations,
                    positioning_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['team'],
                    stat['deaths_to_peekers'],
                    stat['deaths_while_moving'],
                    stat['deaths_from_behind'],
                    stat['deaths_in_open'],
                    stat['avg_time_to_contact'],
                    stat['early_deaths_pct'],
                    stat['entry_frag_success_pct'],
                    stat['hold_success_pct'],
                    stat['time_in_safe_zone_pct'],
                    stat['time_pushed_up_pct'],
                    stat['rotations_count'],
                    stat['late_rotations'],
                    stat['positioning_score']
                )
                for stat in positioning_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} positioning stats")
            
        except Exception as e:
            print(f"Error inserting positioning stats: {e}")
            raise
    
    def insert_death_locations(self, match_id, death_locations):
        """Insert death location data for heatmaps"""
        if not death_locations:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO death_locations (
                    match_id, player_id, player_name,
                    death_x, death_y, death_z,
                    killer_x, killer_y, killer_z,
                    round_number, tick, weapon,
                    was_holding_angle, was_moving
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    loc['player_id'],
                    loc['player_name'],
                    loc['death_x'],
                    loc['death_y'],
                    loc['death_z'],
                    loc['killer_x'],
                    loc['killer_y'],
                    loc['killer_z'],
                    loc['round_number'],
                    loc['tick'],
                    loc['weapon'],
                    loc['was_holding_angle'],
                    loc['was_moving']
                )
                for loc in death_locations
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} death locations")
            
        except Exception as e:
            print(f"Error inserting death locations: {e}")
            raise
    
    def insert_utility_stats(self, match_id, utility_stats):
        """Insert COMPLETE utility usage statistics"""
        if not utility_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_utility_stats (
                    match_id, player_id, player_name,
                    flashbangs_thrown, smokes_thrown, molotovs_thrown,
                    he_grenades_thrown, decoys_thrown,
                    enemies_flashed, avg_flash_duration, teammates_flashed,
                    utility_damage_dealt, smoke_effectiveness_score,
                    utility_wasted, utility_used_in_execute_pct,
                    utility_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['flashbangs_thrown'],
                    stat['smokes_thrown'],
                    stat['molotovs_thrown'],
                    stat['he_grenades_thrown'],
                    stat['decoys_thrown'],
                    stat['enemies_flashed'],
                    stat['avg_flash_duration'],
                    stat['teammates_flashed'],
                    stat['utility_damage_dealt'],
                    stat['smoke_effectiveness_score'],
                    stat['utility_wasted'],
                    stat['utility_used_in_execute_pct'],
                    stat['utility_score']
                )
                for stat in utility_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} utility stats")
            
        except Exception as e:
            print(f"Error inserting utility stats: {e}")
            raise
    
    def insert_economy_stats(self, match_id, economy_stats):
        """Insert COMPLETE economy management statistics"""
        if not economy_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_economy_stats (
                    match_id, player_id, player_name,
                    avg_money_saved_per_round, force_buy_rounds, eco_rounds_survived, full_buy_rounds,
                    avg_weapon_cost, armor_purchase_rate, defuse_kit_purchase_rate,
                    kills_on_eco_rounds, kills_on_full_buy, deaths_on_eco_rounds, deaths_on_full_buy,
                    economy_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['avg_money_saved_per_round'],
                    stat['force_buy_rounds'],
                    stat['eco_rounds_survived'],
                    stat['full_buy_rounds'],
                    stat['avg_weapon_cost'],
                    stat['armor_purchase_rate'],
                    stat['defuse_kit_purchase_rate'],
                    stat['kills_on_eco_rounds'],
                    stat['kills_on_full_buy'],
                    stat['deaths_on_eco_rounds'],
                    stat['deaths_on_full_buy'],
                    stat['economy_score']
                )
                for stat in economy_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} economy stats")
            
        except Exception as e:
            print(f"Error inserting economy stats: {e}")
            raise
    
    def insert_combat_stats(self, match_id, combat_stats):
        """Insert COMPLETE combat performance statistics"""
        if not combat_stats:
            return
        
        try:
            cursor = self.conn.cursor()
            
            query = """
                INSERT INTO player_combat_stats (
                    match_id, player_id, player_name,
                    won_aim_duels, lost_aim_duels, won_multi_kills, lost_multi_kills,
                    traded_teammate_deaths, got_traded_after_kill, trade_success_rate,
                    clutch_attempts, clutch_wins, clutch_win_rate,
                    killed_from_behind_pct, first_kill_rounds, first_death_rounds,
                    combat_score
                )
                VALUES %s
            """
            
            values = [
                (
                    match_id,
                    stat['player_id'],
                    stat['player_name'],
                    stat['won_aim_duels'],
                    stat['lost_aim_duels'],
                    stat['won_multi_kills'],
                    stat['lost_multi_kills'],
                    stat['traded_teammate_deaths'],
                    stat['got_traded_after_kill'],
                    stat['trade_success_rate'],
                    stat['clutch_attempts'],
                    stat['clutch_wins'],
                    stat['clutch_win_rate'],
                    stat['killed_from_behind_pct'],
                    stat['first_kill_rounds'],
                    stat['first_death_rounds'],
                    stat['combat_score']
                )
                for stat in combat_stats
            ]
            
            execute_values(cursor, query, values)
            cursor.close()
            
            print(f"Inserted {len(values)} combat stats")
            
        except Exception as e:
            print(f"Error inserting combat stats: {e}")
            raise
    
    def commit(self):
        """Commit the transaction"""
        try:
            self.conn.commit()
            print("Transaction committed")
        except Exception as e:
            print(f"Error committing transaction: {e}")
            self.conn.rollback()
            raise
    
    def rollback(self):
        """Rollback the transaction"""
        self.conn.rollback()
        print("Transaction rolled back")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")