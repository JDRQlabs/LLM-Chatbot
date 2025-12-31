"""
Live Test Configuration

This module configures live tests that make real API calls.
Live tests are skipped by default unless explicitly enabled.

Usage:
    # Run all tests EXCEPT live tests (default behavior)
    pytest tests/

    # Run ONLY live LLM tests
    pytest tests/live/ -m live_llm

    # Run ONLY live embedding tests
    pytest tests/live/ -m live_embeddings

    # Run ALL live tests
    pytest tests/live/ -m live

Environment Variables Required:
    OPENAI_API_KEY: For embedding and GPT tests
    GOOGLE_API_KEY: For Gemini tests (optional)
"""

import pytest
import os
import sys


def pytest_configure(config):
    """Add custom markers and configure live tests."""
    # Register markers
    config.addinivalue_line("markers", "live_llm: Tests that call real LLM APIs")
    config.addinivalue_line("markers", "live_embeddings: Tests that generate real embeddings")
    config.addinivalue_line("markers", "live: All live API tests")


@pytest.fixture(scope="session")
def openai_api_key():
    """
    Get OpenAI API key from environment.
    Skip test if not available.
    """
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set - skipping live test")
    return key


@pytest.fixture(scope="session")
def google_api_key():
    """
    Get Google API key from environment.
    Skip test if not available.
    """
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        pytest.skip("GOOGLE_API_KEY not set - skipping live test")
    return key


@pytest.fixture(scope="session")
def live_test_warning():
    """
    Print warning before running live tests.
    """
    print("\n" + "=" * 60)
    print("WARNING: Running LIVE tests with real API calls")
    print("This will incur API costs!")
    print("=" * 60 + "\n")
    return True
