import runpod
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import uuid
import logging
import sys
import glob
from io import BytesIO
from tusclient import client as tus_client
from loki_logger_handler.loki_logger_handler import LokiLoggerHandler

# Logging level - set to "debug" for verbose logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").lower()
# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = 50
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = 500
# Time to wait between poll attempts in milliseconds
COMFY_POLLING_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 250))
# Maximum number of poll attempts
COMFY_POLLING_MAX_RETRIES = int(os.environ.get("COMFY_POLLING_MAX_RETRIES", 500))
# Host where ComfyUI is running
COMFY_HOST = "127.0.0.1:8188"
# Enforce a clean state after each job is done
# see https://docs.runpod.io/docs/handler-additional-controls#refresh-worker
REFRESH_WORKER = os.environ.get("REFRESH_WORKER", "false").lower() == "true"
# Enable dry mode - skip ComfyUI processing and just pass through images
DRY_MODE = os.environ.get("DRY_MODE", "false").lower() == "true"

# Module-level logger
logger = None

def setup_logger():
    """
    Sets up and configures the module-level logger instance.
    """
    global logger
    if logger is not None:
        return logger
        
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    LOKI_URL = os.getenv("LOKI_URL")

    if LOKI_URL:
        logger.info("Configuring Loki logging.")
        loki_handler = LokiLoggerHandler(
            url=LOKI_URL,
            labels={"app": "ois-gold-serverless-worker"}
        )
        logger.addHandler(loki_handler)
    else:
        logger.warning("Loki credentials not provided, falling back to local logging.")
        
        local_handler = logging.StreamHandler(sys.stdout)
        local_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        local_handler.setFormatter(formatter)
        
        logger.addHandler(local_handler)
    
    return logger

def ensure_logger():
    """
    Ensures that the logger is set up before use.
    """
    global logger
    if logger is None:
        setup_logger()

def validate_input(job_input):
    """
    Validates the input for the handler function.

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    # Validate if job_input is provided
    if job_input is None:
        return None, "Please provide input"

    # Check if input is a string and try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    # Validate 'input' in input, if provided
    input_url = job_input.get("input")
    if not isinstance(input_url, str):
        return None, "'input' must be a string containing an image URL"

    # Validate 'output' in input
    output_url = job_input.get("output")
    if output_url is None or not isinstance(output_url, str):
        return None, "'output' must be a string containing a presigned URL"

    # Validate 'params' in input
    params = job_input.get("params")
    if not isinstance(params, dict):
        return None, "'params' must be a dictionary"

    tiling = params.get("tiling")
    denoise = params.get("denoise")

    if tiling not in [2, 3, 4, 5]:
        return None, "'tiling' must be one of [2, 3, 4, 5]"

    if denoise not in ["0.4", "0.6"]:
        return None, "'denoise' must be either '0.4' or '0.6'"

    # Return validated data and no error
    return {"input": input_url, "output": output_url, "params": params}, None


def check_server(url, retries=500, delay=50):
    """
    Check if a server is reachable via HTTP GET request

    Args:
    - url (str): The URL to check
    - retries (int, optional): The number of times to attempt connecting to the server. Default is 50
    - delay (int, optional): The time in milliseconds to wait between retries. Default is 500

    Returns:
    bool: True if the server is reachable within the given number of retries, otherwise False
    """
    ensure_logger()

    for i in range(retries):
        try:
            response = requests.get(url)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                logger.info("API is reachable", extra={"url": url})
                return True
        except requests.RequestException as e:
            # If an exception occurs, the server may not be ready
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    logger.error("Failed to connect to server", extra={"url": url, "retries": retries})
    return False


def download_image(url, save_path):
    """
    Download an image from a presigned URL and save it to a specified path.

    Args:
        url (str): The presigned URL to download the image from.
        save_path (str): The path to save the downloaded image.

    Returns:
        tuple: A tuple containing (success_flag, data_or_error_message).
               If successful, returns (True, image_data).
               If unsuccessful, returns (False, error_message).
    """
    ensure_logger()
    
    try:
        logger.info("Downloading image", extra={"url": url})
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Save the image to the specified path
        with open(save_path, 'wb') as f:
            f.write(response.content)

        return True, None
    except requests.RequestException as e:
        error_message = f"Error downloading image: {str(e)}"
        logger.error("Failed to download image", extra={"url": url, "error": str(e)})
        return False, error_message


def upload_image_to_comfy(image_data):
    """
    Upload an image to the ComfyUI server using the /upload/image endpoint.

    Args:
        image_data (tuple): A tuple containing (filename, binary_data) of the image.

    Returns:
        dict: A dictionary containing the status and details of the upload.
    """
    ensure_logger()
    
    if not image_data:
        return {"status": "error", "message": "No image data provided"}

    # Generate a UUID filename
    image_filename = f"{uuid.uuid4()}.png"
    binary_data = image_data[1]  # We only need the binary data, not the original filename
    logger.info("Uploading image to ComfyUI", extra={"image_filename": image_filename})

    try:
        # Prepare the form data
        files = {
            "image": (image_filename, BytesIO(binary_data), "image/png"),
            "overwrite": (None, "true"),
        }

        # POST request to upload the image
        response = requests.post(f"http://{COMFY_HOST}/upload/image", files=files)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        logger.info("Image upload complete", extra={"image_filename": image_filename})
        return {
            "status": "success",
            "message": f"Successfully uploaded {image_filename}",
            "filename": image_filename
        }
    except requests.RequestException as e:
        error_message = f"Error uploading {image_filename}: {str(e)}"
        logger.error("Failed to upload image to ComfyUI", extra={"image_filename": image_filename, "error": str(e)})
        return {
            "status": "error",
            "message": error_message
        }


def queue_workflow(workflow):
    """
    Queue a workflow to be processed by ComfyUI

    Args:
        workflow (dict): A dictionary containing the workflow to be processed

    Returns:
        dict: The JSON response from ComfyUI after processing the workflow
    """

    # The top level element "prompt" is required by ComfyUI
    data = json.dumps({"prompt": workflow}).encode("utf-8")

    req = urllib.request.Request(f"http://{COMFY_HOST}/prompt", data=data)
    return json.loads(urllib.request.urlopen(req).read())


def get_history(prompt_id):
    """
    Retrieve the history of a given prompt using its ID

    Args:
        prompt_id (str): The ID of the prompt whose history is to be retrieved

    Returns:
        dict: The history of the prompt, containing all the processing steps and results
    """
    with urllib.request.urlopen(f"http://{COMFY_HOST}/history/{prompt_id}") as response:
        return json.loads(response.read())


def process_output_images(job_id, upload_url=None):
    """
    This function scans the output directory for all files and uploads them using the TUS protocol.
    After successful upload, each file is removed to prevent re-uploading in subsequent runs.

    Args:
        job_id (str): The unique identifier for the job.
        upload_url (str): The URL to upload the files to using the TUS protocol.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and the message.
    """
    ensure_logger()
    
    if upload_url is None:
        return {
            "status": "error",
            "message": "No upload URL provided in the job output property",
        }

    # The path where ComfyUI stores the generated images
    COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output")

    if not os.path.exists(COMFY_OUTPUT_PATH):
        logger.error("Output directory does not exist", extra={"output_path": COMFY_OUTPUT_PATH})
        return {
            "status": "error",
            "message": f"Output directory does not exist: {COMFY_OUTPUT_PATH}",
        }

    # Find all files in the output directory recursively
    all_files = []
    for root, dirs, files in os.walk(COMFY_OUTPUT_PATH):
        for file in files:
            full_path = os.path.join(root, file)
            # Skip hidden files and directories that start with underscore or contain placeholder text
            if (not file.startswith('.') and 
                not file.startswith('_') and 
                'placeholder' not in file.lower() and
                '_will_be_put_here' not in file.lower()):
                all_files.append(full_path)

    logger.info("Found files to upload", extra={"file_count": len(all_files), "job_id": job_id})

    if not all_files:
        logger.warning("No files found to upload", extra={"output_path": COMFY_OUTPUT_PATH, "job_id": job_id})
        return {
            "status": "success",
            "message": "No files found to upload"
        }

    uploaded_count = 0
    
    # Upload each file
    for file_path in all_files:
        if not os.path.exists(file_path):
            logger.warning("File no longer exists, skipping", extra={"file_path": file_path, "job_id": job_id})
            continue

        try:
            # Get file info for logging
            file_size = os.path.getsize(file_path)
            relative_path = os.path.relpath(file_path, COMFY_OUTPUT_PATH)
            
            logger.info("Starting file upload", extra={
                "file_path": file_path,
                "file_size_bytes": file_size,
                "upload_url": upload_url,
                "job_id": job_id
            })

            # Create a TUS client
            my_client = tus_client.TusClient(upload_url)
            
            # Set up the uploader
            uploader = my_client.uploader(file_path, chunk_size=5*1024*1024)
            
            # Upload the file
            uploader.upload()
            
            # Get the URL of the uploaded file
            uploaded_url = uploader.url
            
            logger.info("File uploaded successfully", extra={
                "file_path": file_path,
                "file_size_bytes": file_size,
                "uploaded_url": uploaded_url,
                "job_id": job_id
            })
            
            # Remove the file after successful upload
            try:
                os.remove(file_path)
                logger.info("File removed after upload", extra={
                    "file_path": file_path,
                    "job_id": job_id
                })
            except OSError as e:
                logger.warning("Failed to remove file after upload", extra={
                    "file_path": file_path,
                    "error": str(e),
                    "job_id": job_id
                })
            
            uploaded_count += 1
            
        except Exception as e:
            error_message = f"Error uploading file {relative_path} using TUS protocol: {str(e)}"
            logger.error("Failed to upload file using TUS protocol", extra={
                "file_path": relative_path,
                "error": str(e),
                "job_id": job_id
            })
            return {
                "status": "error",
                "message": error_message,
            }

    logger.info("All files uploaded successfully", extra={
        "uploaded_count": uploaded_count,
        "job_id": job_id
    })

    return {
        "status": "success",
        "uploaded_count": uploaded_count
    }


def process_dry_mode(input_url, upload_url):
    """
    Process the request in dry mode - download input image and upload it directly.
    Waits 5 seconds before uploading and tracks total processing time.

    Args:
        input_url (str): URL to download the input image from
        upload_url (str): URL to upload the image to using TUS protocol

    Returns:
        dict: A dictionary with status and message
    """
    try:
        # Create a temporary file for the image
        temp_filename = f"/tmp/{uuid.uuid4()}.png"
        
        # Download the input image
        success, error_message = download_image(input_url, temp_filename)
        if not success:
            return {"status": "error", "message": error_message}

        # Record the start time for tracking
        start_time = time.time()

        # Create a TUS client
        my_client = tus_client.TusClient(upload_url)

        try:
            # Wait for 5 seconds before uploading
            logger.info("Waiting before upload in dry mode", extra={"wait_seconds": 5})
            time.sleep(5)
            
            # Set up the uploader with proper file handling
            logger.info("Uploading image using TUS protocol in dry mode", extra={"upload_url": upload_url})
            
            # Use context manager to ensure file is properly closed
            with open(temp_filename, 'rb') as file_obj:
                uploader = my_client.uploader(file_obj, chunk_size=5*1024*1024)
                # Upload the file
                uploader.upload()
            
            # Calculate total processing time
            total_time = time.time() - start_time
            logger.info("Image uploaded successfully in dry mode", extra={"total_time_seconds": round(total_time, 2)})
            
            return {
                "status": "success"
            }

        finally:
            # Clean up temporary file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)

    except Exception as e:
        return {"status": "error", "message": f"Error in dry mode processing: {str(e)}"}


def handler(job):
    """
    The main function that handles a job of generating an image.

    This function validates the input, sends a prompt to ComfyUI for processing,
    polls ComfyUI for result, and retrieves generated images.

    Args:
        job (dict): A dictionary containing job details and input parameters.

    Returns:
        dict: A dictionary containing either an error message or a success status with generated images.
    """
    try:
        setup_logger()
    except Exception as e:
        logger.error("Error setting up logger", extra={"error": str(e)})

    validated_data, error_message = validate_input(job['input'])
    if error_message:
        return {"error": error_message}

    # Extract validated data
    input_url = validated_data["input"]
    upload_url = validated_data["output"]
    params = validated_data["params"]

    # Check if ComfyUI input directory exists early to fail fast
    COMFY_INPUT_PATH = os.environ.get("COMFY_INPUT_PATH", "/comfyui/input")
    if not os.path.exists(COMFY_INPUT_PATH):
        error_message = f"ComfyUI input directory does not exist: {COMFY_INPUT_PATH}"
        logger.error("ComfyUI input directory not found", extra={"input_path": COMFY_INPUT_PATH})
        return {"error": error_message}

    # If in dry mode, skip ComfyUI processing
    if DRY_MODE:
        logger.info("Running in dry mode", extra={})
        result = process_dry_mode(input_url, upload_url)
        return {**result, "refresh_worker": REFRESH_WORKER}

    # Download the input image
    success, error_message = download_image(input_url, f"{COMFY_INPUT_PATH}/input.jpg")
    if not success:
        return {"error": error_message}

    # Load workflow from file based on params
    workflow_file_path = f"workflows/{params['tiling']}_{params['denoise']}/workflow.json"
    # Make the path absolute relative to the script directory
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    workflow_file_path = os.path.join(script_dir, workflow_file_path)
    try:
        with open(workflow_file_path, 'r') as f:
            workflow = json.load(f)
    except Exception as e:
        return {"error": f"Error loading workflow file: {str(e)}"}

    # Make sure that the ComfyUI API is available
    check_server(
        f"http://{COMFY_HOST}",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    )

    # Queue the workflow
    try:
        queued_workflow = queue_workflow(workflow)
        prompt_id = queued_workflow["prompt_id"]
        logger.info("Queued workflow", extra={"prompt_id": prompt_id})
    except Exception as e:
        return {"error": f"Error queuing workflow: {str(e)}"}

    # Poll for completion
    logger.info("Waiting for image generation to complete", extra={})
    retries = 0
    try:
        while retries < COMFY_POLLING_MAX_RETRIES:
            history = get_history(prompt_id)

            # Log history output every fifth iteration only in debug mode
            if LOG_LEVEL == "debug" and retries % 5 == 0:
                logger.debug("Polling iteration", extra={"iteration": retries, "history": json.dumps(history)})

            # Exit the loop if we have found the history
            if prompt_id in history and history[prompt_id].get("outputs"):
                break
            else:
                # Wait before trying again
                time.sleep(COMFY_POLLING_INTERVAL_MS / 1000)
                retries += 1
        else:
            return {"error": "Max retries reached while waiting for image generation"}
    except Exception as e:
        return {"error": f"Error waiting for image generation: {str(e)}"}

    # Get the generated image and upload it using TUS protocol
    images_result = process_output_images(job["id"], upload_url)

    result = {**images_result, "refresh_worker": REFRESH_WORKER}

    return result


# Start the handler only if this script is run directly
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
