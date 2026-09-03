# tests/conftest.py
import os
import sys
from unittest.mock import MagicMock

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Mock external ML/LLM packages if not installed in current test environment
for mod in ["google", "google.generativeai", "torch", "transformers", "langchain_core", "langgraph"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except ImportError:
            mock = MagicMock()
            sys.modules[mod] = mock
