#!/usr/bin/env python3
"""
HTTP Client Module
Provides unified HTTP client functionality for API requests
"""

import logging
import requests
from typing import Dict, Any, Optional, Tuple, Type
from dataclasses import dataclass

from src.exceptions import (
    HTTPRequestError,
    ShellyConnectionError,
    ShellyTimeoutError,
    ShellyRPCError,
    TibberAPIError,
)
from src.retry import RetryConfig, execute_with_retry

logger = logging.getLogger(__name__)


@dataclass
class HTTPResponse:
    """Standardized HTTP response wrapper"""
    status_code: int
    data: Any
    text: str
    headers: Dict[str, str]
    
    @property
    def ok(self) -> bool:
        """Check if response was successful (2xx status code)"""
        return 200 <= self.status_code < 300


class BaseHTTPClient:
    """Base HTTP client with common functionality"""
    
    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        retry_config: Optional[RetryConfig] = None,
        debug: bool = False
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self.debug = debug
        self.session = requests.Session()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def _build_url(self, endpoint: str = "") -> str:
        """Build full URL from base URL and endpoint"""
        if endpoint:
            return f"{self.base_url}/{endpoint.lstrip('/')}"
        return self.base_url
    
    def _make_request(
        self,
        method: str,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> HTTPResponse:
        """
        Make an HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: URL endpoint (appended to base_url)
            headers: Request headers
            json_data: JSON body data
            data: Raw body data
            params: Query parameters
            
        Returns:
            HTTPResponse with status, data, and headers
        """
        url = self._build_url(endpoint)
        self.logger.debug(f"Making {method} request to {url}")
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                data=data,
                params=params,
                timeout=self.timeout
            )
            
            # Try to parse JSON response
            try:
                response_data = response.json()
            except ValueError:
                response_data = None
            
            return HTTPResponse(
                status_code=response.status_code,
                data=response_data,
                text=response.text,
                headers=dict(response.headers)
            )
            
        except requests.exceptions.Timeout as e:
            raise HTTPRequestError(
                f"Request timed out after {self.timeout}s",
                url=url,
                details={"timeout": self.timeout, "error": str(e)}
            )
        except requests.exceptions.ConnectionError as e:
            raise HTTPRequestError(
                f"Connection failed to {url}",
                url=url,
                details={"error": str(e)}
            )
        except requests.exceptions.RequestException as e:
            raise HTTPRequestError(
                f"Request failed: {e}",
                url=url,
                details={"error": str(e)}
            )
    
    def _request_with_retry(
        self,
        method: str,
        endpoint: str = "",
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        retry_exceptions: Tuple[Type[Exception], ...] = (HTTPRequestError,),
        **kwargs
    ) -> HTTPResponse:
        """Make request with retry logic for specified exceptions"""
        def do_request():
            return self._make_request(method, endpoint, headers, json_data, **kwargs)
        
        if self.retry_config.enabled:
            return execute_with_retry(
                do_request,
                self.retry_config,
                exceptions=retry_exceptions
            )
        return do_request()
    
    def get(self, endpoint: str = "", **kwargs) -> HTTPResponse:
        """Make GET request"""
        return self._make_request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str = "", **kwargs) -> HTTPResponse:
        """Make POST request"""
        return self._make_request("POST", endpoint, **kwargs)
    
    def close(self) -> None:
        """Close the session"""
        self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TibberClient(BaseHTTPClient):
    """HTTP client for Tibber GraphQL API"""
    
    TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"
    
    def __init__(
        self,
        token: str,
        timeout: int = 30,
        retry_config: Optional[RetryConfig] = None,
        debug: bool = False
    ):
        super().__init__(
            base_url=self.TIBBER_API_URL,
            timeout=timeout,
            retry_config=retry_config,
            debug=debug
        )
        self.token = token
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    
    def query(self, graphql_query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the Tibber API.

        Args:
            graphql_query: The GraphQL query string
            variables: Optional dictionary of GraphQL variables

        Returns:
            The 'data' portion of the GraphQL response

        Raises:
            TibberAPIError: If the API returns an error
            HTTPRequestError: If the HTTP request fails
        """
        self.logger.debug(f"Executing GraphQL query")

        json_data = {"query": graphql_query}
        if variables:
            json_data["variables"] = variables

        response = self._request_with_retry(
            "POST",
            headers=self._headers,
            json_data=json_data,
            retry_exceptions=(HTTPRequestError,)
        )
        
        if not response.ok:
            raise TibberAPIError(
                f"Tibber API request failed with status {response.status_code}",
                details={
                    "status_code": response.status_code,
                    "response": response.text[:500] if response.text else None
                }
            )
        
        if response.data is None:
            raise TibberAPIError(
                "Tibber API returned invalid JSON response",
                details={"response_text": response.text[:500] if response.text else None}
            )
        
        # Check for GraphQL errors
        if "errors" in response.data:
            errors = response.data["errors"]
            error_messages = [e.get("message", str(e)) for e in errors]
            raise TibberAPIError(
                f"Tibber API returned errors: {'; '.join(error_messages)}",
                details={"errors": errors}
            )
        
        return response.data.get("data", {})


class ShellyClient(BaseHTTPClient):
    """HTTP client for Shelly RPC API"""
    
    def __init__(
        self,
        host: str,
        timeout: int = 10,
        retry_config: Optional[RetryConfig] = None,
        debug: bool = False,
        username: str = "",
        password: str = ""
    ):
        super().__init__(
            base_url=f"http://{host}/rpc",
            timeout=timeout,
            retry_config=retry_config,
            debug=debug
        )
        self.host = host
        
        # Set up authentication if provided
        if username and password:
            self.session.auth = (username, password)
    
    def rpc_call(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an RPC call to the Shelly device.
        
        Args:
            method: RPC method name (e.g., "Schedule.List", "Switch.Set")
            params: Optional parameters for the RPC call
            
        Returns:
            The 'result' portion of the RPC response
            
        Raises:
            ShellyConnectionError: If connection to device fails
            ShellyTimeoutError: If request times out
            ShellyRPCError: If the RPC call returns an error
        """
        payload = {
            "id": 1,
            "method": method
        }
        if params:
            payload["params"] = params
        
        self.logger.debug(f"RPC call: {method} with params: {params}")
        
        try:
            response = self._request_with_retry(
                "POST",
                json_data=payload,
                retry_exceptions=(ShellyConnectionError, ShellyTimeoutError)
            )
        except HTTPRequestError as e:
            # Convert generic HTTP errors to Shelly-specific errors
            if "timed out" in str(e).lower() or "timeout" in str(e).lower():
                raise ShellyTimeoutError(
                    f"Shelly device at {self.host} timed out",
                    details={"host": self.host, "method": method}
                )
            raise ShellyConnectionError(
                f"Failed to connect to Shelly device at {self.host}",
                details={"host": self.host, "method": method, "error": str(e)}
            )
        
        if not response.ok:
            raise ShellyConnectionError(
                f"Shelly device returned HTTP {response.status_code}",
                details={
                    "host": self.host,
                    "status_code": response.status_code,
                    "response": response.text[:500] if response.text else None
                }
            )
        
        if response.data is None:
            raise ShellyRPCError(
                f"Shelly device returned invalid JSON",
                method=method,
                details={"response_text": response.text[:500] if response.text else None}
            )
        
        # Check for RPC errors
        if "error" in response.data:
            error = response.data["error"]
            error_code = error.get("code", -1)
            error_message = error.get("message", "Unknown error")
            raise ShellyRPCError(
                f"Shelly RPC error: {error_message}",
                method=method,
                error_code=error_code,
                details={"error": error}
            )
        
        return response.data.get("result", {})
