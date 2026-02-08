"""
Chat Socket.IO events.
"""
from flask import request
from flask_socketio import emit
import html

from rooms.room_manager import room_manager
from sockets.utils import verify_player_socket


def register_chat_events(socketio):
    """Register all chat-related socket events."""
    
    @socketio.on('send_message')
    def handle_send_message(data):
        """
        Send a chat message.
        Data: { player_id, message }
        """
        player_id = data.get('player_id')
        message = data.get('message', '').strip()
        
        if not player_id or not message:
            return

        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        # Sanitize message to prevent XSS
        sanitized_message = html.escape(message)
        
        success, msg_dict = room_manager.add_chat_message(
            room.room_id, player_id, sanitized_message
        )
        
        if success:
            # Broadcast to all players in the room (including sender)
            emit('chat_message', msg_dict, room=room.room_id, broadcast=True)
    
    @socketio.on('get_chat_history')
    def handle_get_chat_history(data):
        """
        Get chat history for a room.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            return

        if not verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        emit('chat_history', {'messages': room.chat_messages})
