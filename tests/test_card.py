"""
Tests for Card class.
"""
import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.card import Card


class TestCard:
    """Tests for Card class."""
    
    def test_card_creation(self):
        """Test creating a valid card."""
        card = Card('Bastoni', 1)
        assert card.suit == 'Bastoni'
        assert card.value == 1
        assert card.display_name == 'Asso di Bastoni'
    
    def test_invalid_suit(self):
        """Test creating card with invalid suit raises error."""
        with pytest.raises(ValueError):
            Card('Invalid', 1)
    
    def test_invalid_value_low(self):
        """Test creating card with value < 1 raises error."""
        with pytest.raises(ValueError):
            Card('Bastoni', 0)
    
    def test_invalid_value_high(self):
        """Test creating card with value > 10 raises error."""
        with pytest.raises(ValueError):
            Card('Bastoni', 11)
    
    def test_card_strength_order(self):
        """Test that card strength follows correct order."""
        # Bastoni < Spade < Coppe < Ori
        bastoni_1 = Card('Bastoni', 1)
        spade_1 = Card('Spade', 1)
        coppe_1 = Card('Coppe', 1)
        ori_1 = Card('Ori', 1)
        
        # Note: Ori 1 is the Jolly, so we need to test with value 2
        bastoni_2 = Card('Bastoni', 2)
        ori_2 = Card('Ori', 2)
        
        assert bastoni_1.get_strength() < spade_1.get_strength()
        assert spade_1.get_strength() < coppe_1.get_strength()
        assert bastoni_2.get_strength() < ori_2.get_strength()
    
    def test_card_strength_same_suit(self):
        """Test that within same suit, higher value = higher strength."""
        card_1 = Card('Bastoni', 1)
        card_5 = Card('Bastoni', 5)
        card_10 = Card('Bastoni', 10)
        
        assert card_1.get_strength() < card_5.get_strength()
        assert card_5.get_strength() < card_10.get_strength()
    
    def test_jolly_identification(self):
        """Test that Asso di Ori is identified as Jolly."""
        jolly = Card('Ori', 1)
        not_jolly = Card('Bastoni', 1)
        
        assert jolly.is_jolly is True
        assert not_jolly.is_jolly is False
    
    def test_jolly_prende(self):
        """Test Jolly with 'prende' is strongest."""
        jolly = Card('Ori', 1)
        jolly.jolly_choice = 'prende'
        
        re_ori = Card('Ori', 10)
        
        assert jolly.get_strength() == 50
        assert jolly.get_strength() > re_ori.get_strength()
    
    def test_jolly_lascia(self):
        """Test Jolly with 'lascia' is weakest."""
        jolly = Card('Ori', 1)
        jolly.jolly_choice = 'lascia'
        
        asso_bastoni = Card('Bastoni', 1)
        
        assert jolly.get_strength() == -1
        assert jolly.get_strength() < asso_bastoni.get_strength()
    
    def test_jolly_choice_only_on_jolly(self):
        """Test that jolly_choice can only be set on Jolly."""
        not_jolly = Card('Bastoni', 1)
        
        with pytest.raises(ValueError):
            not_jolly.jolly_choice = 'prende'
    
    def test_invalid_jolly_choice(self):
        """Test that invalid jolly choice raises error."""
        jolly = Card('Ori', 1)
        
        with pytest.raises(ValueError):
            jolly.jolly_choice = 'invalid'
    
    def test_image_path(self):
        """Test image path generation."""
        card = Card('Bastoni', 5)
        assert card.image_path() == 'carte_napoletane/Bastoni/Bastoni_5.jpg'
    
    def test_card_serialization(self):
        """Test card to_dict and from_dict."""
        card = Card('Coppe', 7)
        data = card.to_dict()
        
        assert data['suit'] == 'Coppe'
        assert data['value'] == 7
        assert 'display_name' in data
        assert 'image_path' in data
        
        # Recreate card
        card2 = Card.from_dict(data)
        assert card == card2
    
    def test_card_equality(self):
        """Test card equality comparison."""
        card1 = Card('Spade', 3)
        card2 = Card('Spade', 3)
        card3 = Card('Spade', 4)
        
        assert card1 == card2
        assert card1 != card3
    
    def test_card_hash(self):
        """Test card can be used in sets/dicts."""
        card1 = Card('Spade', 3)
        card2 = Card('Spade', 3)
        
        card_set = {card1, card2}
        assert len(card_set) == 1
    
    def test_all_suits(self):
        """Test all suits are valid."""
        for suit in Card.SUITS:
            card = Card(suit, 5)
            assert card.suit == suit
    
    def test_all_values(self):
        """Test all values 1-10 are valid."""
        for value in range(1, 11):
            card = Card('Bastoni', value)
            assert card.value == value
    
    def test_display_names(self):
        """Test display names for special cards."""
        assert Card('Bastoni', 1).display_name == 'Asso di Bastoni'
        assert Card('Spade', 8).display_name == 'Fante di Spade'
        assert Card('Coppe', 9).display_name == 'Cavallo di Coppe'
        assert Card('Ori', 10).display_name == 'Re di Ori'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
