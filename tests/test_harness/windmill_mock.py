"""
Mock Windmill functions for testing.

This module mocks:
- wmill.get_resource() - Returns test database config
- wmill.get_variable() - Returns test API keys
"""

from typing import Dict, Any
import os


class WindmillMock:
    """Mock for Windmill SDK functions."""
    
    def __init__(self):
        self.resources = {
            "f/development/business_layer_db_postgreSQL": {
                "host": os.getenv("TEST_DB_HOST", "localhost"),
                "port": int(os.getenv("TEST_DB_PORT", "5434")),
                "user": os.getenv("TEST_DB_USER", "test_user"),
                "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
                "dbname": os.getenv("TEST_DB_NAME", "test_business_logic"),
                "sslmode": "disable",
                "root_certificate_pem": "",  # Windmill adds this
            }
        }
        
        self.variables = {
            "u/admin/GoogleAPI_JD": os.getenv("GOOGLE_API_KEY", "test_google_key"),
            "u/admin/OpenAI_API_Key": os.getenv("OPENAI_API_KEY", "test_openai_key"),
        }
    
    def get_resource(self, path: str) -> Dict[str, Any]:
        """
        Mock wmill.get_resource().
        
        Args:
            path: Resource path (e.g., "f/development/db_resource")
        
        Returns:
            Resource configuration dict
        
        Raises:
            KeyError: If resource not found
        """
        if path not in self.resources:
            raise KeyError(f"Resource not found: {path}")
        
        return self.resources[path].copy()
    
    def get_variable(self, path: str) -> str:
        """
        Mock wmill.get_variable().
        
        Args:
            path: Variable path (e.g., "u/admin/api_key")
        
        Returns:
            Variable value
        
        Raises:
            KeyError: If variable not found
        """
        if path not in self.variables:
            raise KeyError(f"Variable not found: {path}")
        
        return self.variables[path]
    
    def set_resource(self, path: str, config: Dict[str, Any]):
        """Add or update a resource (for test setup)."""
        self.resources[path] = config.copy()
    
    def set_variable(self, path: str, value: str):
        """Add or update a variable (for test setup)."""
        self.variables[path] = value
    
    def clear(self):
        """Clear all mocked resources and variables."""
        self.resources.clear()
        self.variables.clear()
    
    def reset(self):
        """Reset to default test configuration."""
        self.__init__()