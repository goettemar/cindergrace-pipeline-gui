"""ComfyUI API client with WebSocket support"""
import json
import os
import time
import uuid
import copy
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Optional, Callable, Any
import websocket
from io import BytesIO
from PIL import Image

from domain.exceptions import (
    ComfyUIConnectionError,
    WorkflowLoadError,
    WorkflowExecutionError,
    WorkflowTimeoutError,
)
from infrastructure.logger import get_logger
from .workflow_updater import WorkflowUpdater

logger = get_logger(__name__)


class ComfyUIAPI:
    """ComfyUI API client for workflow execution and monitoring"""

    def __init__(self, server_url: str = "http://127.0.0.1:8188"):
        """
        Initialize ComfyUI API client

        Args:
            server_url: Base URL of ComfyUI server
        """
        self.server_url = server_url.rstrip('/')
        self.ws_url = self.server_url.replace('http', 'ws')
        self.client_id = str(uuid.uuid4())
        self.workflow_updater = WorkflowUpdater()

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to ComfyUI and get system stats

        Returns:
            Dictionary with:
                - connected: bool
                - system: dict of system info (if connected)
                - error: str (if connection failed)
        """
        try:
            logger.info(f"Testing connection to ComfyUI at {self.server_url}")
            response = self._get_request("/system_stats")
            logger.info("✓ Connection successful")
            return {
                "connected": True,
                "system": response,
                "error": None
            }
        except ComfyUIConnectionError as e:
            logger.warning(f"Connection test failed: {e}")
            return {
                "connected": False,
                "system": None,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error during connection test: {e}", exc_info=True)
            return {
                "connected": False,
                "system": None,
                "error": str(e)
            }

    def load_workflow(self, workflow_path: str) -> Dict[str, Any]:
        """
        Load workflow JSON from file

        Args:
            workflow_path: Path to workflow JSON file

        Returns:
            Workflow dictionary

        Raises:
            WorkflowLoadError: If workflow file not found or invalid
        """
        logger.debug(f"Loading workflow from {workflow_path}")

        if not os.path.exists(workflow_path):
            raise WorkflowLoadError(f"Workflow nicht gefunden: {workflow_path}")

        try:
            with open(workflow_path, 'r') as f:
                workflow = json.load(f)
            logger.debug(f"✓ Workflow loaded: {len(workflow)} nodes")
            return workflow
        except json.JSONDecodeError as e:
            raise WorkflowLoadError(f"Ungültiges Workflow-JSON: {e}")
        except Exception as e:
            raise WorkflowLoadError(f"Konnte Workflow nicht laden: {e}")

    def update_workflow_params(
        self,
        workflow: Dict[str, Any],
        **params
    ) -> Dict[str, Any]:
        """
        Update workflow parameters

        Args:
            workflow: Workflow dictionary
            **params: Parameters to update (prompt, seed, steps, cfg, filename_prefix)

        Returns:
            Updated workflow dictionary

        Example:
            api.update_workflow_params(
                workflow,
                prompt="gothic cathedral at night",
                seed=1001,
                steps=20,
                cfg=7.0,
                filename_prefix="test_001",
                width=1280,
                height=720,
                startframe_path="/tmp/frame.png",
                num_frames=72,
            )
        """
        try:
            return self.workflow_updater.update(workflow, **params)
        except Exception as exc:
            logger.warning(f"WorkflowUpdater failed, falling back to legacy updater: {exc}")
            return self._legacy_update_workflow_params(workflow, **params)

    def _legacy_update_workflow_params(self, workflow: Dict[str, Any], **params: Any) -> Dict[str, Any]:
        """
        Backward-compatible parameter injection kept as a safety net.
        """
        workflow_copy = copy.deepcopy(workflow)
        for node_id, node_data in workflow_copy.items():
            node_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})

            if node_type == "RandomNoise":
                if "seed" in params:
                    if "noise_seed" in inputs:
                        inputs["noise_seed"] = params["seed"]
                    if "seed" in inputs:
                        inputs["seed"] = params["seed"]

            elif node_type == "KSampler":
                if "seed" in params and "seed" in inputs:
                    inputs["seed"] = params["seed"]
                if "steps" in params and "steps" in inputs:
                    inputs["steps"] = params["steps"]
                if "cfg" in params and "cfg" in inputs:
                    inputs["cfg"] = params["cfg"]

            elif node_type == "BasicScheduler":
                if "steps" in params and "steps" in inputs:
                    inputs["steps"] = params["steps"]

            elif node_type == "CLIPTextEncode":
                if "prompt" in params:
                    inputs["text"] = params["prompt"]

            elif node_type == "SaveImage":
                if "filename_prefix" in params:
                    inputs["filename_prefix"] = params["filename_prefix"]

            elif node_type == "EmptyLatentImage":
                if "width" in params and "width" in inputs:
                    inputs["width"] = params["width"]
                if "height" in params and "height" in inputs:
                    inputs["height"] = params["height"]

            if "seed" in params:
                for key in ("seed", "noise_seed"):
                    if key in inputs:
                        inputs[key] = params["seed"]

            node_data["inputs"] = inputs

        return workflow_copy

    def queue_prompt(self, workflow: Dict[str, Any]) -> str:
        """
        Queue workflow for execution

        Args:
            workflow: Workflow dictionary

        Returns:
            prompt_id: Unique ID for this job

        Raises:
            Exception: If queue request fails
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        try:
            response = self._post_request("/prompt", payload)
            prompt_id = response["prompt_id"]
            logger.info(f"✓ Queued job: {prompt_id}")
            return prompt_id
        except WorkflowExecutionError:
            raise
        except Exception as e:
            logger.error(f"Failed to queue prompt: {e}", exc_info=True)
            raise WorkflowExecutionError(f"Konnte Workflow nicht starten: {e}")

    def monitor_progress(
        self,
        prompt_id: str,
        callback: Optional[Callable[[float, str], None]] = None,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Monitor job progress via WebSocket

        Args:
            prompt_id: Job ID to monitor
            callback: Optional callback(progress_pct, status_text)
            timeout: Timeout in seconds (default: 300)

        Returns:
            Dictionary with:
                - status: "success" | "error"
                - output_images: List of image paths
                - error: str (if error occurred)
        """
        ws_url = f"{self.ws_url}/ws?clientId={self.client_id}"

        try:
            ws = websocket.create_connection(ws_url, timeout=timeout)
            logger.debug(f"✓ WebSocket connected: {ws_url}")

            start_time = time.time()
            current_node = None
            max_nodes = 1
            has_started = False  # Track if execution has actually started (seen at least one node)

            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    ws.close()
                    return {
                        "status": "error",
                        "output_images": [],
                        "error": "Timeout waiting for completion"
                    }

                # Receive message
                try:
                    message = ws.recv()
                    if isinstance(message, str):
                        data = json.loads(message)
                        msg_type = data.get("type")

                        # Execution started
                        if msg_type == "execution_start":
                            logger.debug(f"Received execution_start for prompt")
                            if callback:
                                callback(0.0, "Execution started...")

                        # Progress update
                        elif msg_type == "executing":
                            exec_data = data.get("data", {})
                            node_id = exec_data.get("node")
                            exec_prompt_id = exec_data.get("prompt_id")

                            # When node is None and prompt_id matches:
                            # - At START: node=null means "about to execute" (has_started=False)
                            # - At END: node=null means "execution complete" (has_started=True)
                            if node_id is None and exec_prompt_id == prompt_id:
                                if has_started:
                                    # This is the END signal - execution complete
                                    logger.info(f"Execution complete for prompt {prompt_id}")
                                    if callback:
                                        callback(1.0, "Generation complete")
                                    break
                                else:
                                    # This is the START signal - execution beginning
                                    logger.debug(f"Execution starting for prompt {prompt_id}")
                                    if callback:
                                        callback(0.0, "Execution starting...")
                            elif node_id:
                                has_started = True  # We've seen at least one node execute
                                current_node = node_id
                                if callback:
                                    # Estimate progress (rough approximation)
                                    progress = 0.5  # Mid-execution
                                    callback(progress, f"Executing node {node_id}...")

                        # Node execution complete
                        elif msg_type == "executed":
                            has_started = True  # Execution has definitely started
                            node_id = data.get("data", {}).get("node")
                            if callback:
                                callback(0.9, f"Completed node {node_id}")

                        # execution_cached means some nodes are cached, but job may still be running
                        # Do NOT break on this - just note that execution has started
                        elif msg_type == "execution_cached":
                            cached_data = data.get("data", {})
                            cached_prompt_id = cached_data.get("prompt_id")
                            if cached_prompt_id == prompt_id:
                                has_started = True  # Execution has begun (some nodes cached)
                                logger.debug(f"Some nodes cached for prompt {prompt_id}, continuing to wait...")
                                if callback:
                                    callback(0.1, "Some nodes cached, processing...")

                        # execution_success is a clear completion signal
                        elif msg_type == "execution_success":
                            success_data = data.get("data", {})
                            success_prompt_id = success_data.get("prompt_id")
                            if success_prompt_id in (None, prompt_id):
                                logger.info(f"Received execution_success for prompt {prompt_id}")
                                if callback:
                                    callback(1.0, "Generation complete")
                                break
                            logger.debug(f"Ignoring execution_success for different prompt {success_prompt_id}")

                except websocket.WebSocketTimeoutException:
                    # Check if job is done via history
                    history = self.get_history(prompt_id)
                    if history:
                        ws.close()
                        if callback:
                            callback(1.0, "Complete")
                        break
                    continue

            ws.close()

            # Get output images (with retries to handle slow history write)
            output_images = self.get_output_images(prompt_id, retries=15, delay=1.0)

            return {
                "status": "success",
                "output_images": output_images,
                "error": None
            }

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            return {
                "status": "error",
                "output_images": [],
                "error": str(e)
            }

    def _monitor_via_polling(
        self,
        prompt_id: str,
        callback: Optional[Callable[[float, str], None]] = None,
        timeout: int = 300,
        start_time: float = None,
        poll_interval: float = 3.0
    ) -> Dict[str, Any]:
        """
        Monitor job progress via HTTP polling (fallback for unstable WebSocket).

        Args:
            prompt_id: Job ID to monitor
            callback: Optional callback(progress_pct, status_text)
            timeout: Timeout in seconds
            start_time: Start time (for continuing from WebSocket failure)
            poll_interval: Seconds between polls

        Returns:
            Dictionary with status, output_images, error
        """
        if start_time is None:
            start_time = time.time()

        if callback:
            callback(0.3, "Polling for completion...")

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return {
                    "status": "error",
                    "output_images": [],
                    "error": f"Timeout after {timeout}s waiting for completion"
                }

            # Check history for completion
            try:
                history = self.get_history(prompt_id)
                if history:
                    # Job completed
                    logger.info(f"Job {prompt_id} completed (detected via polling)")
                    if callback:
                        callback(1.0, "Generation complete")

                    output_images = self.get_output_images(prompt_id, retries=5, delay=1.0)
                    return {
                        "status": "success",
                        "output_images": output_images,
                        "error": None
                    }
            except Exception as e:
                logger.debug(f"Polling check failed: {e}")

            # Check queue status
            try:
                queue = self._get_request("/queue")
                running = queue.get("queue_running", [])
                pending = queue.get("queue_pending", [])

                # Check if our job is still in queue
                job_in_queue = any(
                    item[1] == prompt_id
                    for item in running + pending
                )

                if job_in_queue:
                    progress = min(0.3 + (elapsed / timeout) * 0.6, 0.9)
                    if callback:
                        callback(progress, f"Processing... ({int(elapsed)}s)")
                else:
                    # Job not in queue - check history one more time
                    history = self.get_history(prompt_id)
                    if history:
                        logger.info(f"Job {prompt_id} completed")
                        if callback:
                            callback(1.0, "Generation complete")

                        output_images = self.get_output_images(prompt_id, retries=5, delay=1.0)
                        return {
                            "status": "success",
                            "output_images": output_images,
                            "error": None
                        }

            except Exception as e:
                logger.debug(f"Queue check failed: {e}")

            time.sleep(poll_interval)

    def get_output_images(self, prompt_id: str, retries: int = 0, delay: float = 0.5) -> List[str]:
        """
        Download output images from completed job

        Args:
            prompt_id: Job ID
            retries: Number of retries if history is missing/empty
            delay: Delay between retries (seconds)

        Returns:
            List of local image file paths
        """
        try:
            history = None
            attempt = 0
            while attempt <= retries:
                history = self.get_history(prompt_id)
                if history:
                    break
                if attempt < retries:
                    time.sleep(delay)
                attempt += 1
            if not history:
                logger.warning(f"No history found for prompt_id: {prompt_id} after {retries + 1} attempt(s)")
                return []

            output_images = []

            # Parse history to find output images
            for node_id, node_output in history.get("outputs", {}).items():
                if "images" in node_output:
                    for image_info in node_output["images"]:
                        filename = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")
                        image_type = image_info.get("type", "output")

                        logger.debug(f"Downloading: {filename} (subfolder: {subfolder}, type: {image_type})")

                        try:
                            # Download image
                            image_data = self._get_image(filename, subfolder, image_type)

                            # Save locally with absolute path
                            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                            output_dir = os.path.join(script_dir, "output", "test")
                            os.makedirs(output_dir, exist_ok=True)
                            local_path = os.path.join(output_dir, filename)

                            with open(local_path, 'wb') as f:
                                f.write(image_data)

                            output_images.append(local_path)
                            logger.debug(f"✓ Downloaded: {local_path}")

                        except Exception as e:
                            logger.warning(f"Failed to download {filename}: {e}")
                            continue

            return output_images

        except Exception as e:
            logger.error(f"Failed to get output images: {e}", exc_info=True)
            return []

    def get_history(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job history from ComfyUI

        Args:
            prompt_id: Job ID

        Returns:
            History dictionary or None if not found
        """
        try:
            response = self._get_request(f"/history/{prompt_id}")
            return response.get(prompt_id)
        except Exception as e:
            logger.warning(f"Failed to get history: {e}")
            return None

    def _get_image(
        self,
        filename: str,
        subfolder: str = "",
        image_type: str = "output"
    ) -> bytes:
        """
        Download image from ComfyUI

        Args:
            filename: Image filename
            subfolder: Subfolder path
            image_type: Image type (output, input, temp)

        Returns:
            Image bytes
        """
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": image_type
        }
        url = f"{self.server_url}/view?" + urllib.parse.urlencode(params)

        with urllib.request.urlopen(url) as response:
            return response.read()

    def _get_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make GET request to ComfyUI

        Args:
            endpoint: API endpoint (e.g., "/system_stats")

        Returns:
            Response JSON

        Raises:
            ComfyUIConnectionError: If request fails
        """
        url = f"{self.server_url}{endpoint}"

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read())
        except urllib.error.URLError as e:
            raise ComfyUIConnectionError(f"Verbindung fehlgeschlagen: {e.reason}")
        except Exception as e:
            raise ComfyUIConnectionError(f"Anfrage fehlgeschlagen: {e}")

    def _post_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make POST request to ComfyUI

        Args:
            endpoint: API endpoint
            data: Request payload

        Returns:
            Response JSON

        Raises:
            WorkflowExecutionError: If request fails
        """
        url = f"{self.server_url}{endpoint}"

        payload = json.dumps(data).encode('utf-8')
        headers = {'Content-Type': 'application/json'}

        request = urllib.request.Request(url, data=payload, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            # Read error response body for details
            error_body = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_body)
                error_detail = error_json.get('error', error_body)
            except:
                error_detail = error_body
            logger.error(f"POST request failed: HTTP {e.code} - {error_detail}")
            raise WorkflowExecutionError(f"Workflow-Ausführung fehlgeschlagen: HTTP {e.code} - {error_detail}")
        except Exception as e:
            logger.error(f"POST request failed: {e}")
            raise WorkflowExecutionError(f"Workflow-Ausführung fehlgeschlagen: {e}")
