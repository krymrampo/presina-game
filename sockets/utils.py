"""
Shared socket utilities for Presina.
"""
from rooms.room_manager import room_manager


def verify_player_socket(player_id: str, sid: str) -> bool:
    """
    Verify that the player_id is associated with the given socket SID.
    This prevents players from impersonating others.
    """
    registered_player = room_manager.get_player_by_sid(sid)
    return registered_player == player_id


def ensure_player_socket(player_id: str, sid: str) -> bool:
    """
    Ensure this socket is associated with the player_id.
    If the socket isn't registered yet, register it.
    """
    registered_player = room_manager.get_player_by_sid(sid)
    if registered_player is None:
        room_manager.register_socket(sid, player_id)
        return True
    return registered_player == player_id
