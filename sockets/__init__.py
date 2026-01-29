# Sockets module
from .lobby_events import register_lobby_events
from .game_events import register_game_events
from .chat_events import register_chat_events

__all__ = ['register_lobby_events', 'register_game_events', 'register_chat_events']
