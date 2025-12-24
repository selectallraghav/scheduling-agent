"""Darwinbox Employee API client service."""

import os
import base64
import json
from datetime import datetime
from typing import Optional, Dict, Any, List
import httpx


class DarwinboxClient:
    """Client for Darwinbox Employee API."""
    
    def __init__(
        self,
        username: str = None,
        password: str = None,
        api_key: str = None,
        dataset_key: str = None,
        base_url: str = None
    ):
        """
        Initialize Darwinbox API client.
        
        Args:
            username: Basic Auth username (defaults to env var DARWINBOX_USERNAME)
            password: Basic Auth password (defaults to env var DARWINBOX_PASSWORD)
            api_key: API key (defaults to env var DARWINBOX_API_KEY)
            dataset_key: Dataset key (defaults to env var DARWINBOX_DATASET_KEY)
            base_url: Base URL for Darwinbox API (defaults to env var DARWINBOX_BASE_URL)
        """
        self.username = username or os.getenv("DARWINBOX_USERNAME", "apexon_nest")
        self.password = password or os.getenv("DARWINBOX_PASSWORD", "Apexon@nest@321")
        self.api_key = api_key or os.getenv(
            "DARWINBOX_API_KEY",
            "29e4a737782658d531ceb77c38bcae63e7ec1d5dbda7c9bcf48749da7640a6c79ce52efe36dc0c2586dd7c0f572c4909f00b96ff5f0f97d6dafee91da429a393"
        )
        self.dataset_key = dataset_key or os.getenv(
            "DARWINBOX_DATASET_KEY",
            "d7dd623e21a8460abbc9549b413c523ed4f2822b4800414eb78eea7f730f894874d205b35f531a2355b6438982e3d200741313991e25d5b0db8b2b16703c44e1"
        )
        self.base_url = base_url or os.getenv(
            "DARWINBOX_BASE_URL",
            "https://apexon-peoplehubuat.darwinbox.in/masterapi/employee"
        )
        
        # Cache for employee data
        self._employee_cache: Dict[str, Dict[str, Any]] = {}
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests with Basic Auth."""
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        
        return {
            "Content-Type": "application/json",
            "Authorization": f"Basic {encoded_credentials}"
        }
    
    def get_all_employees(self, last_modified: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all employees from Darwinbox API.
        
        Args:
            last_modified: Date in DD-MM-YYYY format (defaults to "01-01-2025")
            
        Returns:
            List of all employee data dictionaries
        """
        # Use default date if not provided
        if not last_modified:
            last_modified = "01-01-2025"
        
        payload = {
            "api_key": self.api_key,
            "datasetKey": self.dataset_key,
            "last_modified": last_modified,
            "employee_ids": []  # Empty array to get all employees
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                # Try GET method first
                try:
                    response = client.request(
                        "GET",
                        self.base_url,
                        content=json.dumps(payload),
                        headers=self._get_headers()
                    )
                    if response.status_code in [405, 400]:
                        raise httpx.HTTPStatusError("Method not allowed", request=response.request, response=response)
                except (httpx.HTTPStatusError, httpx.RequestError):
                    # Fallback to POST
                    response = client.post(
                        self.base_url,
                        json=payload,
                        headers=self._get_headers()
                    )
                response.raise_for_status()
                
                result = response.json()
                
                if result.get("status") == 1:
                    employee_data = result.get("employee_data", [])
                    
                    # Cache all results
                    for employee in employee_data:
                        emp_id = (
                            employee.get("employee_id", "") or
                            employee.get("employeeId", "") or
                            str(employee.get("employee_id", ""))
                        )
                        if emp_id:
                            self._employee_cache[str(emp_id)] = employee
                    
                    return employee_data
                else:
                    error_msg = result.get("message", "Unknown error")
                    print(f"Darwinbox API error: {error_msg}")
                    return []
                    
        except httpx.HTTPError as e:
            print(f"HTTP error fetching all employees from Darwinbox: {e}")
            return []
        except json.JSONDecodeError:
            print("JSON decode error in Darwinbox API response")
            return []
        except Exception as e:
            print(f"Error fetching all employees from Darwinbox: {e}")
            return []
    
    def get_employee_data(
        self,
        employee_ids: List[str],
        last_modified: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get employee data from Darwinbox API.
        
        Args:
            employee_ids: List of employee IDs to fetch
            last_modified: Date in DD-MM-YYYY format (defaults to "01-01-2025")
            
        Returns:
            List of employee data dictionaries
        """
        if not employee_ids:
            return []
        
        # Check cache first
        cached_results = []
        uncached_ids = []
        for emp_id in employee_ids:
            if emp_id in self._employee_cache:
                cached_results.append(self._employee_cache[emp_id])
            else:
                uncached_ids.append(emp_id)
        
        # If all results are cached, return them
        if not uncached_ids:
            return cached_results
        
        # Use default date if not provided
        if not last_modified:
            last_modified = "01-01-2025"
        
        payload = {
            "api_key": self.api_key,
            "datasetKey": self.dataset_key,
            "last_modified": last_modified,
            "employee_ids": uncached_ids
        }
        
        try:
            with httpx.Client(timeout=30.0) as client:
                # Try GET method first (as shown in Postman screenshots)
                # Some APIs accept GET with JSON body
                try:
                    response = client.request(
                        "GET",
                        self.base_url,
                        content=json.dumps(payload),
                        headers=self._get_headers()
                    )
                    # If GET returns 405 or similar, try POST
                    if response.status_code in [405, 400]:
                        raise httpx.HTTPStatusError("Method not allowed", request=response.request, response=response)
                except (httpx.HTTPStatusError, httpx.RequestError):
                    # Fallback to POST if GET doesn't work
                    response = client.post(
                        self.base_url,
                        json=payload,
                        headers=self._get_headers()
                    )
                response.raise_for_status()
                
                result = response.json()
                
                # Check if request was successful
                if result.get("status") == 1:
                    employee_data = result.get("employee_data", [])
                    
                    # Cache the results
                    for employee in employee_data:
                        # Try multiple employee_id field variations
                        emp_id = (
                            employee.get("employee_id", "") or
                            employee.get("employeeId", "") or
                            str(employee.get("employee_id", ""))
                        )
                        if emp_id:
                            self._employee_cache[str(emp_id)] = employee
                    
                    # Return cached + new results
                    return cached_results + employee_data
                else:
                    # API returned error
                    error_msg = result.get("message", "Unknown error")
                    print(f"Darwinbox API error: {error_msg}")
                    return cached_results
                    
        except httpx.HTTPError as e:
            print(f"HTTP error fetching employee data from Darwinbox: {e}")
            return cached_results
        except json.JSONDecodeError:
            print("JSON decode error in Darwinbox API response")
            return cached_results
        except Exception as e:
            print(f"Error fetching employee data from Darwinbox: {e}")
            return cached_results
    
    def get_employee_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get employee data by email address.
        
        Note: This requires fetching all employees and filtering by email.
        For better performance, use get_employee_data with employee_id if available.
        
        Args:
            email: Employee email address
            
        Returns:
            Employee data dictionary or None if not found
        """
        # Check cache first
        for emp_data in self._employee_cache.values():
            # Try multiple email field variations
            emp_email = (
                emp_data.get("email", "") or 
                emp_data.get("email_id", "") or
                emp_data.get("emailId", "") or
                emp_data.get("employee_email", "")
            )
            if emp_email and emp_email.lower() == email.lower():
                return emp_data
        
        # If not in cache, we'd need to fetch all employees
        # For now, return None - this should be called with employee_id when possible
        return None
    
    def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """
        Get employee data by employee ID.
        
        Args:
            employee_id: Employee ID (can be string or number)
            
        Returns:
            Employee data dictionary or None if not found
        """
        # Normalize employee_id to string
        employee_id_str = str(employee_id).strip()
        
        # Check cache first
        if employee_id_str in self._employee_cache:
            return self._employee_cache[employee_id_str]
        
        # Also check cache with different formats
        for cached_id, cached_data in self._employee_cache.items():
            if str(cached_id) == employee_id_str or cached_id == employee_id_str:
                return cached_data
        
        # Fetch from API
        results = self.get_employee_data([employee_id_str])
        if results:
            return results[0]
        
        return None
    
    def extract_manager_info(self, employee_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract manager information from employee data.
        
        Args:
            employee_data: Employee data dictionary from Darwinbox API
            
        Returns:
            Dictionary with keys: hrbp, hiring_manager, reporting_manager
            Each value is a dict with email and employee_id (if available)
        """
        result = {
            "hrbp": None,
            "hiring_manager": None,
            "reporting_manager": None
        }
        
        # Helper function to get value with multiple possible keys
        def get_value(data: Dict[str, Any], *keys: str, default: str = "") -> str:
            """Try multiple keys to get a value."""
            for key in keys:
                value = data.get(key, "")
                if value:
                    return str(value).strip()
            return default
        
        # Extract HRBP info - try multiple field name variations
        # Primary format uses underscores (as shown in example)
        hrbp_employee_id = get_value(
            employee_data,
            "hrbp_employee_id",  # Primary - underscore format
            "hrbp employee id",  # Fallback - spaces
            "hrbpEmployeeId",
            default=""
        )
        hrbp_email = get_value(
            employee_data,
            "hrbp_email_id",  # Primary - underscore format
            "hrbp email id",  # Fallback - spaces
            "hrbpEmailId",
            "hrbpEmail",
            default=""
        )
        
        if hrbp_email or hrbp_employee_id:
            result["hrbp"] = {
                "email": hrbp_email,
                "employee_id": hrbp_employee_id
            }
        
        # Extract direct manager info (could be hiring or reporting manager)
        # Primary format uses underscores (as shown in example)
        direct_manager_employee_id = get_value(
            employee_data,
            "direct_manager_employee_id",  # Primary - underscore format
            "direct manager employee id",  # Fallback - spaces
            "directManagerEmployeeId",
            default=""
        )
        direct_manager_email = get_value(
            employee_data,
            "direct_manager_email",  # Primary - underscore format
            "direct manager email",  # Fallback - spaces
            "directManagerEmail",
            default=""
        )
        
        if direct_manager_email or direct_manager_employee_id:
            # Use direct manager as both hiring and reporting manager for now
            # This can be refined based on actual data structure
            manager_info = {
                "email": direct_manager_email,
                "employee_id": direct_manager_employee_id
            }
            result["hiring_manager"] = manager_info
            result["reporting_manager"] = manager_info
        
        return result
