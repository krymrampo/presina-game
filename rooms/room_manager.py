"""
Room Manager for Presina game.
Handles room creation, joining, and lobby management.
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import time
import uuid

from game.player import Player
from game.presina_game import PresinaGameOnline, GamePhase


@dataclass
class Room:
    """A game room."""
    room_id: str
    name: str
    admin_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    is_public: bool = True
    access_code: Optional[str] = None  # Code for private rooms
    game: PresinaGameOnline = None
    chat_messages: List[dict] = field(default_factory=list)
    
    def __post_init__(self):
        if self.game is None:
            self.game = PresinaGameOnline(self.room_id)
    
    def update_activity(self):
        """Update last activity timestamp."""
        self.last_activity = time.time()
    
    def is_stale(self, max_age_hours: float = 24.0) -> bool:
        """Check if room has been inactive for too long."""
        age = time.time() - self.last_activity
        return age > (max_age_hours * 3600)
    
    def is_finished_and_stale(self, max_age_minutes: float = 30.0) -> bool:
        """Check if finished game room should be cleaned up."""
        if self.game.phase != GamePhase.GAME_OVER:
            return False
        age = time.time() - self.last_activity
        return age > (max_age_minutes * 60)
    
    @property
    def status(self) -> str:
        """Get room status."""
        if self.game.phase == GamePhase.WAITING:
            return "waiting"
        elif self.game.phase == GamePhase.GAME_OVER:
            return "finished"
        else:
            return "playing"
    
    @property
    def player_count(self) -> int:
        """Get current player count."""
        return len(self.game.players)
    
    def to_dict(self) -> dict:
        """Serialize room for lobby display."""
        return {
            'room_id': self.room_id,
            'name': self.name,
            'admin_id': self.admin_id,
            'status': self.status,
            'player_count': self.player_count,
            'max_players': PresinaGameOnline.MAX_PLAYERS,
            'is_public': self.is_public,
            'is_private': not self.is_public,
            'created_at': self.created_at
        }
    
    def to_dict_with_code(self) -> dict:
        """Serialize room including access code (for admin only)."""
        data = self.to_dict()
        data['access_code'] = self.access_code
        return data


class RoomManager:
    """Manages all game rooms."""
    
    MAX_CHAT_MESSAGES = 100
    ROOM_MAX_AGE_HOURS = 24.0  # Delete inactive rooms after 24h
    FINISHED_ROOM_MAX_AGE_MINUTES = 30.0  # Delete finished games after 30min
    
    def __init__(self):
        self.rooms: Dict[str, Room] = {}
        self.player_rooms: Dict[str, str] = {}  # player_id -> room_id
        self.sid_to_player: Dict[str, str] = {}  # socket sid -> player_id
    
    def cleanup_stale_rooms(self) -> int:
        """
        Remove old inactive rooms.
        Returns number of rooms deleted.
        """
        to_delete = []
        
        for room_id, room in self.rooms.items():
            # Remove finished games after shorter timeout
            if room.is_finished_and_stale(self.FINISHED_ROOM_MAX_AGE_MINUTES):
                to_delete.append(room_id)
            # Remove very old inactive rooms
            elif room.is_stale(self.ROOM_MAX_AGE_HOURS):
                to_delete.append(room_id)
        
        for room_id in to_delete:
            self.delete_room(room_id)
        
        return len(to_delete)
    
    # ==================== Room Management ====================
    
    def create_room(self, name: str, admin_player: Player, is_public: bool = True, access_code: Optional[str] = None) -> Room:
        """
        Create a new room.
        
        Args:
            name: Room name
            admin_player: The player creating the room (becomes admin)
            
        Returns:
            The created room
        """
        room_id = str(uuid.uuid4())[:8]
        while room_id in self.rooms:
            room_id = str(uuid.uuid4())[:8]
        room = Room(room_id=room_id, name=name, admin_id=admin_player.player_id, 
                    is_public=is_public, access_code=access_code)
        
        # Add admin to the room
        room.game.add_player(admin_player)
        
        self.rooms[room_id] = room
        self.player_rooms[admin_player.player_id] = room_id
        
        return room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """Get a room by ID."""
        return self.rooms.get(room_id)
    
    def delete_room(self, room_id: str):
        """Delete a room."""
        if room_id in self.rooms:
            room = self.rooms[room_id]
            # Remove all players from player_rooms mapping
            for pid in list(room.game.players.keys()):
                if pid in self.player_rooms:
                    del self.player_rooms[pid]
            del self.rooms[room_id]
    
    def get_public_rooms(self) -> List[Room]:
        """Get all public rooms for the lobby."""
        return [r for r in self.rooms.values() if r.is_public]
    
    def search_rooms(self, query: str) -> List[Room]:
        """Search rooms by name."""
        query = query.lower()
        return [r for r in self.get_public_rooms() if query in r.name.lower()]
    
    # ==================== Player Management ====================
    
    def join_room(self, room_id: str, player: Player, access_code: Optional[str] = None) -> tuple[bool, str]:
        """
        Join a room.
        
        Args:
            room_id: Room to join
            player: Player joining
            
        Returns:
            (success, message)
        """
        room = self.get_room(room_id)
        if not room:
            return False, "Stanza non trovata"
        
        # Update activity
        room.update_activity()

        # Check access code for private rooms
        if not room.is_public:
            if room.access_code is None:
                return False, "Stanza privata non configurata correttamente"
            if access_code != room.access_code:
                return False, "Codice di accesso errato"
        
        # Disallow joining finished games
        if room.game.phase == GamePhase.GAME_OVER:
            return False, "Partita finita"
        
        # Check if player is already in another room
        if player.player_id in self.player_rooms:
            old_room_id = self.player_rooms[player.player_id]
            if old_room_id != room_id:
                return False, "Sei già in un'altra stanza"
        
        # Check if game is in progress
        if room.game.phase != GamePhase.WAITING:
            # If we're already in the last turn, no next turn to join
            last_turn_index = len(PresinaGameOnline.CARDS_PER_TURN) - 1
            if room.game.current_turn >= last_turn_index:
                return False, "Non puoi entrare nell'ultimo turno"
            # Join as spectator or for next turn
            if room.player_count >= PresinaGameOnline.MAX_PLAYERS:
                return False, "Stanza piena"
            
            player.is_spectator = True
            player.join_next_turn = True
            # Set lives to minimum of active players
            active = room.game.get_active_players()
            if active:
                player.lives = min(p.lives for p in active)
            
            if not room.game.add_player(player):
                return False, "Impossibile entrare"
            
            self.player_rooms[player.player_id] = room_id
            return True, "Entrato come spettatore, giocherai dal prossimo turno"
        
        # Normal join
        if not room.game.add_player(player):
            return False, "Stanza piena"
        
        self.player_rooms[player.player_id] = room_id
        return True, "Entrato nella stanza"
    
    def leave_room(self, player_id: str) -> tuple[bool, str]:
        """
        Leave current room.
        
        Returns:
            (success, message)
        """
        if player_id not in self.player_rooms:
            return False, "Non sei in nessuna stanza"
        
        room_id = self.player_rooms[player_id]
        room = self.get_room(room_id)
        
        if room:
            room.update_activity()
        
        if not room:
            del self.player_rooms[player_id]
            return True, "Uscito dalla stanza"

        # If game is over, allow a full leave and cleanup
        if room.game.phase == GamePhase.GAME_OVER:
            if player_id in room.game.players:
                del room.game.players[player_id]
                if player_id in room.game.player_order:
                    room.game.player_order.remove(player_id)

            if player_id in self.player_rooms:
                del self.player_rooms[player_id]

            # Handle admin reassignment or room deletion
            if len(room.game.players) == 0:
                self.delete_room(room_id)
            elif room.admin_id == player_id:
                room.admin_id = list(room.game.players.keys())[0]

            return True, "Uscito dalla stanza"
        
        # If game is in progress, mark as offline instead of removing
        if room.game.phase != GamePhase.WAITING:
            player = room.game.get_player(player_id)
            if player:
                player.is_online = False
            # Try to auto-advance if an offline player is blocking
            room.game.auto_advance_offline()
            # Don't remove from player_rooms so they can rejoin
            return True, "Disconnesso dalla partita"
        
        # Remove from game
        room.game.remove_player(player_id)
        del self.player_rooms[player_id]
        
        # Handle admin reassignment or room deletion
        if len(room.game.players) == 0:
            self.delete_room(room_id)
        elif room.admin_id == player_id:
            # Assign new admin
            new_admin_id = list(room.game.players.keys())[0]
            room.admin_id = new_admin_id
        
        return True, "Uscito dalla stanza"
    
    def kick_player(self, admin_id: str, player_id: str) -> tuple[bool, str]:
        """
        Kick a player from a room (admin only, waiting phase only).
        
        Returns:
            (success, message)
        """
        if admin_id not in self.player_rooms:
            return False, "Non sei in nessuna stanza"
        
        room_id = self.player_rooms[admin_id]
        room = self.get_room(room_id)
        
        if not room:
            return False, "Stanza non trovata"
        
        if room.admin_id != admin_id:
            return False, "Solo l'admin può rimuovere giocatori"
        
        if room.game.phase != GamePhase.WAITING:
            return False, "Non puoi rimuovere giocatori a partita iniziata"
        
        if player_id == admin_id:
            return False, "Non puoi rimuoverti da solo"
        
        if player_id not in room.game.players:
            return False, "Giocatore non trovato"
        
        room.game.remove_player(player_id)
        if player_id in self.player_rooms:
            del self.player_rooms[player_id]
        
        return True, "Giocatore rimosso"
    
    def get_player_room(self, player_id: str) -> Optional[Room]:
        """Get the room a player is in."""
        if player_id not in self.player_rooms:
            return None
        return self.get_room(self.player_rooms[player_id])
    
    # ==================== Reconnection ====================
    
    def rejoin_room(self, player_id: str, new_sid: str) -> tuple[bool, str, Optional[Room]]:
        """
        Rejoin a room after disconnection.
        
        Returns:
            (success, message, room)
        """
        if player_id not in self.player_rooms:
            return False, "Non eri in nessuna stanza", None
        
        room_id = self.player_rooms[player_id]
        room = self.get_room(room_id)
        
        if not room:
            del self.player_rooms[player_id]
            return False, "Stanza non più esistente", None
        
        player = room.game.get_player(player_id)
        if not player:
            del self.player_rooms[player_id]
            return False, "Non sei più in questa stanza", None
        
        # Update player's socket and online status
        player.sid = new_sid
        player.is_online = True
        
        return True, "Riconnesso alla stanza", room
    
    # ==================== Socket Mapping ====================
    
    def register_socket(self, sid: str, player_id: str):
        """Register a socket ID to a player."""
        self.sid_to_player[sid] = player_id
    
    def unregister_socket(self, sid: str):
        """Unregister a socket and mark player offline."""
        if sid in self.sid_to_player:
            player_id = self.sid_to_player[sid]
            del self.sid_to_player[sid]
            
            # Mark player as offline
            room = self.get_player_room(player_id)
            if room:
                player = room.game.get_player(player_id)
                if player:
                    player.is_online = False
                    room.game.auto_advance_offline()
                
                # Handle admin reassignment if admin disconnects
                if room.admin_id == player_id:
                    # Find another online player
                    for pid, p in room.game.players.items():
                        if p.is_online and pid != player_id:
                            room.admin_id = pid
                            break
                
                # Check if all players are offline - close the room if game is in progress
                if room.game.phase != GamePhase.WAITING and room.game.phase != GamePhase.GAME_OVER:
                    all_offline = all(not p.is_online for p in room.game.players.values())
                    if all_offline:
                        # All players offline - delete the room
                        self.delete_room(room.room_id)
                        return
    
    def get_player_by_sid(self, sid: str) -> Optional[str]:
        """Get player ID from socket ID."""
        return self.sid_to_player.get(sid)
    
    # ==================== Chat ====================
    
    def add_chat_message(self, room_id: str, player_id: str, message: str) -> tuple[bool, dict]:
        """
        Add a chat message to a room.
        
        Returns:
            (success, message_dict)
        """
        room = self.get_room(room_id)
        if not room:
            return False, {}
        
        # Update activity
        room.update_activity()
        
        player = room.game.get_player(player_id)
        if not player:
            return False, {}
        
        # Limit message length
        message = message[:200]
        
        msg_dict = {
            'player_id': player_id,
            'player_name': player.name,
            'message': message,
            'timestamp': time.time()
        }
        
        room.chat_messages.append(msg_dict)
        
        # Keep only last N messages
        if len(room.chat_messages) > self.MAX_CHAT_MESSAGES:
            room.chat_messages = room.chat_messages[-self.MAX_CHAT_MESSAGES:]
        
        return True, msg_dict


# Singleton instance
room_manager = RoomManager()
