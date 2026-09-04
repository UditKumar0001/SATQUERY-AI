# tests/conftest.py
import os
import sys
from unittest.mock import MagicMock

# Ensure repository root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Mock external ML/LLM packages if not installed in current test environment
if "rasterio" not in sys.modules:
    try:
        import rasterio
    except ImportError:
        mock_r = MagicMock()
        mock_r.open.side_effect = Exception("Rasterio unavailable")
        sys.modules["rasterio"] = mock_r

import types

class MockModule(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()

for mod in ["openai", "google", "google.generativeai", "torch", "transformers", "langchain_core", "langgraph", "langgraph.graph"]:
    if mod not in sys.modules:
        try:
            __import__(mod)
        except Exception:
            m = MockModule(mod)
            sys.modules[mod] = m
