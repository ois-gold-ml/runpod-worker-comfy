import unittest
from unittest.mock import patch, MagicMock, mock_open, Mock
import sys
import os
import json
import requests
import uuid

# Mock modules before importing rp_handler
sys.modules['runpod'] = MagicMock()
sys.modules['runpod.serverless'] = MagicMock()
sys.modules['runpod.serverless.utils'] = MagicMock()
sys.modules['runpod.serverless.utils.rp_upload'] = MagicMock()
sys.modules['tusclient'] = MagicMock()
sys.modules['tusclient.client'] = MagicMock()

# Make sure that "src" is known and can be used to import rp_handler.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from src import rp_handler

# Local folder for test resources
RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES = "./test_resources/images"


class TestRunpodWorkerComfy(unittest.TestCase):
    def test_valid_input_with_workflow_only(self):
        input_data = {"input": "https://example.com/image.png", "output": "https://example.com/output"}
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, {"input": "https://example.com/image.png", "output": "https://example.com/output"})

    def test_valid_input_with_workflow_and_input_url(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output",
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, input_data)

    def test_input_missing_workflow(self):
        input_data = {"input": "https://example.com/image.png"}
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'output' must be a string containing a presigned URL")

    def test_input_with_invalid_input_url_type(self):
        input_data = {
            "input": 123,  # Not a string
            "output": "https://example.com/output",
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'input' must be a string containing an image URL")

    def test_invalid_json_string_input(self):
        input_data = "invalid json"
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Invalid JSON format in input")

    def test_valid_json_string_input(self):
        input_data = '{"input": "https://example.com/image.png", "output": "https://example.com/output"}'
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, {"input": "https://example.com/image.png", "output": "https://example.com/output"})

    def test_empty_input(self):
        input_data = None
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Please provide input")

    @patch("rp_handler.requests.get")
    def test_check_server_server_up(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.return_value = mock_response

        result = rp_handler.check_server("http://127.0.0.1:8188", 1, 50)
        self.assertTrue(result)

    @patch("rp_handler.requests.get")
    def test_check_server_server_down(self, mock_requests):
        mock_requests.side_effect = rp_handler.requests.RequestException()
        result = rp_handler.check_server("http://127.0.0.1:8188", 1, 50)
        self.assertFalse(result)

    @patch("rp_handler.urllib.request.urlopen")
    def test_queue_prompt(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"prompt_id": "123"}).encode()
        mock_urlopen.return_value = mock_response
        result = rp_handler.queue_workflow({"prompt": "test"})
        self.assertEqual(result, {"prompt_id": "123"})

    @patch("rp_handler.urllib.request.urlopen")
    def test_get_history(self, mock_urlopen):
        # Mock response data as a JSON string
        mock_response_data = json.dumps({"key": "value"}).encode("utf-8")

        # Define a mock response function for `read`
        def mock_read():
            return mock_response_data

        # Create a mock response object
        mock_response = Mock()
        mock_response.read = mock_read

        # Mock the __enter__ and __exit__ methods to support the context manager
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = Mock()

        # Set the return value of the urlopen mock
        mock_urlopen.return_value = mock_response

        # Call the function under test
        result = rp_handler.get_history("123")

        # Assertions
        self.assertEqual(result, {"key": "value"})
        mock_urlopen.assert_called_with("http://127.0.0.1:8188/history/123")

    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.tus_client.TusClient")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_with_upload_url_parameter(self, mock_tus_client, mock_exists):
        """Test that process_output_images correctly uses the upload_url parameter."""
        # Mock file exists
        mock_exists.return_value = True
        
        # Mock TUS client uploader
        mock_uploader = MagicMock()
        mock_uploader.url = "http://example.com/tus/uploaded_file"
        mock_tus_client.return_value.uploader.return_value = mock_uploader
        
        # Test data
        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "test_job"
        upload_url = "http://example.com/tus" 
        
        # Call the function directly
        result = rp_handler.process_output_images(outputs, job_id, upload_url)
        
        # Verify TUS client was created with the correct upload_url
        mock_tus_client.assert_called_once_with(upload_url)
        
        # Verify uploader was created and upload was called
        uploader_path = f"{RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}/ComfyUI_00001_.png"
        mock_tus_client.return_value.uploader.assert_called_once_with(
            uploader_path, chunk_size=5*1024*1024
        )
        mock_uploader.upload.assert_called_once()
        
        # Verify the result contains the expected values
        self.assertEqual(result["status"], "success")

    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.tus_client.TusClient")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_upload_fails(self, mock_tus_client, mock_exists):
        # Mock the file existing
        mock_exists.return_value = True
        
        # Mock TUS client with upload exception
        mock_tus_client.return_value.uploader.side_effect = Exception("Upload failed")
        
        # Test data
        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "test_job"
        upload_url = "http://example.com/tus"
        
        # Call the function under test
        result = rp_handler.process_output_images(outputs, job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertIn("Error uploading image ComfyUI_00001_.png using TUS protocol", result["message"])

    @patch("rp_handler.os.path.exists")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_no_upload_url(self, mock_exists):
        # Test data
        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "test_job"
        upload_url = None
        
        # Call the function under test
        result = rp_handler.process_output_images(outputs, job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "No upload URL provided in the job output property")

    @patch("rp_handler.os.path.exists")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_file_not_exists(self, mock_exists):
        # Mock the file not existing
        mock_exists.return_value = False
        
        # Test data
        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "test_job" 
        upload_url = "http://example.com/tus"
        
        # Call the function under test
        result = rp_handler.process_output_images(outputs, job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "No images were successfully uploaded")
    
    def test_handler_without_upload_url(self):
        # Setup mock to pass validation but with error about missing output
        
        # Create job without upload_url
        job = {
            "id": "test_job",
            "input": {"input": "https://example.com/image.png"}
            # No output property
        }
        
        # Call the handler
        result = rp_handler.handler(job)
        
        # Assertions
        self.assertIn("error", result)
        self.assertEqual(result["error"], "'output' must be a string containing a presigned URL")
        
    @patch("rp_handler.requests.get")
    def test_download_image_successful(self, mock_get):
        # Create a mock response for the GET request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Test Image Data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Test URL with a valid filename
        url = "https://example.com/images/test_image.png"
        success, result = rp_handler.download_image(url)

        # Assertions
        self.assertTrue(success)
        self.assertEqual(result[0], "test_image.png")  # Filename
        self.assertEqual(result[1], b"Test Image Data")  # Image data
        mock_get.assert_called_with(url, stream=True)

    @patch("rp_handler.requests.get")
    def test_download_image_with_invalid_url(self, mock_get):
        # Mock a failed request
        mock_get.side_effect = requests.RequestException("Failed to download")

        url = "https://example.com/invalid_image.png"
        success, error_message = rp_handler.download_image(url)

        # Assertions
        self.assertFalse(success)
        self.assertIn("Error downloading image", error_message)
        mock_get.assert_called_with(url, stream=True)

    @patch("rp_handler.requests.get")
    def test_download_image_with_url_no_filename(self, mock_get):
        # Create a mock response for the GET request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Test Image Data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Test URL without a filename
        url = "https://example.com/images/"
        success, result = rp_handler.download_image(url)

        # Assertions
        self.assertTrue(success)
        self.assertEqual(result[0], "downloaded_image.png")  # Default filename
        self.assertEqual(result[1], b"Test Image Data")  # Image data

    @patch("rp_handler.requests.post")
    @patch("rp_handler.uuid.uuid4")
    def test_upload_image_to_comfy_successful(self, mock_uuid, mock_post):
        # Mock UUID generation for consistent testing
        mock_uuid.return_value = "test-uuid"
        
        # Create a mock response for the POST request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Test data
        image_data = ("test_image.png", b"Test Image Data")
        result = rp_handler.upload_image_to_comfy(image_data)

        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertIn("Successfully uploaded", result["message"])
        self.assertEqual(result["filename"], "test-uuid.png")
        mock_post.assert_called_once()

    @patch("rp_handler.requests.post")
    def test_upload_image_to_comfy_failed(self, mock_post):
        # Mock a failed request
        mock_post.side_effect = requests.RequestException("Failed to upload")

        # Test data
        image_data = ("test_image.png", b"Test Image Data")
        result = rp_handler.upload_image_to_comfy(image_data)

        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertIn("Error uploading", result["message"])
        mock_post.assert_called_once()

    @patch("rp_handler.requests.post")
    def test_upload_image_to_comfy_no_data(self, mock_post):
        # Test with no image data
        result = rp_handler.upload_image_to_comfy(None)

        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "No image data provided")
