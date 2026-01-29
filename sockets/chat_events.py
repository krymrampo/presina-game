"""
Chat Socket.IO events.
"""
from flask import request
from flask_socketio import emit

from rooms.room_manager import room_manager


def _verify_player_socket(player_id: str, sid: str) -> bool:
    """Verify player_id matches socket SID."""
    registered_player = room_manager.get_player_by_sid(sid)
    return registered_player == player_id


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

        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        success, msg_dict = room_manager.add_chat_message(
            room.room_id, player_id, message
        )
        
        if success:
            emit('chat_message', msg_dict, room=room.room_id)
    
    @socketio.on('get_chat_history')
    def handle_get_chat_history(data):
        """
        Get chat history for a room.
        Data: { player_id }
        """
        player_id = data.get('player_id')
        
        if not player_id:
            return

        if not _verify_player_socket(player_id, request.sid):
            emit('error', {'message': 'Sessione non valida, ricarica la pagina'})
            return
        
        room = room_manager.get_player_room(player_id)
        if not room:
            return
        
        emit('chat_history', {'messages': room.chat_messages})
