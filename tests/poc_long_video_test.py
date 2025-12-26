#!/usr/bin/env python3
"""POC Test for Wan 2.2 Long Video Workflow via API."""
import json
import os
import shutil
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infrastructure.comfy_api.client import ComfyUIAPI
from infrastructure.config_manager import ConfigManager


def main():
    print("=" * 60)
    print("POC Test: Wan 2.2 Long Video Workflow")
    print("=" * 60)

    # Setup
    config = ConfigManager()
    api = ComfyUIAPI(config.get_comfy_url())

    # Test connection
    print("\n1. Testing ComfyUI connection...")
    result = api.test_connection()
    if not result["connected"]:
        print(f"   ❌ Connection failed: {result['error']}")
        return
    print("   ✅ Connected to ComfyUI")

    # Load workflow
    print("\n2. Loading workflow...")
    workflow_path = "config/workflow_templates/Wan 2.2 long txt 2 vid.json"
    workflow = api.load_workflow(workflow_path)
    print(f"   ✅ Loaded workflow with {len(workflow)} nodes")

    # Copy test image to ComfyUI input
    print("\n3. Preparing test image...")
    test_image = "output/test/cathedral-interior_v1_00001_.png"
    if not os.path.exists(test_image):
        print(f"   ❌ Test image not found: {test_image}")
        return

    comfy_input = os.path.join(config.get_comfy_root(), "input")
    os.makedirs(comfy_input, exist_ok=True)

    target_filename = "poc_test_image.png"
    target_path = os.path.join(comfy_input, target_filename)
    shutil.copy2(test_image, target_path)
    print(f"   ✅ Copied image to: {target_path}")

    # Update workflow parameters
    print("\n4. Configuring workflow...")

    # Set start image (Node 52)
    workflow["52"]["inputs"]["image"] = target_filename
    print(f"   - Start image: {target_filename}")

    # Set prompt for first segment (Node 740)
    test_prompt = "Slow cinematic push through gothic cathedral interior, candlelight flickering, fog drifting, moonlight through windows"
    workflow["740"]["inputs"]["text"] = test_prompt
    print(f"   - Prompt: {test_prompt[:50]}...")

    # Set negative prompt (Node 741)
    neg_prompt = "blurry, low quality, distorted, ugly, bad anatomy"
    workflow["741"]["inputs"]["text"] = neg_prompt
    print(f"   - Negative: {neg_prompt[:30]}...")

    # Set resolution (smaller for faster test)
    workflow["806"]["inputs"]["Number"] = "640"  # Width
    workflow["809"]["inputs"]["Number"] = "360"  # Height
    print("   - Resolution: 640x360 (fast test)")

    # Set frames (shorter for test)
    workflow["277"]["inputs"]["Number"] = "33"  # ~1.4 seconds at 24fps
    print("   - Frames: 33 (~1.4s)")

    # Show GGUF models being used
    print(f"\n   Models:")
    print(f"   - HighNoise: {workflow['61']['inputs']['unet_name']}")
    print(f"   - LowNoise: {workflow['62']['inputs']['unet_name']}")

    # Queue workflow
    print("\n5. Queuing workflow...")
    try:
        prompt_id = api.queue_prompt(workflow)
        print(f"   ✅ Queued with ID: {prompt_id}")
    except Exception as e:
        print(f"   ❌ Queue failed: {e}")
        return

    # Monitor progress
    print("\n6. Monitoring progress...")
    def progress_callback(pct, status):
        bar = "█" * int(pct * 20) + "░" * (20 - int(pct * 20))
        print(f"\r   [{bar}] {pct*100:5.1f}% - {status[:40]:<40}", end="", flush=True)

    start_time = time.time()
    result = api.monitor_progress(prompt_id, callback=progress_callback, timeout=600)
    elapsed = time.time() - start_time

    print(f"\n\n7. Result:")
    print(f"   - Status: {result['status']}")
    print(f"   - Time: {elapsed:.1f}s")

    if result["status"] == "success":
        print(f"   - Output files: {len(result.get('output_images', []))}")
        for img in result.get("output_images", []):
            print(f"     • {img}")
        print("\n   ✅ POC Test PASSED!")
    else:
        print(f"   - Error: {result.get('error', 'Unknown')}")
        print("\n   ❌ POC Test FAILED")

    # Cleanup
    if os.path.exists(target_path):
        os.remove(target_path)
        print(f"\n   Cleaned up: {target_path}")


if __name__ == "__main__":
    main()
