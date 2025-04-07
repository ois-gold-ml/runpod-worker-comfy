import unittest
from unittest.mock import patch, MagicMock, mock_open, Mock
import sys
import os
import json
import base64
import requests

# Mock modules before importing rp_handler
sys.modules['runpod'] = MagicMock()
sys.modules['runpod.serverless'] = MagicMock()
sys.modules['runpod.serverless.utils'] = MagicMock()
sys.modules['runpod.serverless.utils.rp_upload'] = MagicMock()

# Make sure that "src" is known and can be used to import rp_handler.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
from src import rp_handler

# Local folder for test resources
RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES = "./test_resources/images"


class TestRunpodWorkerComfy(unittest.TestCase):
    def test_valid_input_with_workflow_only(self):
        input_data = {"workflow": {"key": "value"}}
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, {"workflow": {"key": "value"}, "input": None})

    def test_valid_input_with_workflow_and_input_url(self):
        input_data = {
            "workflow": {"key": "value"},
            "input": "https://example.com/image.png",
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, input_data)

    def test_input_missing_workflow(self):
        input_data = {"input": "https://example.com/image.png"}
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Missing 'workflow' parameter")

    def test_input_with_invalid_input_url_type(self):
        input_data = {
            "workflow": {"key": "value"},
            "input": 123,  # Not a string
        }
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "'input' must be a string containing a presigned URL")

    def test_invalid_json_string_input(self):
        input_data = "invalid json"
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNotNone(error)
        self.assertEqual(error, "Invalid JSON format in input")

    def test_valid_json_string_input(self):
        input_data = '{"workflow": {"key": "value"}}'
        validated_data, error = rp_handler.validate_input(input_data)
        self.assertIsNone(error)
        self.assertEqual(validated_data, {"workflow": {"key": "value"}, "input": None})

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

    @patch("builtins.open", new_callable=mock_open, read_data=b"test")
    def test_base64_encode(self, mock_file):
        test_data = base64.b64encode(b"test").decode("utf-8")

        result = rp_handler.base64_encode("dummy_path")

        self.assertEqual(result, test_data)

    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.rp_upload.upload_image")
    @patch.dict(
        os.environ, {"COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES}
    )
    def test_bucket_endpoint_not_configured(self, mock_upload_image, mock_exists):
        mock_exists.return_value = True
        mock_upload_image.return_value = "simulated_uploaded/image.png"

        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "123"

        result = rp_handler.process_output_images(outputs, job_id)

        self.assertEqual(result["status"], "success")

    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.rp_upload.upload_image")
    @patch.dict(
        os.environ,
        {
            "COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES,
            "BUCKET_ENDPOINT_URL": "http://example.com",
        },
    )
    def test_bucket_endpoint_configured(self, mock_upload_image, mock_exists):
        # Mock the os.path.exists to return True, simulating that the image exists
        mock_exists.return_value = True

        # Mock the rp_upload.upload_image to return a simulated URL
        mock_upload_image.return_value = "http://example.com/uploaded/image.png"

        # Define the outputs and job_id for the test
        outputs = {"node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": "test"}]}}
        job_id = "123"

        # Call the function under test
        result = rp_handler.process_output_images(outputs, job_id)

        # Assertions
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["message"], "http://example.com/uploaded/image.png")
        mock_upload_image.assert_called_once_with(
            job_id, "./test_resources/images/test/ComfyUI_00001_.png"
        )

    @patch("rp_handler.os.path.exists")
    @patch("rp_handler.rp_upload.upload_image")
    @patch.dict(
        os.environ,
        {
            "COMFY_OUTPUT_PATH": RUNPOD_WORKER_COMFY_TEST_RESOURCES_IMAGES,
            "BUCKET_ENDPOINT_URL": "http://example.com",
            "BUCKET_ACCESS_KEY_ID": "",
            "BUCKET_SECRET_ACCESS_KEY": "",
        },
    )
    def test_bucket_image_upload_fails_env_vars_wrong_or_missing(
        self, mock_upload_image, mock_exists
    ):
        # Simulate the file existing in the output path
        mock_exists.return_value = True

        # When AWS credentials are wrong or missing, upload_image should return 'simulated_uploaded/...'
        mock_upload_image.return_value = "simulated_uploaded/image.png"

        outputs = {
            "node_id": {"images": [{"filename": "ComfyUI_00001_.png", "subfolder": ""}]}
        }
        job_id = "123"

        result = rp_handler.process_output_images(outputs, job_id)

        # Check if the image was saved to the 'simulated_uploaded' directory
        self.assertIn("simulated_uploaded", result["message"])
        self.assertEqual(result["status"], "success")

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
    def test_upload_image_to_comfy_successful(self, mock_post):
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
        self.assertEqual(result["filename"], "test_image.png")
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

    def test_upload_image_to_comfy_no_data(self):
        # Test with no image data
        result = rp_handler.upload_image_to_comfy(None)

        # Assertions
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["message"], "No image data provided")
