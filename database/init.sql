-- Create database
CREATE DATABASE IF NOT EXISTS cs2analytics;

-- Use the database
SET DATABASE = cs2analytics;

-- Matches table - stores basic match information
CREATE TABLE IF NOT EXISTS matches (
    match_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name STRING NOT NULL,
    map_name STRING,
    game_mode STRING,
    duration_seconds INT,
    winner_team STRING,
    ct_score INT,
    t_score INT,
    processed_at TIMESTAMP DEFAULT current_timestamp(),
    created_at TIMESTAMP DEFAULT current_timestamp()
);

-- Player stats per match - aggregated statistics
CREATE TABLE IF NOT EXISTS player_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL,
    player_id STRING NOT NULL,
    player_name STRING NOT NULL,
    team STRING NOT NULL,
    kills INT DEFAULT 0,
    deaths INT DEFAULT 0,
    assists INT DEFAULT 0,
    mvps INT DEFAULT 0,
    score INT DEFAULT 0,
    headshot_kills INT DEFAULT 0,
    total_damage INT DEFAULT 0,
    kd_ratio FLOAT,
    adr FLOAT,
    headshot_percentage FLOAT,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    CONSTRAINT fk_match FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    INDEX idx_player_id (player_id),
    INDEX idx_match_id (match_id)
);

-- Round details - stores round-by-round information
CREATE TABLE IF NOT EXISTS rounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL,
    round_number INT NOT NULL,
    winner_team STRING,
    end_reason STRING,
    duration_seconds INT,
    ct_equipment_value INT,
    t_equipment_value INT,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    CONSTRAINT fk_match_rounds FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    INDEX idx_match_rounds (match_id, round_number)
);

-- Kill events - detailed kill information
CREATE TABLE IF NOT EXISTS kills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL,
    round_number INT NOT NULL,
    tick INT NOT NULL,
    attacker_id STRING,
    attacker_name STRING,
    victim_id STRING,
    victim_name STRING,
    weapon STRING,
    is_headshot BOOLEAN DEFAULT false,
    assister_id STRING,
    assister_name STRING,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    CONSTRAINT fk_match_kills FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    INDEX idx_match_kills (match_id, round_number)
);

-- ML Predictions table (for Day 2)
CREATE TABLE IF NOT EXISTS ml_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL,
    predicted_winner STRING,
    confidence FLOAT,
    actual_winner STRING,
    prediction_correct BOOLEAN,
    created_at TIMESTAMP DEFAULT current_timestamp(),
    CONSTRAINT fk_match_predictions FOREIGN KEY (match_id) REFERENCES matches(match_id) ON DELETE CASCADE,
    INDEX idx_match_predictions (match_id)
);

-- Processing status tracking (prevents duplicate processing)
CREATE TABLE IF NOT EXISTS processing_status (
    file_name STRING PRIMARY KEY,
    status STRING NOT NULL,
    match_id UUID,
    error_message STRING,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT current_timestamp()
);

CREATE TABLE player_movement_stats (
    movement_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Distance & Velocity
    total_distance_traveled DECIMAL(10,2),
    avg_velocity DECIMAL(6,2),
    time_walking_pct DECIMAL(5,2),
    time_running_pct DECIMAL(5,2),
    time_crouched_pct DECIMAL(5,2),
    
    -- Jump & Air Movement
    jump_count INT,
    time_airborne_pct DECIMAL(5,2),
    bhop_attempts INT,
    successful_bhops INT,
    
    -- Strafing
    time_strafing_pct DECIMAL(5,2),
    strafe_efficiency DECIMAL(5,2),
    
    -- Movement Score (aggregate 0-100)
    movement_score DECIMAL(5,2)
);

CREATE INDEX idx_movement_player ON player_movement_stats(player_id);
CREATE INDEX idx_movement_match ON player_movement_stats(match_id);

CREATE TABLE player_aim_stats (
    aim_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Crosshair Placement
    avg_crosshair_height DECIMAL(6,2),
    crosshair_on_enemy_pct DECIMAL(5,2),
    pre_aim_accuracy DECIMAL(5,2),
    
    -- Shooting Mechanics
    first_bullet_accuracy DECIMAL(5,2),
    spray_control_accuracy DECIMAL(5,2),
    burst_fire_pct DECIMAL(5,2),
    
    -- Reaction & Flicks
    avg_reaction_time_ms INT,
    avg_flick_distance DECIMAL(6,2),
    flick_accuracy DECIMAL(5,2),
    
    -- Kill Quality
    one_tap_kills INT,
    spray_kills INT,
    avg_bullets_to_kill DECIMAL(4,1),
    
    -- Aim Score (aggregate 0-100)
    aim_score DECIMAL(5,2)
);

CREATE INDEX idx_aim_player ON player_aim_stats(player_id);
CREATE INDEX idx_aim_match ON player_aim_stats(match_id);

CREATE TABLE player_positioning_stats (
    position_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    team VARCHAR(10),
    
    -- Death Analysis
    deaths_to_peekers INT,
    deaths_while_moving INT,
    deaths_from_behind INT,
    deaths_in_open INT,
    
    -- Positioning Behavior
    avg_time_to_contact DECIMAL(6,2),
    early_deaths_pct DECIMAL(5,2),
    entry_frag_success_pct DECIMAL(5,2),
    hold_success_pct DECIMAL(5,2),
    
    -- Map Control
    time_in_safe_zone_pct DECIMAL(5,2),
    time_pushed_up_pct DECIMAL(5,2),
    rotations_count INT,
    late_rotations INT,
    
    -- Positioning Score (aggregate 0-100)
    positioning_score DECIMAL(5,2)
);

CREATE INDEX idx_positioning_player ON player_positioning_stats(player_id);
CREATE INDEX idx_positioning_match ON player_positioning_stats(match_id);

CREATE TABLE player_utility_stats (
    utility_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Grenade Usage
    flashbangs_thrown INT,
    smokes_thrown INT,
    molotovs_thrown INT,
    he_grenades_thrown INT,
    decoys_thrown INT,
    
    -- Utility Effectiveness
    enemies_flashed INT,
    avg_flash_duration DECIMAL(5,2),
    teammates_flashed INT,
    
    utility_damage_dealt INT,
    smoke_effectiveness_score DECIMAL(5,2),
    
    -- Timing
    utility_wasted INT,
    utility_used_in_execute_pct DECIMAL(5,2),
    
    -- Utility Score (aggregate 0-100)
    utility_score DECIMAL(5,2)
);

CREATE INDEX idx_utility_player ON player_utility_stats(player_id);
CREATE INDEX idx_utility_match ON player_utility_stats(match_id);

CREATE TABLE player_economy_stats (
    economy_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Money Management
    avg_money_saved_per_round DECIMAL(8,2),
    force_buy_rounds INT,
    eco_rounds_survived INT,
    full_buy_rounds INT,
    
    -- Equipment Choices
    avg_weapon_cost DECIMAL(8,2),
    armor_purchase_rate DECIMAL(5,2),
    defuse_kit_purchase_rate DECIMAL(5,2),
    
    -- Performance by Economy
    kills_on_eco_rounds INT,
    kills_on_full_buy INT,
    deaths_on_eco_rounds INT,
    deaths_on_full_buy INT,
    
    -- Economy Score (aggregate 0-100)
    economy_score DECIMAL(5,2)
);

CREATE INDEX idx_economy_player ON player_economy_stats(player_id);
CREATE INDEX idx_economy_match ON player_economy_stats(match_id);

CREATE TABLE player_combat_stats (
    combat_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Engagement Types
    won_aim_duels INT,
    lost_aim_duels INT,
    won_multi_kills INT,
    lost_multi_kills INT,
    
    -- Trading
    traded_teammate_deaths INT,
    got_traded_after_kill INT,
    trade_success_rate DECIMAL(5,2),
    
    -- Clutch Performance
    clutch_attempts INT,
    clutch_wins INT,
    clutch_win_rate DECIMAL(5,2),
    
    -- Combat Awareness
    killed_from_behind_pct DECIMAL(5,2),
    first_kill_rounds INT,
    first_death_rounds INT,
    
    -- Combat Score (aggregate 0-100)
    combat_score DECIMAL(5,2)
);

CREATE INDEX idx_combat_player ON player_combat_stats(player_id);
CREATE INDEX idx_combat_match ON player_combat_stats(match_id);

CREATE TABLE death_locations (
    death_location_id SERIAL PRIMARY KEY,
    match_id UUID REFERENCES matches(match_id),
    player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(100),
    
    -- Death Position
    death_x DECIMAL(10,2),
    death_y DECIMAL(10,2),
    death_z DECIMAL(10,2),
    
    -- Killer Position
    killer_x DECIMAL(10,2),
    killer_y DECIMAL(10,2),
    killer_z DECIMAL(10,2),
    
    -- Context
    round_number INT,
    tick INT,
    weapon VARCHAR(50),
    was_holding_angle BOOLEAN,
    was_moving BOOLEAN
);

CREATE INDEX idx_death_loc_player ON death_locations(player_id);
CREATE INDEX idx_death_loc_match ON death_locations(match_id);
