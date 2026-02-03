"""
User model and authentication system for Presina
"""
import hashlib
import secrets
import time
import os
import base64
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import extras
UPLOADS_PATH = Path(__file__).parent.parent / "uploads" / "avatars"
DEFAULT_AVATAR_URL = "/static/img/logo.png"

# Ensure uploads directory exists
UPLOADS_PATH.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    """Get a database connection"""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL non impostata. Impostala per usare Postgres.")
    conn = psycopg2.connect(database_url, sslmode="require")
    return conn


def init_database():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            display_name TEXT,
            avatar TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            session_token TEXT,
            session_expires BIGINT
        )
    ''')
    
    # User statistics table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            games_played INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            games_lost INTEGER DEFAULT 0,
            total_lives_lost INTEGER DEFAULT 0,
            total_lives_remaining INTEGER DEFAULT 0,
            total_bets_correct INTEGER DEFAULT 0,
            total_bets_wrong INTEGER DEFAULT 0,
            total_tricks_won INTEGER DEFAULT 0,
            best_streak INTEGER DEFAULT 0,
            current_streak INTEGER DEFAULT 0,
            favorite_suit TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Game history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS game_history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            room_name TEXT,
            players_count INTEGER,
            final_position INTEGER,
            final_lives INTEGER,
            lives_lost INTEGER,
            bets_correct INTEGER,
            bets_wrong INTEGER,
            tricks_won INTEGER,
            won BOOLEAN,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Achievements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS achievements (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            achievement_id TEXT NOT NULL,
            achievement_name TEXT,
            achievement_description TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, achievement_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database initialized successfully")


class User:
    def __init__(self, user_id=None, username=None, display_name=None, 
                 avatar=None, created_at=None, last_login=None, is_active=True):
        self.id = user_id
        self.username = username
        self.display_name = display_name or username
        self.avatar = avatar
        self.created_at = created_at
        self.last_login = last_login
        self.is_active = is_active
        self.stats = None
    
    @staticmethod
    def hash_password(password):
        """Hash a password with salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}${pwd_hash}"
    
    @staticmethod
    def verify_password(password, hashed):
        """Verify a password against its hash"""
        try:
            salt, stored_hash = hashed.split('$')
            pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            return pwd_hash == stored_hash
        except:
            return False
    
    @staticmethod
    def generate_session_token():
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    @classmethod
    def register(cls, username, password, email=None, display_name=None):
        """Register a new user"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        try:
            # Check if username exists
        cursor.execute('SELECT id FROM users WHERE username = %s', (username.lower(),))
        if cursor.fetchone():
            return None, "Username già in uso"
            
            # Create user
            password_hash = cls.hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, display_name)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (username.lower(), password_hash, email, display_name or username))
            
            user_id = cursor.fetchone()['id']
            
            # Initialize stats
            cursor.execute('''
                INSERT INTO user_stats (user_id) VALUES (%s)
            ''', (user_id,))
            
            conn.commit()
            
            return cls.get_by_id(user_id), None
            
        except Exception as e:
            conn.rollback()
            return None, str(e)
        finally:
            conn.close()
    
    @classmethod
    def login(cls, username, password):
        """Login a user"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT id, username, password_hash, display_name, avatar, 
                   created_at, last_login, is_active
            FROM users WHERE username = %s AND is_active = TRUE
        ''', (username.lower(),))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None, "Username o password non validi"
        
        if not cls.verify_password(password, row['password_hash']):
            return None, "Username o password non validi"
        
        # Create session
        user = cls(
            user_id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            avatar=row['avatar'],
            created_at=row['created_at'],
            last_login=row['last_login'],
            is_active=row['is_active']
        )
        
        # Update last login and create session
        session_token = user.create_session()
        
        return {'user': user, 'token': session_token}, None
    
    @classmethod
    def get_by_id(cls, user_id):
        """Get user by ID"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT id, username, display_name, avatar, created_at, last_login, is_active
            FROM users WHERE id = %s
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return cls(
            user_id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            avatar=row['avatar'],
            created_at=row['created_at'],
            last_login=row['last_login'],
            is_active=row['is_active']
        )
    
    @classmethod
    def get_by_token(cls, token):
        """Get user by session token"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT id, username, display_name, avatar, created_at, last_login, is_active
            FROM users 
            WHERE session_token = %s AND session_expires > %s
        ''', (token, int(time.time())))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return cls(
            user_id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            avatar=row['avatar'],
            created_at=row['created_at'],
            last_login=row['last_login'],
            is_active=row['is_active']
        )
    
    def create_session(self, duration_days=7):
        """Create a session token"""
        token = self.generate_session_token()
        expires = int(time.time()) + (duration_days * 24 * 60 * 60)
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            UPDATE users 
            SET session_token = %s, session_expires = %s, last_login = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (token, expires, self.id))
        
        conn.commit()
        conn.close()
        
        return token
    
    def logout(self):
        """Clear session"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            UPDATE users SET session_token = NULL, session_expires = NULL
            WHERE id = %s
        ''', (self.id,))
        
        conn.commit()
        conn.close()
    
    def get_stats(self):
        """Get user statistics"""
        if self.stats:
            return self.stats
        
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM user_stats WHERE user_id = %s
        ''', (self.id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.stats = dict(row)
            # Calculate win rate
            if self.stats['games_played'] > 0:
                self.stats['win_rate'] = round(
                    (self.stats['games_won'] / self.stats['games_played']) * 100, 1
                )
            else:
                self.stats['win_rate'] = 0
            
            # Calculate average lives
            if self.stats['games_played'] > 0:
                self.stats['avg_lives_remaining'] = round(
                    self.stats['total_lives_remaining'] / self.stats['games_played'], 1
                )
            else:
                self.stats['avg_lives_remaining'] = 0
        
        return self.stats or {}
    
    def update_stats_after_game(self, game_result):
        """Update stats after a game"""
        if self.stats is None:
            self.get_stats()
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        try:
            # Update game history
            cursor.execute('''
                INSERT INTO game_history 
                (user_id, room_name, players_count, final_position, final_lives,
                 lives_lost, bets_correct, bets_wrong, tricks_won, won)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                self.id,
                game_result.get('room_name', 'Unknown'),
                game_result.get('players_count', 0),
                game_result.get('final_position', 0),
                game_result.get('final_lives', 0),
                game_result.get('lives_lost', 0),
                game_result.get('bets_correct', 0),
                game_result.get('bets_wrong', 0),
                game_result.get('tricks_won', 0),
                game_result.get('won', False)
            ))
            
            # Update aggregated stats
            won = game_result.get('won', False)
            if won:
                new_streak = self.stats.get('current_streak', 0) + 1
            else:
                new_streak = 0
            best_streak = max(self.stats.get('best_streak', 0), new_streak)
            
            cursor.execute('''
                UPDATE user_stats SET
                    games_played = games_played + 1,
                    games_won = games_won + %s,
                    games_lost = games_lost + %s,
                    total_lives_lost = total_lives_lost + %s,
                    total_lives_remaining = total_lives_remaining + %s,
                    total_bets_correct = total_bets_correct + %s,
                    total_bets_wrong = total_bets_wrong + %s,
                    total_tricks_won = total_tricks_won + %s,
                    current_streak = %s,
                    best_streak = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (
                1 if won else 0,
                0 if won else 1,
                game_result.get('lives_lost', 0),
                game_result.get('final_lives', 0),
                game_result.get('bets_correct', 0),
                game_result.get('bets_wrong', 0),
                game_result.get('tricks_won', 0),
                new_streak,
                best_streak,
                self.id
            ))
            
            conn.commit()
            
            # Reload stats
            self.stats = None
            self.get_stats()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_recent_games(self, limit=10):
        """Get recent game history"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM game_history 
            WHERE user_id = %s
            ORDER BY played_at DESC
            LIMIT %s
        ''', (self.id, limit))
        
        games = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return games
    
    def get_achievements(self):
        """Get user achievements"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        
        cursor.execute('''
            SELECT * FROM achievements 
            WHERE user_id = %s
            ORDER BY unlocked_at DESC
        ''', (self.id,))
        
        achievements = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return achievements
    
    def update_avatar(self, image_data):
        """Update user avatar from base64 image data"""
        if not image_data:
            return False
        
        try:
            # Remove data URL prefix if present
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            # Decode base64
            image_bytes = base64.b64decode(image_data)
            
            # Validate size (max 2MB)
            if len(image_bytes) > 2 * 1024 * 1024:
                return False, "Immagine troppo grande (max 2MB)"
            
            # Generate filename
            filename = f"user_{self.id}_{int(time.time())}.png"
            filepath = UPLOADS_PATH / filename
            
            # Save file
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            # Remove old avatar if exists
            if self.avatar:
                if self.avatar.startswith('/uploads/avatars/'):
                    old_path = Path(__file__).parent.parent / self.avatar.lstrip('/')
                    if old_path.exists():
                        try:
                            old_path.unlink()
                        except:
                            pass
            
            # Update database
            avatar_url = f"/uploads/avatars/{filename}"
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
            cursor.execute(
                'UPDATE users SET avatar = %s WHERE id = %s',
                (avatar_url, self.id)
            )
            conn.commit()
            conn.close()
            
            self.avatar = avatar_url
            return True, avatar_url
            
        except Exception as e:
            return False, str(e)

    def update_display_name(self, display_name):
        """Update user display name"""
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute(
            'UPDATE users SET display_name = %s WHERE id = %s',
            (display_name, self.id)
        )
        conn.commit()
        conn.close()
        self.display_name = display_name
    
    def to_dict(self, include_stats=False):
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'avatar': self.avatar or DEFAULT_AVATAR_URL,
            'created_at': self.created_at,
            'last_login': self.last_login
        }
        
        if include_stats:
            data['stats'] = self.get_stats()
        
        return data


# Initialize database on module import
init_database()
