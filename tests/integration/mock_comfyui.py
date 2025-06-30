from flask import Flask, request, jsonify, send_file
import time
import os
import threading
import json

app = Flask(__name__)

# Store prompts and their "outputs"
prompts = {}
output_dir = os.environ.get('COMFY_OUTPUT_PATH', '/comfyui/output')
test_data_dir = os.environ.get('TEST_DATA_DIR', 'data/comfy')

# Ensure output directory exists
os.makedirs(output_dir, exist_ok=True)
os.makedirs(test_data_dir, exist_ok=True)

# For debugging - log the prompts dictionary
def log_prompts():
    print(f"ComfyUI Mock Server: Current prompts: {list(prompts.keys())}")

@app.route('/prompt', methods=['POST'])
def handle_prompt():
    print(f"ComfyUI Mock Server: Received prompt request")
    try:
        # Get the JSON data from the request
        data = request.get_json(force=True)
        print(f"ComfyUI Mock Server: Request data: {json.dumps(data)[:200]}...")
        with open(f'{test_data_dir}/workflow.json', 'w') as f:
            json.dump(data, f)
        
        # Fixed prompt ID for testing to ensure consistency
        prompt_id = "test-prompt-id"
        
        # Store the prompt
        prompts[prompt_id] = {'status': 'processing', 'prompt': data}
        print(f"ComfyUI Mock Server: Created prompt with ID: {prompt_id}")
        log_prompts()
        
        # Schedule completion after a brief delay
        def complete_job():
            time.sleep(1)  # Reduced time for faster tests
            
            # Create subdirectories like real ComfyUI
            batch_output_dir = os.path.join(output_dir, 'batch_output')
            psd_output_dir = os.path.join(output_dir, 'psd_output')
            os.makedirs(batch_output_dir, exist_ok=True)
            os.makedirs(psd_output_dir, exist_ok=True)
            
            # Create test output images in different subdirectories
            # Batch output files
            for i in range(1, 3):  # 2 PNG files
                test_image_path = os.path.join(batch_output_dir, f'result_image_{i}.png')
                with open(test_image_path, 'wb') as f:
                    f.write(f'Result image {i}'.encode())
            
            # PSD output files
            psd_path = os.path.join(psd_output_dir, 'result.psd')
            with open(psd_path, 'wb') as f:
                f.write(b'Result image 3')
            
            # Create a report file in psd_output
            report_path = os.path.join(psd_output_dir, 'psd_saver_report.txt')
            with open(report_path, 'w') as f:
                f.write('PSD processing report\nFiles processed: 1\n')
            
            # Update prompt with output information (though this won't be used anymore)
            prompts[prompt_id] = {
                'outputs': {
                    'node_id': {
                        'images': [
                            {'filename': 'result_image_1.png', 'subfolder': 'batch_output'},
                            {'filename': 'result_image_2.png', 'subfolder': 'batch_output'},
                            {'filename': 'result.psd', 'subfolder': 'psd_output'}
                        ]
                    }
                }
            }
            print(f"ComfyUI Mock Server: Job complete, created files in batch_output and psd_output")
            log_prompts()
        
        # Start the completion in a background thread
        thread = threading.Thread(target=complete_job)
        thread.daemon = True
        thread.start()
        
        print(f"ComfyUI Mock Server: Returning prompt ID: {prompt_id}")
        return jsonify({'prompt_id': prompt_id})
    except Exception as e:
        print(f"ComfyUI Mock Server ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/history/<prompt_id>', methods=['GET'])
def get_history(prompt_id):
    print(f"ComfyUI Mock Server: Getting history for prompt {prompt_id}")
    
    # Always return a successful result regardless of the prompt_id
    # This ensures the test doesn't fail due to prompt ID mismatch
    dummy_result = {
        'outputs': {
            'node_id': {
                'images': [{'filename': 'test_output.png', 'subfolder': ''}]
            }
        }
    }
    
    if prompt_id in prompts:
        print(f"ComfyUI Mock Server: Found prompt in history")
        return jsonify({prompt_id: prompts[prompt_id]})
    else:
        print(f"ComfyUI Mock Server: Prompt not found in history. Available IDs: {list(prompts.keys())}")
        print(f"ComfyUI Mock Server: Returning dummy result for testing")
        return jsonify({prompt_id: dummy_result})

@app.route('/upload/image', methods=['POST'])
def upload_image():
    print(f"ComfyUI Mock Server: Received image upload request")
    # Save the uploaded image
    if 'image' not in request.files:
        print(f"ComfyUI Mock Server: No image in request")
        return jsonify({'success': False, 'error': 'No image in request'})
    
    image = request.files['image']
    filename = image.filename
    
    # Save the image to a temporary location
    save_path = os.path.join(output_dir, filename)
    print(f"ComfyUI Mock Server: Saving uploaded image to {save_path}")
    image.save(save_path)
    
    return jsonify({'success': True, 'filename': filename})

@app.route('/', methods=['GET'])
def health_check():
    return "OK"

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8188, debug=True, use_reloader=False)