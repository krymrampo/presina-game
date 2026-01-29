"""
Tests for Room Manager.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rooms.room_manager import RoomManager, Room
from game.player import Player
from game.presina_game import GamePhase


class TestRoomManager:
    """Tests for RoomManager class."""
    
    def setup_method(self):
        """Setup for each test."""
        self.manager = RoomManager()
    
    def test_create_room(self):
        """Test creating a room."""
        player = Player('p1', 'Player 1', 'sid1')
        room = self.manager.create_room('Test Room', player)
        
        assert room is not None
        assert room.name == 'Test Room'
        assert room.admin_id == 'p1'
        assert 'p1' in room.game.players
    
    def test_get_room(self):
        """Test getting a room by ID."""
        player = Player('p1', 'Player 1', 'sid1')
        room = self.manager.create_room('Test Room', player)
        
        found = self.manager.get_room(room.room_id)
        
        assert found is not None
        assert found.room_id == room.room_id
    
    def test_get_nonexistent_room(self):
        """Test getting a room that doesn't exist."""
        found = self.manager.get_room('nonexistent')
        assert found is None
    
    def test_join_room(self):
        """Test joining a room."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        player = Player('p1', 'Player 1', 'sid1')
        success, msg = self.manager.join_room(room.room_id, player)
        
        assert success is True
        assert 'p1' in room.game.players
    
    def test_join_full_room(self):
        """Test joining a full room."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        # Add 7 more players (max 8)
        for i in range(7):
            player = Player(f'p{i}', f'Player {i}', f'sid{i}')
            self.manager.join_room(room.room_id, player)
        
        # Try to add 9th player
        extra = Player('extra', 'Extra', 'sid_extra')
        success, msg = self.manager.join_room(room.room_id, extra)
        
        assert success is False
    
    def test_leave_room_waiting(self):
        """Test leaving a room in waiting phase."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        player = Player('p1', 'Player 1', 'sid1')
        self.manager.join_room(room.room_id, player)
        
        success, msg = self.manager.leave_room('p1')
        
        assert success is True
        assert 'p1' not in room.game.players
    
    def test_admin_reassignment(self):
        """Test admin is reassigned when admin leaves."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        player = Player('p1', 'Player 1', 'sid1')
        self.manager.join_room(room.room_id, player)
        
        self.manager.leave_room('admin')
        
        assert room.admin_id == 'p1'
    
    def test_room_deleted_when_empty(self):
        """Test room is deleted when last player leaves."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        room_id = room.room_id
        
        self.manager.leave_room('admin')
        
        assert self.manager.get_room(room_id) is None
    
    def test_kick_player(self):
        """Test kicking a player."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        player = Player('p1', 'Player 1', 'sid1')
        self.manager.join_room(room.room_id, player)
        
        success, msg = self.manager.kick_player('admin', 'p1')
        
        assert success is True
        assert 'p1' not in room.game.players
    
    def test_non_admin_cannot_kick(self):
        """Test non-admin cannot kick."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        player1 = Player('p1', 'Player 1', 'sid1')
        player2 = Player('p2', 'Player 2', 'sid2')
        self.manager.join_room(room.room_id, player1)
        self.manager.join_room(room.room_id, player2)
        
        success, msg = self.manager.kick_player('p1', 'p2')
        
        assert success is False
    
    def test_get_public_rooms(self):
        """Test getting public rooms."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Public Room', admin)
        
        public = self.manager.get_public_rooms()
        
        assert len(public) == 1
        assert public[0].name == 'Public Room'
    
    def test_search_rooms(self):
        """Test searching rooms by name."""
        admin1 = Player('admin1', 'Admin 1', 'sid_admin1')
        admin2 = Player('admin2', 'Admin 2', 'sid_admin2')
        
        self.manager.create_room('Test Room', admin1)
        self.manager.create_room('Another Room', admin2)
        
        results = self.manager.search_rooms('test')
        
        assert len(results) == 1
        assert 'Test' in results[0].name
    
    def test_rejoin_room(self):
        """Test rejoining a room after disconnect."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        self.manager.register_socket('sid_admin', 'admin')
        
        # Simulate disconnect
        self.manager.unregister_socket('sid_admin')
        
        # Rejoin with new socket
        success, msg, found_room = self.manager.rejoin_room('admin', 'new_sid')
        
        assert success is True
        assert found_room is not None
        player = room.game.get_player('admin')
        assert player.is_online is True
    
    def test_chat_message(self):
        """Test adding chat message."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        success, msg = self.manager.add_chat_message(room.room_id, 'admin', 'Hello!')
        
        assert success is True
        assert msg['message'] == 'Hello!'
        assert len(room.chat_messages) == 1
    
    def test_chat_message_limit(self):
        """Test chat message length limit."""
        admin = Player('admin', 'Admin', 'sid_admin')
        room = self.manager.create_room('Test Room', admin)
        
        long_message = 'x' * 300
        success, msg = self.manager.add_chat_message(room.room_id, 'admin', long_message)
        
        assert success is True
        assert len(msg['message']) == 200  # Truncated to 200


class TestRoom:
    """Tests for Room class."""
    
    def test_room_status_waiting(self):
        """Test room status is 'waiting' initially."""
        room = Room('id', 'Test', 'admin')
        assert room.status == 'waiting'
    
    def test_room_player_count(self):
        """Test room player count."""
        room = Room('id', 'Test', 'admin')
        
        player = Player('p1', 'Player 1')
        room.game.add_player(player)
        
        assert room.player_count == 1
    
    def test_room_serialization(self):
        """Test room to_dict."""
        room = Room('id', 'Test', 'admin')
        data = room.to_dict()
        
        assert 'room_id' in data
        assert 'name' in data
        assert 'status' in data
        assert 'player_count' in data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
