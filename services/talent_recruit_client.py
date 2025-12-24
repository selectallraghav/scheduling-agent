"""Employee data client service - Uses Darwinbox API as the data source."""

import os
from datetime import date, timedelta
from typing import Optional, Dict, Any, List

from models.entities import Candidate, Manager
from services.darwinbox_client import DarwinboxClient


class TalentRecruitClient:
    """
    Client for employee and candidate data.
    
    This client wraps the Darwinbox API to provide a unified interface for
    accessing employee information, candidates, and their associated managers
    (HRBP, Hiring Manager, Reporting Manager).
    
    Note: The class name is kept for backward compatibility, but it now uses
    Darwinbox API exclusively, not Talent Recruit API.
    """
    
    def __init__(self):
        """Initialize client with Darwin API as the only data source."""
        try:
            self.darwinbox_client = DarwinboxClient()
        except Exception as e:
            raise ValueError(f"Failed to initialize Darwinbox client: {e}")
        
        # Cache for candidates and managers
        self._candidates_cache: Dict[str, Candidate] = {}
        self._managers_cache: Dict[str, Manager] = {}
        self._candidates_list_cache: List[Candidate] = []
        self._raw_api_data_cache: List[Dict[str, Any]] = []
    
    def clear_cache(self):
        """Clear all caches."""
        self._candidates_cache.clear()
        self._managers_cache.clear()
        self._candidates_list_cache.clear()
        self._raw_api_data_cache.clear()
    
    def _get_field(self, data: Dict[str, Any], *keys: str, default: str = "") -> str:
        """Helper to get value with multiple field name variations."""
        for key in keys:
            value = data.get(key, "")
            if value:
                return str(value).strip()
        return default
    
    def _map_employee_to_candidate(self, employee_data: Dict[str, Any]) -> Optional[Candidate]:
        """
        Map Darwin API employee data to Candidate entity.
        
        Darwin API provides:
        - employee_id
        - first_name
        - last_name
        - direct_manager_employee_id
        - direct_manager_email
        - hrbp_employee_id
        - hrbp_email_id
        """
        try:
            # Extract basic info
            first_name = self._get_field(employee_data, "first_name", "first name", "firstName", default="")
            last_name = self._get_field(employee_data, "last_name", "last name", "lastName", default="")
            name = f"{first_name} {last_name}".strip()
            
            if not name:
                return None
            
            # Get employee ID
            employee_id = self._get_field(
                employee_data,
                "employee_id",
                "employee id",
                "employeeId",
                default=""
            )
            
            if not employee_id:
                return None
            
            candidate_id = str(employee_id).strip()
            
            # Email - not in Darwin API, generate from name
            email = self._get_field(employee_data, "email", "email_id", "emailId", default="")
            if not email:
                if first_name and last_name:
                    email = f"{first_name.lower()}.{last_name.lower()}@apexon.com"
                else:
                    email = f"employee_{employee_id}@apexon.com"
            
            # Role title - not in Darwin API, use default
            role_title = self._get_field(
                employee_data,
                "role_title",
                "designation",
                "job_title",
                default="Employee"
            )
            
            # Start date - not in Darwin API, use default (today + 14 days)
            start_date = date.today() + timedelta(days=14)
            
            # Location/timezone - not in Darwin API, use default
            location_timezone = "Asia/Kolkata"
            
            # Manager IDs from Darwin API
            direct_manager_email = self._get_field(
                employee_data,
                "direct_manager_email",
                "direct manager email",
                "directManagerEmail",
                default=""
            )
            
            # Use direct manager for both hiring and reporting manager
            hiring_manager_id = f"mgr_{direct_manager_email}" if direct_manager_email else "mgr_default"
            reporting_manager_id = hiring_manager_id
            
            return Candidate(
                id=candidate_id,
                name=name,
                email=email,
                role_title=role_title,
                location_timezone=location_timezone,
                start_date=start_date,
                hiring_manager_id=hiring_manager_id,
                reporting_manager_id=reporting_manager_id
            )
        except Exception as e:
            print(f"Error mapping employee to candidate: {e}")
            return None
    
    def _create_manager_from_email(
        self,
        email: str,
        employee_id: str = "",
        role: str = "Hiring Manager"
    ) -> Optional[Manager]:
        """Create Manager entity from email and optional employee ID."""
        if not email:
            return None
        
        # Extract name from email
        email_name = email.split("@")[0].replace(".", " ").title()
        manager_id = f"mgr_{email}"
        
        return Manager(
            id=manager_id,
            name=email_name,
            email=email,
            role=role,
            location_timezone="Asia/Kolkata",
            calendar_ids={"apexon": f"apexon_cal_{manager_id}"}
        )
    
    def _fetch_all_employees(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Fetch all employees from Darwin API."""
        if use_cache and self._raw_api_data_cache:
            return self._raw_api_data_cache
        
        try:
            employees_data = self.darwinbox_client.get_all_employees()
            self._raw_api_data_cache = employees_data
            return employees_data
        except Exception as e:
            print(f"Error fetching employees from Darwin API: {e}")
            return []
    
    def get_candidate_by_id(self, candidate_id: str) -> Optional[Candidate]:
        """Get a candidate by ID (employee ID from Darwin API)."""
        # Check cache first
        if candidate_id in self._candidates_cache:
            return self._candidates_cache[candidate_id]
        
        # Try to find in cached list
        if self._candidates_list_cache:
            for candidate in self._candidates_list_cache:
                if candidate.id == candidate_id or str(candidate.id) == str(candidate_id):
                    self._candidates_cache[candidate_id] = candidate
                    return candidate
        
        # Fetch from Darwin API
        try:
            employee_data = self.darwinbox_client.get_employee_by_id(candidate_id)
            if employee_data:
                mapped_candidate = self._map_employee_to_candidate(employee_data)
                if mapped_candidate:
                    self._candidates_cache[candidate_id] = mapped_candidate
                    return mapped_candidate
        except Exception as e:
            print(f"Error fetching employee {candidate_id} from Darwin API: {e}")
        
        # Fallback: search in cached API data
        employees_data = self._fetch_all_employees(use_cache=True)
        for employee_data in employees_data:
            mapped_candidate = self._map_employee_to_candidate(employee_data)
            if mapped_candidate:
                if mapped_candidate.id == candidate_id or str(mapped_candidate.id) == str(candidate_id):
                    self._candidates_cache[candidate_id] = mapped_candidate
                    return mapped_candidate
        
        return None
    
    def list_candidates(self) -> List[Candidate]:
        """List all candidates from Darwin API."""
        # Return cached list if available
        if self._candidates_list_cache:
            return self._candidates_list_cache
        
        # Fetch from Darwin API
        employees_data = self._fetch_all_employees(use_cache=False)
        
        if not employees_data:
            return []
        
        candidates = []
        for employee_data in employees_data:
            mapped_candidate = self._map_employee_to_candidate(employee_data)
            if mapped_candidate:
                self._candidates_cache[mapped_candidate.id] = mapped_candidate
                candidates.append(mapped_candidate)
        
        self._candidates_list_cache = candidates
        return candidates
    
    def get_manager_by_id(self, manager_id: str) -> Optional[Manager]:
        """Get a manager by ID."""
        # Check cache first
        if manager_id in self._managers_cache:
            return self._managers_cache[manager_id]
        
        # Try to find manager from cached employees
        employees_data = self._fetch_all_employees(use_cache=True)
        for employee_data in employees_data:
            manager_info = self.darwinbox_client.extract_manager_info(employee_data)
            
            # Check HRBP
            if manager_info.get("hrbp") and manager_info["hrbp"].get("email"):
                hrbp_email = manager_info["hrbp"]["email"]
                potential_id = f"mgr_{hrbp_email}"
                if potential_id == manager_id:
                    manager = self._create_manager_from_email(hrbp_email, role="HRBP")
                    if manager:
                        self._managers_cache[manager_id] = manager
                        return manager
            
            # Check Hiring Manager
            if manager_info.get("hiring_manager") and manager_info["hiring_manager"].get("email"):
                hm_email = manager_info["hiring_manager"]["email"]
                potential_id = f"mgr_{hm_email}"
                if potential_id == manager_id:
                    manager = self._create_manager_from_email(hm_email, role="Hiring Manager")
                    if manager:
                        self._managers_cache[manager_id] = manager
                        return manager
            
            # Check Reporting Manager
            if manager_info.get("reporting_manager") and manager_info["reporting_manager"].get("email"):
                rm_email = manager_info["reporting_manager"]["email"]
                potential_id = f"mgr_{rm_email}"
                if potential_id == manager_id:
                    manager = self._create_manager_from_email(rm_email, role="Reporting Manager")
                    if manager:
                        self._managers_cache[manager_id] = manager
                        return manager
        
        return None
    
    def get_related_personas_for_candidate(self, candidate_id: str) -> Dict[str, Manager]:
        """
        Get related personas (managers) for a candidate from Darwin API.
        
        Returns:
            dict with keys: "hiring_manager", "reporting_manager", "hrbp" (if available)
            Note: Recruiter info is NOT available in Darwin API
        """
        # Cache keys
        hiring_manager_cache_key = f"hiring_manager_{candidate_id}"
        reporting_manager_cache_key = f"reporting_manager_{candidate_id}"
        hrbp_cache_key = f"hrbp_{candidate_id}"
        
        # Check cache first
        cached_result = {}
        if hiring_manager_cache_key in self._managers_cache:
            cached_result["hiring_manager"] = self._managers_cache[hiring_manager_cache_key]
        if reporting_manager_cache_key in self._managers_cache:
            cached_result["reporting_manager"] = self._managers_cache[reporting_manager_cache_key]
        if hrbp_cache_key in self._managers_cache:
            cached_result["hrbp"] = self._managers_cache[hrbp_cache_key]
        
        if cached_result:
            return cached_result
        
        result = {}
        
        # Get employee data from Darwin API
        try:
            employee_data = self.darwinbox_client.get_employee_by_id(candidate_id)
            
            if not employee_data:
                return result
            
            # Extract manager info from Darwin API
            manager_info = self.darwinbox_client.extract_manager_info(employee_data)
            
            # Create Manager entities from Darwin data
            # HRBP
            if manager_info.get("hrbp") and manager_info["hrbp"].get("email"):
                hrbp_data = manager_info["hrbp"]
                hrbp = self._create_manager_from_email(hrbp_data["email"], role="HRBP")
                if hrbp:
                    result["hrbp"] = hrbp
                    self._managers_cache[hrbp_cache_key] = hrbp
                    self._managers_cache[hrbp.id] = hrbp
            
            # Hiring Manager (from direct_manager)
            if manager_info.get("hiring_manager") and manager_info["hiring_manager"].get("email"):
                hm_data = manager_info["hiring_manager"]
                hiring_manager = self._create_manager_from_email(hm_data["email"], role="Hiring Manager")
                if hiring_manager:
                    result["hiring_manager"] = hiring_manager
                    self._managers_cache[hiring_manager_cache_key] = hiring_manager
                    self._managers_cache[hiring_manager.id] = hiring_manager
            
            # Reporting Manager (from direct_manager)
            if manager_info.get("reporting_manager") and manager_info["reporting_manager"].get("email"):
                rm_data = manager_info["reporting_manager"]
                reporting_manager = self._create_manager_from_email(rm_data["email"], role="Reporting Manager")
                if reporting_manager:
                    result["reporting_manager"] = reporting_manager
                    self._managers_cache[reporting_manager_cache_key] = reporting_manager
                    self._managers_cache[reporting_manager.id] = reporting_manager
                    
        except Exception as e:
            print(f"Error fetching personas from Darwin API: {e}")
            return result
        
        return result
    
    def get_candidate_documents(self, candidate_id: str) -> List[Dict[str, Any]]:
        """
        Get documents for a candidate.
        
        Note: Darwin API does not provide document information.
        This method is kept for compatibility but returns empty list.
        """
        return []
