from flask import Flask, send_from_directory, jsonify
import threading
import os
import time

app = Flask(__name__)

class MockHTTPServer:
    def __init__(self, host='127.0.0.1', port=8000, directory=None):
        self.host = host
        self.port = port
        self.directory = directory or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        self.url = f'http://{host}:{port}'
        self.server_thread = None
        
        # Ensure the directory exists
        if not os.path.exists(self.directory):
            os.makedirs(self.directory, exist_ok=True)
            print(f"Mock HTTP Server: Created directory {self.directory}")
        
        # List files in the directory
        files = os.listdir(self.directory)
        print(f"Mock HTTP Server: Files in directory: {files}")
        
        # Set the directory for the Flask app
        app.config['MOCK_HTTP_SERVER_DIR'] = self.directory
        
        # Define routes
        @app.route('/')
        def home():
            return jsonify({"status": "ok", "files": os.listdir(app.config['MOCK_HTTP_SERVER_DIR'])})
        
        @app.route('/<path:filename>')
        def serve_file(filename):
            print(f"Mock HTTP Server: Serving file: {filename}")
            try:
                return send_from_directory(app.config['MOCK_HTTP_SERVER_DIR'], filename)
            except Exception as e:
                print(f"Mock HTTP Server ERROR: {str(e)}")
                return jsonify({"error": f"File not found: {filename}"}), 404
    
    def start(self):
        """Start the HTTP server in a background thread."""
        def run_server():
            app.run(host=self.host, port=self.port, use_reloader=False)
        
        self.server_thread = threading.Thread(target=run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Give it a moment to start
        time.sleep(0.5)
        print(f"Mock HTTP server started at {self.url}")
        print(f"Serving files from: {self.directory}")
    
    def shutdown(self):
        """Shut down the HTTP server."""
        # There's no clean way to shut down a Flask app in a thread,
        # so we'll rely on the daemon thread to be killed when the program exits
        print(f"Mock HTTP server at {self.url} has been shut down")

if __name__ == '__main__':
    server = MockHTTPServer()
    server.start()
    
    try:
        # Keep the server running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown() 