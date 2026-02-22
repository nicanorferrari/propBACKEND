import socketio
import logging

logger = logging.getLogger("urbanocrm.socket")

sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# user_id -> set of sids
connected_users = {}

@sio.on('connect')
async def connect(sid, environ, auth):
    logger.info(f"Socket connection attempt: {sid}")
    
    # We expect the frontend to pass token or user info in auth
    # For now, let's just accept the connection
    # Front-end `auth: { token }` payload:
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get('token')
        
    # In a real scenario, we decode the JWT token to get the user ID
    # For simplicity, if we pass user_id explicitly or decode token:
    user_id = "1" # Replace with real token decoding logic if needed
    
    if user_id not in connected_users:
        connected_users[user_id] = set()
        
    connected_users[user_id].add(sid)
    
    async with sio.session(sid) as session:
        session['user_id'] = user_id
        
    logger.info(f"Client connected: {sid} (User: {user_id})")

@sio.on('disconnect')
async def disconnect(sid):
    try:
        async with sio.session(sid) as session:
            user_id = session.get('user_id')
            if user_id and user_id in connected_users:
                connected_users[user_id].discard(sid)
                if not connected_users[user_id]:
                    del connected_users[user_id]
                logger.info(f"Client disconnected: {sid} (User: {user_id})")
            else:
                logger.info(f"Client disconnected: {sid}")
    except Exception as e:
        logger.error(f"Error on disconnect: {e}")

async def send_notification(user_id, notification_data):
    """
    Send a real-time notification to a specific user.
    notification_data should be a dict matching the frontend NotificationItem interface.
    """
    user_id_str = str(user_id)
    if user_id_str in connected_users:
        for sid in connected_users[user_id_str]:
            await sio.emit('notification', notification_data, to=sid)
        logger.info(f"Notification sent to user {user_id_str}")
    else:
        logger.info(f"User {user_id_str} not connected. Notification will be available via polling.")
