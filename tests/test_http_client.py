#!/usr/bin/env python3
"""
Unit tests for HTTP client module
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import requests

from src.http_client import (
    BaseHTTPClient,
    TibberClient,
    ShellyClient,
    HTTPResponse,
)
from src.exceptions import (
    HTTPRequestError,
    TibberAPIError,
    ShellyConnectionError,
    ShellyTimeoutError,
    ShellyRPCError,
)
from src.retry import RetryConfig


class TestHTTPResponse(unittest.TestCase):
    """Test HTTPResponse dataclass"""
    
    def test_ok_for_200(self):
        """Test ok property for 200 status"""
        response = HTTPResponse(200, {"data": "test"}, '{"data": "test"}', {})
        self.assertTrue(response.ok)
    
    def test_ok_for_201(self):
        """Test ok property for 201 status"""
        response = HTTPResponse(201, {}, '{}', {})
        self.assertTrue(response.ok)
    
    def test_not_ok_for_400(self):
        """Test ok property for 400 status"""
        response = HTTPResponse(400, {}, '{}', {})
        self.assertFalse(response.ok)
    
    def test_not_ok_for_500(self):
        """Test ok property for 500 status"""
        response = HTTPResponse(500, {}, '{}', {})
        self.assertFalse(response.ok)


class TestBaseHTTPClient(unittest.TestCase):
    """Test BaseHTTPClient"""
    
    def test_build_url_no_endpoint(self):
        """Test URL building without endpoint"""
        client = BaseHTTPClient("https://api.example.com")
        self.assertEqual(client._build_url(), "https://api.example.com")
    
    def test_build_url_with_endpoint(self):
        """Test URL building with endpoint"""
        client = BaseHTTPClient("https://api.example.com")
        self.assertEqual(client._build_url("/v1/test"), "https://api.example.com/v1/test")
    
    def test_build_url_strips_trailing_slash(self):
        """Test URL building strips trailing slash from base"""
        client = BaseHTTPClient("https://api.example.com/")
        self.assertEqual(client._build_url("/test"), "https://api.example.com/test")
    
    @patch('src.http_client.requests.Session')
    def test_make_request_success(self, mock_session_class):
        """Test successful request"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "ok"}'
        mock_response.json.return_value = {"result": "ok"}
        mock_response.headers = {"Content-Type": "application/json"}
        mock_session.request.return_value = mock_response
        
        client = BaseHTTPClient("https://api.example.com")
        response = client._make_request("GET", "/test")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"result": "ok"})
    
    @patch('src.http_client.requests.Session')
    def test_make_request_timeout(self, mock_session_class):
        """Test request timeout handling"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        client = BaseHTTPClient("https://api.example.com", timeout=5)
        
        with self.assertRaises(HTTPRequestError) as context:
            client._make_request("GET", "/test")
        
        self.assertIn("timed out", str(context.exception).lower())
    
    @patch('src.http_client.requests.Session')
    def test_make_request_connection_error(self, mock_session_class):
        """Test connection error handling"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = BaseHTTPClient("https://api.example.com")
        
        with self.assertRaises(HTTPRequestError) as context:
            client._make_request("GET", "/test")
        
        self.assertIn("Connection failed", str(context.exception))


class TestTibberClient(unittest.TestCase):
    """Test TibberClient"""
    
    def test_init_sets_headers(self):
        """Test that init sets authorization headers"""
        client = TibberClient("test-token")
        self.assertEqual(client._headers["Authorization"], "Bearer test-token")
        self.assertEqual(client._headers["Content-Type"], "application/json")
    
    @patch('src.http_client.requests.Session')
    def test_query_success(self, mock_session_class):
        """Test successful GraphQL query"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"data": {"viewer": {"homes": []}}}'
        mock_response.json.return_value = {"data": {"viewer": {"homes": []}}}
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = TibberClient("test-token")
        result = client.query("{ viewer { homes { id } } }")
        
        self.assertEqual(result, {"viewer": {"homes": []}})
    
    @patch('src.http_client.requests.Session')
    def test_query_api_error(self, mock_session_class):
        """Test GraphQL query with API error"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_response.json.return_value = None
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = TibberClient("invalid-token")
        
        with self.assertRaises(TibberAPIError):
            client.query("{ viewer { homes { id } } }")
    
    @patch('src.http_client.requests.Session')
    def test_query_graphql_error(self, mock_session_class):
        """Test GraphQL query with GraphQL errors"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"errors": [{"message": "Invalid query"}]}'
        mock_response.json.return_value = {"errors": [{"message": "Invalid query"}]}
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = TibberClient("test-token")
        
        with self.assertRaises(TibberAPIError) as context:
            client.query("{ invalid }")
        
        self.assertIn("Invalid query", str(context.exception))


class TestShellyClient(unittest.TestCase):
    """Test ShellyClient"""
    
    def test_init_sets_base_url(self):
        """Test that init sets correct base URL"""
        client = ShellyClient("192.168.1.100")
        self.assertEqual(client.base_url, "http://192.168.1.100/rpc")
    
    @patch('src.http_client.requests.Session')
    def test_rpc_call_success(self, mock_session_class):
        """Test successful RPC call"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"id": 1, "result": {"jobs": []}}'
        mock_response.json.return_value = {"id": 1, "result": {"jobs": []}}
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = ShellyClient("192.168.1.100")
        result = client.rpc_call("Schedule.List")
        
        self.assertEqual(result, {"jobs": []})
    
    @patch('src.http_client.requests.Session')
    def test_rpc_call_with_params(self, mock_session_class):
        """Test RPC call with parameters"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"id": 1, "result": {"id": 123}}'
        mock_response.json.return_value = {"id": 1, "result": {"id": 123}}
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = ShellyClient("192.168.1.100")
        result = client.rpc_call("Schedule.Create", {"timespec": "0 0 10 * * *"})
        
        self.assertEqual(result, {"id": 123})
        
        # Verify the payload was correct
        call_args = mock_session.request.call_args
        json_data = call_args.kwargs.get('json')
        self.assertEqual(json_data["method"], "Schedule.Create")
        self.assertEqual(json_data["params"], {"timespec": "0 0 10 * * *"})
    
    @patch('src.http_client.requests.Session')
    def test_rpc_call_connection_error(self, mock_session_class):
        """Test RPC call with connection error"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        client = ShellyClient("192.168.1.100", retry_config=RetryConfig(enabled=False))
        
        with self.assertRaises(ShellyConnectionError):
            client.rpc_call("Schedule.List")
    
    @patch('src.http_client.requests.Session')
    def test_rpc_call_timeout(self, mock_session_class):
        """Test RPC call with timeout"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.request.side_effect = requests.exceptions.Timeout("Timed out")
        
        client = ShellyClient("192.168.1.100", retry_config=RetryConfig(enabled=False))
        
        with self.assertRaises(ShellyTimeoutError):
            client.rpc_call("Schedule.List")
    
    @patch('src.http_client.requests.Session')
    def test_rpc_call_rpc_error(self, mock_session_class):
        """Test RPC call with RPC error response"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"id": 1, "error": {"code": -1, "message": "Invalid method"}}'
        mock_response.json.return_value = {"id": 1, "error": {"code": -1, "message": "Invalid method"}}
        mock_response.headers = {}
        mock_session.request.return_value = mock_response
        
        client = ShellyClient("192.168.1.100")
        
        with self.assertRaises(ShellyRPCError) as context:
            client.rpc_call("Invalid.Method")
        
        self.assertIn("Invalid method", str(context.exception))


class TestClientContextManager(unittest.TestCase):
    """Test context manager functionality"""
    
    @patch('src.http_client.requests.Session')
    def test_context_manager(self, mock_session_class):
        """Test client can be used as context manager"""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        with BaseHTTPClient("https://api.example.com") as client:
            self.assertIsNotNone(client)
        
        mock_session.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
