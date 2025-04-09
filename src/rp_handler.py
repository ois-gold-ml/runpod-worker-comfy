import runpod
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import uuid
from io import BytesIO
from tusclient import client as tus_client

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
# Path to the workflow JSON file
WORKFLOW_FILE = os.environ.get("WORKFLOW_FILE", "/workflow.json")


def load_workflow():
    """
    Load the workflow from the JSON file.

    Returns:
        tuple: A tuple containing the workflow and an error message, if any.
               The structure is (workflow, error_message).
    """
    try:
        # List contents of root directory for debugging
        print("Contents of root directory:")
        for item in os.listdir('/app/src'):
            print(f"- {item}")
            
        print(f"\nAttempting to load workflow from: {WORKFLOW_FILE}")
        with open(WORKFLOW_FILE, 'r') as f:
            workflow = json.load(f)
        return workflow, None
    except Exception as e:
        return None, f"Error loading workflow file: {str(e)}"


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
    if input_url is not None and not isinstance(input_url, str):
        return None, "'input' must be a string containing a presigned URL"

    # Validate 'output' in input
    output_url = job_input.get("output")
    if output_url is None or not isinstance(output_url, str):
        return None, "'output' must be a string containing a presigned URL"

    # Return validated data and no error
    return {"input": input_url, "output": output_url}, None


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

    for i in range(retries):
        try:
            response = requests.get(url)

            # If the response status code is 200, the server is up and running
            if response.status_code == 200:
                print(f"runpod-worker-comfy - API is reachable")
                return True
        except requests.RequestException as e:
            # If an exception occurs, the server may not be ready
            pass

        # Wait for the specified delay before retrying
        time.sleep(delay / 1000)

    print(
        f"runpod-worker-comfy - Failed to connect to server at {url} after {retries} attempts."
    )
    return False


def download_image(url):
    """
    Download an image from a presigned URL.

    Args:
        url (str): The presigned URL to download the image from.

    Returns:
        tuple: A tuple containing (success_flag, data_or_error_message).
               If successful, returns (True, image_data).
               If unsuccessful, returns (False, error_message).
    """
    try:
        print(f"runpod-worker-comfy - downloading image from {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Extract filename from URL or use a default name
        try:
            filename = os.path.basename(urllib.parse.urlparse(url).path)
            if not filename or '.' not in filename:
                filename = "downloaded_image.png"
        except:
            filename = "downloaded_image.png"
            
        return True, (filename, response.content)
    except requests.RequestException as e:
        error_message = f"Error downloading image: {str(e)}"
        print(f"runpod-worker-comfy - {error_message}")
        return False, error_message


def upload_image_to_comfy(image_data):
    """
    Upload an image to the ComfyUI server using the /upload/image endpoint.

    Args:
        image_data (tuple): A tuple containing (filename, binary_data) of the image.

    Returns:
        dict: A dictionary containing the status and details of the upload.
    """
    if not image_data:
        return {"status": "error", "message": "No image data provided"}

    # Generate a UUID filename
    filename = f"{uuid.uuid4()}.png"
    binary_data = image_data[1]  # We only need the binary data, not the original filename
    print(f"runpod-worker-comfy - uploading image: {filename}")

    try:
        # Prepare the form data
        files = {
            "image": (filename, BytesIO(binary_data), "image/png"),
            "overwrite": (None, "true"),
        }

        # POST request to upload the image
        response = requests.post(f"http://{COMFY_HOST}/upload/image", files=files)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        print(f"runpod-worker-comfy - image upload complete")
        return {
            "status": "success",
            "message": f"Successfully uploaded {filename}",
            "filename": filename
        }
    except requests.RequestException as e:
        error_message = f"Error uploading {filename}: {str(e)}"
        print(f"runpod-worker-comfy - {error_message}")
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


def process_output_images(outputs, job_id, upload_url=None):
    """
    This function processes output images and uploads them using the TUS protocol.

    Args:
        outputs (dict): A dictionary containing the outputs from image generation,
                        typically includes node IDs and their respective output data.
        job_id (str): The unique identifier for the job.
        upload_url (str): The URL to upload the image to using the TUS protocol.

    Returns:
        dict: A dictionary with the status ('success' or 'error') and the message,
              which is the URL to the uploaded image or an error message.
    """
    if upload_url is None:
        return {
            "status": "error",
            "message": "No upload URL provided in the job output property",
        }

    # The path where ComfyUI stores the generated images
    COMFY_OUTPUT_PATH = os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output")

    output_images = []
    uploaded_urls = []

    # Collect all image paths
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for image in node_output["images"]:
                image_path = os.path.join(image["subfolder"], image["filename"])
                output_images.append(image_path)

    print(f"runpod-worker-comfy - found {len(output_images)} images to upload")

    # Upload each image
    for image_path in output_images:
        local_image_path = f"{COMFY_OUTPUT_PATH}/{image_path}"
        
        if not os.path.exists(local_image_path):
            print(f"runpod-worker-comfy - image does not exist: {local_image_path}")
            continue

        try:
            # Create a TUS client
            my_client = tus_client.TusClient(upload_url)
            
            # Get the file size
            file_size = os.path.getsize(local_image_path)
            
            # Set up the uploader
            print(f"runpod-worker-comfy - uploading image {image_path} using TUS protocol to {upload_url}")
            uploader = my_client.uploader(local_image_path, chunk_size=5*1024*1024)
            
            # Upload the file
            uploader.upload()
            
            # Get the URL of the uploaded file
            uploaded_url = uploader.url
            uploaded_urls.append(uploaded_url)
            
            print(f"runpod-worker-comfy - image {image_path} was uploaded successfully")
            
        except Exception as e:
            error_message = f"Error uploading image {image_path} using TUS protocol: {str(e)}"
            print(f"runpod-worker-comfy - {error_message}")
            return {
                "status": "error",
                "message": error_message,
            }

    if not uploaded_urls:
        return {
            "status": "error",
            "message": "No images were successfully uploaded",
        }

    return {
        "status": "success",
        "message": uploaded_urls[0],  # Return the first URL for backward compatibility
        "all_urls": uploaded_urls,    # Include all URLs in the response
    }


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
    validated_data, error_message = validate_input(job)
    if error_message:
        return {"error": error_message}

    # Extract validated data
    input_url = validated_data["input"]
    upload_url = validated_data["output"]

    # Load workflow from file
    workflow, error_message = load_workflow()
    if error_message:
        return {"error": error_message}

    # Make sure that the ComfyUI API is available
    check_server(
        f"http://{COMFY_HOST}",
        COMFY_API_AVAILABLE_MAX_RETRIES,
        COMFY_API_AVAILABLE_INTERVAL_MS,
    )

    # Download and upload image if URL is provided
    if input_url:
        success, result = download_image(input_url)
        if not success:
            return {"error": result}
        
        upload_result = upload_image_to_comfy(result)
        if upload_result["status"] == "error":
            return {"error": upload_result["message"]}
        
        # Update the workflow with the new filename
        # Find the LoadImage node and update its image input
        for node_id, node_data in workflow.items():
            if node_data.get("class_type") == "LoadImage":
                node_data["inputs"]["image"] = upload_result["filename"]
                break

    # Queue the workflow
    try:
        queued_workflow = queue_workflow(workflow)
        prompt_id = queued_workflow["prompt_id"]
        print(f"runpod-worker-comfy - queued workflow with ID {prompt_id}")
    except Exception as e:
        return {"error": f"Error queuing workflow: {str(e)}"}

    # Poll for completion
    print(f"runpod-worker-comfy - wait until image generation is complete")
    retries = 0
    try:
        while retries < COMFY_POLLING_MAX_RETRIES:
            history = get_history(prompt_id)

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
    images_result = process_output_images(history[prompt_id].get("outputs"), job["id"], upload_url)

    result = {**images_result, "refresh_worker": REFRESH_WORKER}

    return result


# Start the handler only if this script is run directly
if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
