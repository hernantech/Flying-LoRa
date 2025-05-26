from flask import Flask, jsonify, request

app = Flask(__name__)

# Global variable to store current operation mode
current_mode = 1  # Default to mode 1

@app.route('/mode', methods=['GET'])
def get_mode():
    """Get the current operation mode"""
    return jsonify({'mode': current_mode})

@app.route('/mode', methods=['POST'])
def set_mode():
    """Set the operation mode"""
    global current_mode
    data = request.get_json()
    
    if 'mode' not in data:
        return jsonify({'error': 'Mode not specified'}), 400
    
    new_mode = data['mode']
    
    # Validate mode
    if new_mode not in [1, 2, 3]:
        return jsonify({'error': 'Invalid mode. Must be 1, 2, or 3'}), 400
    
    current_mode = new_mode
    return jsonify({'mode': current_mode})

@app.route('/status', methods=['GET'])
def get_status():
    """Get the server status and current mode"""
    return jsonify({
        'status': 'running',
        'mode': current_mode
    })

if __name__ == '__main__':
    # Run the server on all available network interfaces
    app.run(host='0.0.0.0', port=8080, debug=True) 