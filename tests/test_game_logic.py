"""
Tests for game logic (PresinaGameOnline).
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.presina_game import PresinaGameOnline, GamePhase
from game.player import Player
from game.card import Card


class TestPresinaGame:
    """Tests for PresinaGameOnline class."""
    
    def setup_method(self):
        """Setup for each test."""
        self.game = PresinaGameOnline('test_room')
    
    def add_players(self, count):
        """Helper to add players to game."""
        players = []
        for i in range(count):
            player = Player(f'player_{i}', f'Player {i}', f'sid_{i}')
            self.game.add_player(player)
            players.append(player)
        return players
    
    def test_game_creation(self):
        """Test game is created in waiting phase."""
        assert self.game.phase == GamePhase.WAITING
        assert self.game.room_id == 'test_room'
        assert len(self.game.players) == 0
    
    def test_add_players(self):
        """Test adding players."""
        players = self.add_players(3)
        
        assert len(self.game.players) == 3
        assert len(self.game.player_order) == 3
    
    def test_max_players(self):
        """Test max 8 players."""
        self.add_players(8)
        
        extra_player = Player('extra', 'Extra', 'sid_extra')
        result = self.game.add_player(extra_player)
        
        assert result is False
        assert len(self.game.players) == 8
    
    def test_remove_player_waiting(self):
        """Test removing player in waiting phase."""
        players = self.add_players(3)
        
        result = self.game.remove_player('player_1')
        
        assert result is True
        assert len(self.game.players) == 2
        assert 'player_1' not in self.game.players
    
    def test_cannot_start_with_one_player(self):
        """Test game cannot start with < 2 players."""
        self.add_players(1)
        
        assert self.game.can_start() is False
    
    def test_can_start_with_two_players(self):
        """Test game can start with 2+ players."""
        self.add_players(2)
        
        assert self.game.can_start() is True
    
    def test_start_game(self):
        """Test starting the game."""
        self.add_players(3)
        
        result = self.game.start_game()
        
        assert result is True
        assert self.game.phase == GamePhase.BETTING
        assert self.game.current_turn == 0
    
    def test_cards_dealt(self):
        """Test correct number of cards dealt."""
        self.add_players(3)
        self.game.start_game()
        
        for player in self.game.players.values():
            assert len(player.hand) == 5  # First turn has 5 cards
    
    def test_betting_order(self):
        """Test betting happens in order."""
        players = self.add_players(3)
        self.game.start_game()
        
        # First player should be current better
        current_better = self.game.get_current_better()
        assert current_better is not None
    
    def test_make_valid_bet(self):
        """Test making a valid bet."""
        players = self.add_players(2)
        self.game.start_game()
        
        current_better = self.game.get_current_better()
        success, msg = self.game.make_bet(current_better.player_id, 2)
        
        assert success is True
        assert current_better.bet == 2
    
    def test_make_invalid_bet_too_high(self):
        """Test bet > cards is invalid."""
        players = self.add_players(2)
        self.game.start_game()
        
        current_better = self.game.get_current_better()
        success, msg = self.game.make_bet(current_better.player_id, 10)
        
        assert success is False
    
    def test_forbidden_bet_for_last_player(self):
        """Test last player cannot make sum = cards."""
        players = self.add_players(2)
        self.game.start_game()
        
        # First player bets 3 (out of 5 cards)
        first_better = self.game.get_current_better()
        self.game.make_bet(first_better.player_id, 3)
        
        # Last player cannot bet 2 (3+2=5)
        forbidden = self.game.get_forbidden_bet()
        assert forbidden == 2
        
        second_better = self.game.get_current_better()
        success, msg = self.game.make_bet(second_better.player_id, 2)
        
        assert success is False
    
    def test_transition_to_playing(self):
        """Test transition from betting to playing."""
        players = self.add_players(2)
        self.game.start_game()
        
        # Both players bet
        first = self.game.get_current_better()
        self.game.make_bet(first.player_id, 2)
        
        second = self.game.get_current_better()
        # Bet something allowed (not forbidden)
        forbidden = self.game.get_forbidden_bet()
        bet = 0 if forbidden != 0 else 1
        self.game.make_bet(second.player_id, bet)
        
        assert self.game.phase == GamePhase.PLAYING
    
    def test_play_card(self):
        """Test playing a card."""
        players = self.add_players(2)
        self.game.start_game()
        
        # Complete betting
        for _ in range(2):
            better = self.game.get_current_better()
            forbidden = self.game.get_forbidden_bet()
            bet = 0 if forbidden != 0 else 1
            self.game.make_bet(better.player_id, bet)
        
        # Play a card
        current_player = self.game.get_current_player()
        card = current_player.hand[0]
        
        success, msg = self.game.play_card(current_player.player_id, card.suit, card.value)
        
        assert success is True
        assert len(self.game.cards_on_table) == 1
    
    def test_special_turn(self):
        """Test special turn detection (1 card turn)."""
        # Turn 4 (index 4) has 1 card
        self.game.current_turn = 4
        assert self.game.is_special_turn() is True
        
        self.game.current_turn = 0
        assert self.game.is_special_turn() is False
    
    def test_player_life_loss_wrong_bet(self):
        """Test player loses life with wrong bet."""
        player = Player('p1', 'Player 1')
        player.bet = 2
        player.tricks_won = 3  # Different from bet
        
        change = player.calculate_life_change()
        assert change == -1
    
    def test_player_no_life_loss_correct_bet(self):
        """Test player keeps life with correct bet."""
        player = Player('p1', 'Player 1')
        player.bet = 2
        player.tricks_won = 2  # Same as bet
        
        change = player.calculate_life_change()
        assert change == 0
    
    def test_get_state_for_player(self):
        """Test game state serialization."""
        players = self.add_players(2)
        self.game.start_game()
        
        state = self.game.get_state_for_player('player_0')
        
        assert 'room_id' in state
        assert 'phase' in state
        assert 'players' in state
        assert 'current_turn' in state
        assert 'cards_this_turn' in state
    
    def test_get_active_players(self):
        """Test getting active (non-spectator) players."""
        players = self.add_players(3)
        players[1].is_spectator = True
        
        active = self.game.get_active_players()
        
        assert len(active) == 2
        assert players[1] not in active


class TestPlayerIntegration:
    """Integration tests for Player in game context."""
    
    def test_player_initial_lives(self):
        """Test player starts with 5 lives."""
        player = Player('p1', 'Test')
        assert player.lives == 5
    
    def test_player_reset_for_turn(self):
        """Test player state reset between turns."""
        player = Player('p1', 'Test')
        player.bet = 3
        player.tricks_won = 2
        player.hand = [Card('Bastoni', 1)]
        
        player.reset_for_turn()
        
        assert player.bet is None
        assert player.tricks_won == 0
        assert len(player.hand) == 0
    
    def test_player_eliminated(self):
        """Test player elimination at 0 lives."""
        player = Player('p1', 'Test')
        player.lives = 1
        player.bet = 0
        player.tricks_won = 1  # Wrong bet
        
        player.apply_life_change()
        
        assert player.lives == 0
        assert player.is_eliminated is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
