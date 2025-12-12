#!/usr/bin/env python3
"""Test script to verify logging works"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure.logger import get_logger

logger = get_logger(__name__)

print("Testing logger...")
print(f"Logger name: {logger.name}")
print(f"Logger level: {logger.level}")
print(f"Logger handlers: {logger.handlers}")
print(f"Parent logger: {logger.parent}")
print(f"Parent handlers: {logger.parent.handlers if logger.parent else 'None'}")

logger.debug("This is a DEBUG message")
logger.info("This is an INFO message")
logger.warning("This is a WARNING message")
logger.error("This is an ERROR message")

print("\nCheck logs/pipeline.log for output")
