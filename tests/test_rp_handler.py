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
        input_data = {
            "input": "https://example.com/image.png", 
            "output": "https://example.com/output",
            "params": {"tiling": 2, "denoise": "0.4"}
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, input_data)

    def test_valid_input_with_workflow_and_input_url(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output",
            "params": {"tiling": 3, "denoise": "0.6"}
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
            "params": {"tiling": 2, "denoise": "0.4"}
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
        input_data = '{"input": "https://example.com/image.png", "output": "https://example.com/output", "params": {"tiling": 2, "denoise": "0.4"}}'
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, {"input": "https://example.com/image.png", "output": "https://example.com/output", "params": {"tiling": 2, "denoise": "0.4"}})

    def test_empty_input(self):
        input_data = None
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Please provide input")

    def test_get_mime_type_known_extensions(self):
        """Test MIME type detection for known file extensions."""
        test_cases = [
            ("test.png", "image/png"),
            ("test.jpg", "image/jpeg"),
            ("test.jpeg", "image/jpeg"),
            ("test.gif", "image/gif"),
            ("test.txt", "text/plain"),
            ("test.pdf", "application/pdf"),
            ("test.mp4", "video/mp4"),
            ("test.webp", "image/webp")
        ]
        
        for filename, expected_mime in test_cases:
            with self.subTest(filename=filename):
                result = rp_handler.get_mime_type(filename)
                self.assertEqual(result, expected_mime)

    def test_get_mime_type_unknown_extension(self):
        """Test MIME type detection for unknown file extensions."""
        result = rp_handler.get_mime_type("test.unknownext")
        self.assertEqual(result, "application/octet-stream")

    def test_get_mime_type_no_extension(self):
        """Test MIME type detection for files without extensions."""
        result = rp_handler.get_mime_type("filename_no_ext")
        self.assertEqual(result, "application/octet-stream")

    def test_get_mime_type_psd_file(self):
        """Test MIME type detection for PSD files specifically."""
        result = rp_handler.get_mime_type("artwork.psd")
        # PSD files might be detected as image/vnd.adobe.photoshop or fall back to application/octet-stream
        self.assertIn(result, ["image/vnd.adobe.photoshop", "application/octet-stream"])

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

    @patch("rp_handler.os.walk")
    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.os.path.getsize")
    @patch("rp_handler.os.remove")
    @patch("rp_handler.get_mime_type")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_with_upload_url_parameter(self, mock_get_mime_type, mock_remove, mock_getsize, mock_exists, mock_walk):
        """Test that process_output_images correctly scans directory and uploads files with MIME type headers."""
        # Mock directory walking to return test files
        mock_walk.return_value = [
            (RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES, [], ["test1.png", "test2.jpg"])
        ]
        
        # Mock file exists and size
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        # Mock MIME type detection
        mock_get_mime_type.side_effect = ["image/png", "image/jpeg"]
        
        # Reset the global mock and configure it
        rp_handler.tus_client.reset_mock()
        
        # Mock TUS client and uploader
        mock_tus_client = MagicMock()
        mock_uploader = MagicMock()
        mock_uploader.url = "http://example.com/tus/uploaded_file"
        mock_tus_client.uploader.return_value = mock_uploader
        rp_handler.tus_client.TusClient.return_value = mock_tus_client
        
        # Test data
        job_id = "test_job"
        upload_url = "http://example.com/tus" 
        
        # Call the function directly
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Verify TUS client was created with the correct upload_url
        rp_handler.tus_client.TusClient.assert_called_with(upload_url)
        
        # Verify set_headers was called with MIME types
        expected_calls = [
            unittest.mock.call({"mimeType": "image/png"}),
            unittest.mock.call({"mimeType": "image/jpeg"})
        ]
        mock_tus_client.set_headers.assert_has_calls(expected_calls, any_order=False)
        
        # Verify uploader was created for both files and upload was called
        self.assertEqual(mock_tus_client.uploader.call_count, 2)
        mock_uploader.upload.assert_called()
        
        # Verify both files were removed after upload
        self.assertEqual(mock_remove.call_count, 2)
        
        # Verify the result contains the expected values
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["uploaded_count"], 2)

    @patch("rp_handler.os.walk")
    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.os.path.getsize")
    @patch("rp_handler.get_mime_type")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_upload_fails(self, mock_get_mime_type, mock_getsize, mock_exists, mock_walk):
        # Mock directory walking to return test files
        mock_walk.return_value = [
            (RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES, [], ["test1.png"])
        ]
        
        # Mock the file existing and size
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        # Mock MIME type detection
        mock_get_mime_type.return_value = "image/png"
        
        # Reset the global mock and configure it to fail
        rp_handler.tus_client.reset_mock()
        
        # Mock TUS client with upload exception
        mock_tus_client = MagicMock()
        mock_uploader = MagicMock()
        mock_uploader.upload.side_effect = Exception("Upload failed")
        mock_tus_client.uploader.return_value = mock_uploader
        rp_handler.tus_client.TusClient.return_value = mock_tus_client
        
        # Test data
        job_id = "test_job"
        upload_url = "http://example.com/tus"
        
        # Call the function under test
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertIn("Error uploading file test1.png using TUS protocol", result["message"])
        
        # Verify MIME type header was still set
        mock_tus_client.set_headers.assert_called_with({"mimeType": "image/png"})

    @patch("rp_handler.os.path.exists")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_no_upload_url(self, mock_exists):
        # Mock output directory exists
        mock_exists.return_value = True
        
        # Test data
        job_id = "test_job"
        upload_url = None
        
        # Call the function under test
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "No upload URL provided in the job output property")

    @patch("rp_handler.os.walk")
    @patch("rp_handler.os.path.exists")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_no_files_found(self, mock_exists, mock_walk):
        # Mock output directory exists but no files found
        mock_exists.return_value = True
        mock_walk.return_value = [
            (RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES, [], [])
        ]
        
        # Test data
        job_id = "test_job" 
        upload_url = "http://example.com/tus"
        
        # Call the function under test
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "No files found to upload")

    @patch("rp_handler.os.path.exists")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_directory_not_exists(self, mock_exists):
        # Mock output directory doesn't exist
        mock_exists.return_value = False
        
        # Test data
        job_id = "test_job" 
        upload_url = "http://example.com/tus"
        
        # Call the function under test
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertIn("Output directory does not exist", result["message"])

    @patch("rp_handler.os.walk")
    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.os.path.getsize")
    @patch("rp_handler.os.remove")
    @patch("rp_handler.get_mime_type")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_process_output_images_mixed_file_types(self, mock_get_mime_type, mock_remove, mock_getsize, mock_exists, mock_walk):
        """Test that mixed file types (PSD, PNG, TXT) are handled with correct MIME types."""
        # Mock directory walking to return mixed file types
        mock_walk.return_value = [
            (RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES, [], ["artwork.psd", "layer1.png", "layer2.png", "metadata.txt"])
        ]
        
        # Mock file exists and size
        mock_exists.return_value = True
        mock_getsize.return_value = 1024
        
        # Mock MIME type detection for mixed file types
        mock_get_mime_type.side_effect = [
            "image/vnd.adobe.photoshop",  # .psd
            "image/png",                  # .png
            "image/png",                  # .png
            "text/plain"                  # .txt
        ]
        
        # Reset the global mock and configure it
        rp_handler.tus_client.reset_mock()
        
        # Mock TUS client and uploader
        mock_tus_client = MagicMock()
        mock_uploader = MagicMock()
        mock_uploader.url = "http://example.com/tus/uploaded_file"
        mock_tus_client.uploader.return_value = mock_uploader
        rp_handler.tus_client.TusClient.return_value = mock_tus_client
        
        # Test data
        job_id = "test_job"
        upload_url = "http://example.com/tus" 
        
        # Call the function directly
        result = rp_handler.process_output_images(job_id, upload_url)
        
        # Verify TUS client was created with the correct upload_url
        rp_handler.tus_client.TusClient.assert_called_with(upload_url)
        
        # Verify set_headers was called with correct MIME types for each file
        expected_calls = [
            unittest.mock.call({"mimeType": "image/vnd.adobe.photoshop"}),
            unittest.mock.call({"mimeType": "image/png"}),
            unittest.mock.call({"mimeType": "image/png"}),
            unittest.mock.call({"mimeType": "text/plain"})
        ]
        mock_tus_client.set_headers.assert_has_calls(expected_calls, any_order=False)
        
        # Verify uploader was created for all 4 files and upload was called
        self.assertEqual(mock_tus_client.uploader.call_count, 4)
        self.assertEqual(mock_uploader.upload.call_count, 4)
        
        # Verify all 4 files were removed after upload
        self.assertEqual(mock_remove.call_count, 4)
        
        # Verify the result contains the expected values
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["uploaded_count"], 4)

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
    @patch("builtins.open", new_callable=mock_open)
    def test_download_image_successful(self, mock_file, mock_get):
        # Create a mock response for the GET request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Test Image Data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Test URL with a valid filename
        url = "https://example.com/images/test_image.png"
        save_path = "/test/path/input.jpg"
        success, result = rp_handler.download_image(url, save_path)

        # Assertions
        self.assertTrue(success)
        self.assertIsNone(result)  # Should return None on success
        mock_get.assert_called_with(url, stream=True)
        mock_file.assert_called_with(save_path, 'wb')

    @patch("rp_handler.requests.get")
    def test_download_image_with_invalid_url(self, mock_get):
        # Mock a failed request
        mock_get.side_effect = requests.RequestException("Failed to download")

        url = "https://example.com/invalid_image.png"
        save_path = "/test/path/input.jpg"
        success, error_message = rp_handler.download_image(url, save_path)

        # Assertions
        self.assertFalse(success)
        self.assertIn("Error downloading image", error_message)
        mock_get.assert_called_with(url, stream=True)

    @patch("rp_handler.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    def test_download_image_with_url_no_filename(self, mock_file, mock_get):
        # Create a mock response for the GET request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Test Image Data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # Test URL without a filename
        url = "https://example.com/images/"
        save_path = "/test/path/input.jpg"
        success, result = rp_handler.download_image(url, save_path)

        # Assertions
        self.assertTrue(success)
        self.assertIsNone(result)  # Should return None on success
        mock_file.assert_called_with(save_path, 'wb')

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

    def test_valid_input_with_params(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output",
            "params": {"tiling": 2, "denoise": "0.4"}
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, input_data)

    def test_invalid_tiling_param(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output",
            "params": {"tiling": 6, "denoise": "0.4"}  # Invalid tiling
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'tiling' must be one of [2, 3, 4, 5]")

    def test_invalid_denoise_param(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output",
            "params": {"tiling": 2, "denoise": "0.8"}  # Invalid denoise
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'denoise' must be either '0.4' or '0.6'")

    def test_missing_params(self):
        input_data = {
            "input": "https://example.com/image.png",
            "output": "https://example.com/output"
            # Missing params
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'params' must be a dictionary")
