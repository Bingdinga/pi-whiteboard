# app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Create directories if they don't exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# Store active users and their cursors
active_rooms = {}  # {room_id: {user_id: {cursor_x, cursor_y, username, color}}}
drawing_history = {}  # {room_id: [drawing actions]}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/board/<room_id>')
def board(room_id):
    return render_template('whiteboard.html', room_id=room_id)

@app.route('/create-board', methods=['POST'])
def create_board():
    room_id = str(uuid.uuid4())[:8]  # Create a shorter unique ID
    active_rooms[room_id] = {}
    drawing_history[room_id] = []
    return jsonify({'room_id': room_id})

@socketio.on('join')
def on_join(data):
    room_id = data['room']
    user_id = data['userId']
    username = data.get('username', f'User_{user_id[:4]}')
    user_color = data.get('color', '#' + user_id[:6])
    
    join_room(room_id)
    
    if room_id not in active_rooms:
        active_rooms[room_id] = {}
        drawing_history[room_id] = []
    
    active_rooms[room_id][user_id] = {
        'cursor_x': 0,
        'cursor_y': 0,
        'username': username,
        'color': user_color
    }
    
    # Send current users to the new user
    emit('user_joined', {
        'userId': user_id,
        'username': username,
        'color': user_color,
        'activeUsers': active_rooms[room_id]
    }, to=room_id)
    
    # Send drawing history to new user
    if room_id in drawing_history:
        emit('drawing_history', drawing_history[room_id], to=request.sid)

@socketio.on('leave')
def on_leave(data):
    room_id = data['room']
    user_id = data['userId']
    
    leave_room(room_id)
    
    if room_id in active_rooms and user_id in active_rooms[room_id]:
        del active_rooms[room_id][user_id]
        emit('user_left', {'userId': user_id}, to=room_id)
        
        # Clean up empty rooms
        if len(active_rooms[room_id]) == 0:
            del active_rooms[room_id]
            if room_id in drawing_history:
                del drawing_history[room_id]

@socketio.on('cursor_move')
def on_cursor_move(data):
    room_id = data['room']
    user_id = data['userId']
    x = data['x']
    y = data['y']
    
    if room_id in active_rooms and user_id in active_rooms[room_id]:
        active_rooms[room_id][user_id]['cursor_x'] = x
        active_rooms[room_id][user_id]['cursor_y'] = y
        
        # Broadcast cursor position to all users in the room except sender
        emit('cursor_update', {
            'userId': user_id,
            'x': x,
            'y': y
        }, to=room_id, skip_sid=request.sid)

@socketio.on('draw')
def on_draw(data):
    room_id = data['room']
    
    # Save to drawing history
    if room_id in drawing_history:
        drawing_history[room_id].append(data)
    
    # Broadcast drawing action to all users in the room except sender
    emit('draw', data, to=room_id, skip_sid=request.sid)

@socketio.on('clear_canvas')
def on_clear_canvas(data):
    room_id = data['room']
    
    # Clear drawing history
    if room_id in drawing_history:
        drawing_history[room_id] = []
    
    # Broadcast clear canvas to all users in the room
    emit('clear_canvas', {}, to=room_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)