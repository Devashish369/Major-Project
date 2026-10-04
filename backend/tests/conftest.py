"""
conftest.py – pytest configuration for IntelliPM backend tests.

Adding the backend directory to sys.path ensures pytest can find the `app`
package when running from the repo root or from backend/.
"""
import sys
import os

# Make sure 'app' is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
