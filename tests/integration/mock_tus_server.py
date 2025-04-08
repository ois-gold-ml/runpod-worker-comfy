from flask import Flask, request, jsonify, send_file
import os
import threading
import uuid
import base64
import logging
import hashlib
import shutil

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TUS-Server")

# Store uploaded files
uploads = {}
upload_dir = 'uploads'
os.makedirs(upload_dir, exist_ok=True)

@app.route('/files', methods=['POST'])
def create_upload():
    """Create a new upload endpoint according to the tus protocol"""
    # Check for tus resumable header
    if request.headers.get('Tus-Resumable') != '1.0.0':
        logger.warning("Invalid or missing Tus-Resumable header")
        response = jsonify({'error': 'Tus-Resumable header must be 1.0.0'})
        response.status_code = 412
        return response
    
    upload_id = str(uuid.uuid4())
    upload_metadata = request.headers.get('Upload-Metadata', '')
    upload_length = request.headers.get('Upload-Length', '0')
    
    # Extract filename from metadata if available
    filename = f"file-{upload_id}"
    metadata_dict = {}
    if upload_metadata:
        for item in upload_metadata.split(','):
            if item.strip():
                try:
                    key, value = item.split(' ', 1)
                    metadata_dict[key] = base64.b64decode(value).decode('utf-8')
                    if key == 'filename':
                        filename = metadata_dict[key]
                except Exception as e:
                    logger.warning(f"Error parsing metadata item {item}: {str(e)}")
    
    # Create a unique filename to prevent collisions
    file_extension = os.path.splitext(filename)[1] if '.' in filename else ''
    unique_filename = f"{os.path.splitext(filename)[0]}-{upload_id}{file_extension}"
    upload_path = os.path.join(upload_dir, unique_filename)
    
    # Create an empty file to start with
    with open(upload_path, 'wb') as f:
        pass  # Just create an empty file
    
    uploads[upload_id] = {
        'id': upload_id,
        'path': upload_path,
        'size': int(upload_length),
        'offset': 0,
        'filename': unique_filename,
        'original_filename': filename,
        'metadata': metadata_dict
    }
    
    logger.info(f"Created upload: {upload_id} for file: {filename}")
    
    # According to tus protocol
    response = jsonify({})
    response.headers['Location'] = f'/files/{upload_id}'
    response.headers['Tus-Resumable'] = '1.0.0'
    response.status_code = 201
    return response

@app.route('/files/<upload_id>', methods=['PATCH'])
def upload_chunk(upload_id):
    """Handle chunk upload"""
    # Check for tus resumable header
    if request.headers.get('Tus-Resumable') != '1.0.0':
        logger.warning("Invalid or missing Tus-Resumable header in PATCH request")
        response = jsonify({'error': 'Tus-Resumable header must be 1.0.0'})
        response.status_code = 412
        return response
    
    if upload_id not in uploads:
        logger.warning(f"Upload ID not found: {upload_id}")
        return '', 404
    
    upload = uploads[upload_id]
    offset = int(request.headers.get('Upload-Offset', '0'))
    
    # Verify offset matches our records
    if offset != upload['offset']:
        logger.warning(f"Offset mismatch: got {offset}, expected {upload['offset']}")
        response = jsonify({'error': 'Offset conflict'})
        response.status_code = 409
        return response
    
    content_length = int(request.headers.get('Content-Length', '0'))
    chunk = request.data
    
    # Check if content length matches actual data length
    if len(chunk) != content_length:
        logger.warning(f"Content-Length mismatch: {content_length} vs {len(chunk)}")
        response = jsonify({'error': 'Content-Length mismatch'})
        response.status_code = 400
        return response
    
    # Append data to file
    with open(upload['path'], 'ab') as f:
        f.write(chunk)
    
    # Update offset
    upload['offset'] += len(chunk)
    logger.info(f"Updated {upload_id}: received {len(chunk)} bytes, new offset {upload['offset']}")
    
    # Check if upload is complete
    if upload['offset'] == upload['size']:
        logger.info(f"Upload complete for {upload_id} ({upload['original_filename']})")
        
        # Verify file size
        file_size = os.path.getsize(upload['path'])
        if file_size != upload['size']:
            logger.warning(f"File size mismatch: {file_size} vs {upload['size']}")
    
    # Return the new offset
    response = jsonify({})
    response.headers['Upload-Offset'] = str(upload['offset'])
    response.headers['Tus-Resumable'] = '1.0.0'
    response.status_code = 204
    return response

@app.route('/files/<upload_id>', methods=['HEAD'])
def get_upload_status(upload_id):
    """Get the status of an upload"""
    # Check for tus resumable header
    if request.headers.get('Tus-Resumable') != '1.0.0':
        logger.warning("Invalid or missing Tus-Resumable header in HEAD request")
        response = jsonify({'error': 'Tus-Resumable header must be 1.0.0'})
        response.status_code = 412
        return response
    
    if upload_id not in uploads:
        logger.warning(f"Upload ID not found in HEAD request: {upload_id}")
        return '', 404
    
    upload = uploads[upload_id]
    
    response = jsonify({})
    response.headers['Upload-Offset'] = str(upload['offset'])
    response.headers['Upload-Length'] = str(upload['size'])
    response.headers['Tus-Resumable'] = '1.0.0'
    response.status_code = 200
    
    # Add custom header with the original filename for client information
    response.headers['Upload-Metadata'] = f"filename {base64.b64encode(upload['original_filename'].encode()).decode()}"
    
    return response

@app.route('/files/<upload_id>', methods=['GET'])
def download_file(upload_id):
    """Allow downloading the file for verification purposes"""
    if upload_id not in uploads:
        logger.warning(f"Upload ID not found in GET request: {upload_id}")
        return jsonify({"error": "File not found"}), 404
    
    upload = uploads[upload_id]
    
    # Check if the upload is complete
    if upload['offset'] != upload['size']:
        return jsonify({"error": "Upload not complete"}), 400
    
    return send_file(upload['path'], 
                     as_attachment=True,
                     download_name=upload['original_filename'])

@app.route('/files', methods=['GET'])
def list_uploads():
    """List all uploads - not part of TUS protocol but useful for testing"""
    upload_list = []
    for upload_id, data in uploads.items():
        upload_list.append({
            'id': upload_id,
            'filename': data['original_filename'],
            'size': data['size'],
            'offset': data['offset'],
            'complete': data['offset'] == data['size']
        })
    
    return jsonify(upload_list)

def run_server(host='127.0.0.1', port=1080):
    app.run(host=host, port=port, use_reloader=False)

class TusServer:
    def __init__(self, host='127.0.0.1', port=1080):
        self.host = host
        self.port = port
        self.url = f'http://{host}:{port}/files'
        self.server_thread = None
        
        # Clean up the uploads directory before starting
        if os.path.exists(upload_dir):
            for filename in os.listdir(upload_dir):
                file_path = os.path.join(upload_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error cleaning up file {file_path}: {str(e)}")
    
    def start(self):
        self.server_thread = threading.Thread(target=run_server, args=(self.host, self.port))
        self.server_thread.daemon = True
        self.server_thread.start()
        logger.info(f"TUS server started at {self.url}")
    
    def shutdown(self):
        # No clean way to shut down a Flask app in a thread
        # We'll rely on the daemon thread to be killed when the program exits
        logger.info(f"TUS server at {self.url} shutting down")
    
    def get_uploads(self):
        """Return the current uploads dictionary for verification"""
        return uploads
        
    def get_upload_path(self, upload_id):
        """Get the path to an uploaded file by ID"""
        if upload_id in uploads:
            return uploads[upload_id]['path']
        return None
    
    def verify_upload(self, upload_id, expected_content=None):
        """Verify that an upload is complete and matches expected content if provided"""
        if upload_id not in uploads:
            return False, "Upload ID not found"
        
        upload = uploads[upload_id]
        
        # Check if upload is complete
        if upload['offset'] != upload['size']:
            return False, f"Upload not complete: {upload['offset']}/{upload['size']} bytes"
        
        # Verify file exists
        if not os.path.exists(upload['path']):
            return False, f"File not found at {upload['path']}"
        
        # Verify file size
        file_size = os.path.getsize(upload['path'])
        if file_size != upload['size']:
            return False, f"File size mismatch: {file_size} vs {upload['size']}"
        
        # Verify content if provided
        if expected_content is not None:
            with open(upload['path'], 'rb') as f:
                content = f.read()
                
            if content != expected_content:
                # For debugging, calculate hashes
                expected_hash = hashlib.md5(expected_content).hexdigest()
                actual_hash = hashlib.md5(content).hexdigest()
                return False, f"Content mismatch: expected MD5 {expected_hash}, got {actual_hash}"
        
        return True, "Upload verified successfully"

if __name__ == '__main__':
    server = TusServer()
    server.start()
    
    try:
        # Keep the server running until interrupted
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown() 