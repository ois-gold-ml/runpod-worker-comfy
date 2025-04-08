import unittest
import os
import sys
import json
import time
import requests
import subprocess
import tempfile
import shutil
import hashlib
import logging
from tusclient import client as tus_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Integration-Test")

# Add the project root to path to make imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Import local servers
from mock_tus_server import TusServer
from mock_http_server import MockHTTPServer

# Mock function for downloading images
# We need this because the mock HTTP server doesn't really serve the files properly
def mock_download_image(url):
    logger.info(f"Mock download_image called with URL: {url}")
    # Always return success with a dummy image
    return True, ("dummy_image.png", b"dummy image content")

class IntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once before all tests."""
        # Create output directory where ComfyUI would save images
        cls.output_dir = os.path.join(tempfile.gettempdir(), 'comfyui_output')
        os.makedirs(cls.output_dir, exist_ok=True)
        
        # Set environment variable for output path
        os.environ['COMFY_OUTPUT_PATH'] = cls.output_dir
        
        # Set ComfyUI host to our mock server
        os.environ['COMFY_HOST'] = '127.0.0.1:8188'
        
        # Start mock ComfyUI server
        cls.comfy_process = subprocess.Popen(
            [sys.executable, os.path.join(os.path.dirname(__file__), 'mock_comfyui.py')],
            env=os.environ.copy()
        )
        
        # Start mock HTTP server for input images
        cls.http_server = MockHTTPServer()
        cls.http_server.start()
        
        # Start TUS server for output uploads
        cls.tus_server = TusServer()
        cls.tus_server.start()
        
        # Wait for services to start
        time.sleep(2)
        
        # Check if ComfyUI server is running
        retries = 10
        while retries > 0:
            try:
                response = requests.get('http://127.0.0.1:8188/')
                if response.status_code == 200:
                    break
            except:
                pass
            time.sleep(1)
            retries -= 1
        
        if retries == 0:
            raise RuntimeError("Mock ComfyUI server did not start properly")
        
        # Create test output image in ComfyUI output directory
        logger.info("Creating test output file in ComfyUI output directory")
        cls.test_image_content = b'This is a test image content for verification'
        cls.test_image_path = os.path.join(cls.output_dir, 'test_output.png')
        with open(cls.test_image_path, 'wb') as f:
            f.write(cls.test_image_content)
            
        # Create test input files in the data directory
        data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
        os.makedirs(data_dir, exist_ok=True)
        input_path = os.path.join(data_dir, 'input.jpeg')
        output_path = os.path.join(data_dir, 'output.png')
        
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests are done."""
        # Stop servers
        if hasattr(cls, 'comfy_process'):
            cls.comfy_process.terminate()
            cls.comfy_process.wait()
        
        if hasattr(cls, 'http_server'):
            cls.http_server.shutdown()
        
        if hasattr(cls, 'tus_server'):
            cls.tus_server.shutdown()
        
        # Clean up temporary directories
        if hasattr(cls, 'output_dir') and os.path.exists(cls.output_dir):
            shutil.rmtree(cls.output_dir, ignore_errors=True)
    
    def test_handler_happy_path(self):
        """Test the full workflow with an input image."""
        from src.rp_handler import handler
        
        # Patch the download_image function for this test
        from src.rp_handler import download_image
        # Store the original function
        original_download_image = download_image
        # Replace with our mock
        import src.rp_handler
        src.rp_handler.download_image = mock_download_image
        
        try:
            # Create a test workflow
            workflow = {
                "3": {
                    "inputs": {
                        "prompt": "test prompt",
                        "seed": 42
                    },
                    "class_type": "KSampler"
                },
                "4": {
                    "inputs": {
                        "images": ["3"]
                    },
                    "class_type": "SaveImage"
                }
            }
            
            logger.info(f"TUS server URL: {self.tus_server.url}")
            # Job with input image and upload URL
            job = {
                "id": "test-job-with-input",
                "input": {
                    "workflow": workflow,
                    "input": f"{self.http_server.url}/input.jpeg"
                },
                "output": self.tus_server.url
            }
            
            # Run the handler
            result = handler(job)
            
            # Print the actual result for debugging
            logger.info(f"Test with input image result: {result}")
            
            # Verify the result
            self.assertNotIn('error', result, f"Handler failed: {result.get('error', 'Unknown error')}")
            self.assertIn('status', result, f"Result doesn't have a status key: {result}")
            self.assertEqual(result['status'], 'success', f"Handler status is not success: {result}")
            
            # Verify that exactly 3 files were uploaded to the TUS server
            uploads = self.tus_server.get_uploads()
            self.assertEqual(len(uploads), 3, f"Expected 3 uploads, got {len(uploads)}")
            
            # Verify all uploads are complete and content matches
            for i, (upload_id, upload_data) in enumerate(uploads.items(), 1):
                self.assertEqual(upload_data['offset'], upload_data['size'], 
                                f"Upload {upload_id} is not complete: {upload_data['offset']}/{upload_data['size']}")
                
                # Verify the file exists
                self.assertTrue(os.path.exists(upload_data['path']), 
                               f"Uploaded file doesn't exist at {upload_data['path']}")
                
                # Verify the file content matches what we generated
                with open(upload_data['path'], 'rb') as f:
                    content = f.read()
                    expected_content = f'Result image {i}'.encode()
                    self.assertEqual(content, expected_content, 
                                   f"Content of image {i} doesn't match expected content")
                    
                # Verify the file size
                self.assertEqual(os.path.getsize(upload_data['path']), len(expected_content),
                                f"Uploaded file size doesn't match: {os.path.getsize(upload_data['path'])} != {len(expected_content)}")
                
        finally:
            # Restore the original function
            src.rp_handler.download_image = original_download_image

if __name__ == '__main__':
    unittest.main() 