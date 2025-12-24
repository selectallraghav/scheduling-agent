"""Mock Talent Recruit service for synthetic data."""

from datetime import date, timedelta
from typing import Optional

from models.entities import Candidate, Manager


class TalentRecruitClientMock:
    """Mock client for Talent Recruit API."""
    
    def __init__(self):
        """Initialize with synthetic data."""
        self._candidates = self._generate_candidates()
        self._managers = self._generate_managers()
    
    def _generate_candidates(self) -> list[Candidate]:
        """Generate synthetic candidates."""
        today = date.today()
        return [
            Candidate(
                id="cand_001",
                name="Rajesh Kumar",
                email="rajesh.kumar@example.com",
                role_title="Senior Software Engineer",
                location_timezone="Asia/Kolkata",
                start_date=today + timedelta(days=14),
                hiring_manager_id="mgr_001",
                reporting_manager_id="mgr_002"
            ),
            Candidate(
                id="cand_002",
                name="Priya Sharma",
                email="priya.sharma@example.com",
                role_title="Data Scientist",
                location_timezone="Asia/Kolkata",
                start_date=today + timedelta(days=21),
                hiring_manager_id="mgr_001",
                reporting_manager_id="mgr_003"
            ),
            Candidate(
                id="cand_003",
                name="Michael Chen",
                email="michael.chen@example.com",
                role_title="Product Manager",
                location_timezone="America/Los_Angeles",
                start_date=today + timedelta(days=10),
                hiring_manager_id="mgr_002",
                reporting_manager_id="mgr_002"
            ),
            Candidate(
                id="cand_004",
                name="Sarah Johnson",
                email="sarah.johnson@example.com",
                role_title="UX Designer",
                location_timezone="America/New_York",
                start_date=today + timedelta(days=18),
                hiring_manager_id="mgr_003",
                reporting_manager_id="mgr_001"
            ),
            Candidate(
                id="cand_005",
                name="Amit Patel",
                email="amit.patel@example.com",
                role_title="DevOps Engineer",
                location_timezone="Asia/Kolkata",
                start_date=today + timedelta(days=7),
                hiring_manager_id="mgr_002",
                reporting_manager_id="mgr_002"
            ),
            Candidate(
                id="cand_006",
                name="Emma Wilson",
                email="emma.wilson@example.com",
                role_title="Business Analyst",
                location_timezone="Europe/London",
                start_date=today + timedelta(days=25),
                hiring_manager_id="mgr_001",
                reporting_manager_id="mgr_003"
            ),
        ]
    
    def _generate_managers(self) -> list[Manager]:
        """Generate synthetic managers."""
        return [
            Manager(
                id="mgr_001",
                name="Vikram Singh",
                email="vikram.singh@apexon.com",
                role="Hiring Manager",
                location_timezone="Asia/Kolkata",
                calendar_ids={"apexon": "apexon_cal_001", "client": "client_cal_001"}
            ),
            Manager(
                id="mgr_002",
                name="David Thompson",
                email="david.thompson@apexon.com",
                role="Reporting Manager",
                location_timezone="America/Los_Angeles",
                calendar_ids={"apexon": "apexon_cal_002", "client": "client_cal_002"}
            ),
            Manager(
                id="mgr_003",
                name="Lisa Anderson",
                email="lisa.anderson@apexon.com",
                role="HRBP",
                location_timezone="America/New_York",
                calendar_ids={"apexon": "apexon_cal_003"}
            ),
            Manager(
                id="mgr_004",
                name="Anjali Mehta",
                email="anjali.mehta@apexon.com",
                role="Hiring Manager",
                location_timezone="Asia/Kolkata",
                calendar_ids={"apexon": "apexon_cal_004", "client": "client_cal_004"}
            ),
            Manager(
                id="mgr_005",
                name="James Wilson",
                email="james.wilson@apexon.com",
                role="Reporting Manager",
                location_timezone="Europe/London",
                calendar_ids={"apexon": "apexon_cal_005"}
            ),
        ]
    
    def get_candidate_by_id(self, candidate_id: str) -> Optional[Candidate]:
        """Get a candidate by ID."""
        for candidate in self._candidates:
            if candidate.id == candidate_id:
                return candidate
        return None
    
    def list_candidates(self) -> list[Candidate]:
        """List all candidates."""
        return self._candidates.copy()
    
    def get_manager_by_id(self, manager_id: str) -> Optional[Manager]:
        """Get a manager by ID."""
        for manager in self._managers:
            if manager.id == manager_id:
                return manager
        return None
    
    def get_related_personas_for_candidate(self, candidate_id: str) -> dict:
        """
        Get related personas (managers) for a candidate.
        
        Returns:
            dict with keys: "hiring_manager", "reporting_manager", "hrbp"
        """
        candidate = self.get_candidate_by_id(candidate_id)
        if not candidate:
            return {}
        
        result = {}
        
        hiring_manager = self.get_manager_by_id(candidate.hiring_manager_id)
        if hiring_manager:
            result["hiring_manager"] = hiring_manager
        
        reporting_manager = self.get_manager_by_id(candidate.reporting_manager_id)
        if reporting_manager:
            result["reporting_manager"] = reporting_manager
        
        # For now, assign HRBP based on candidate location or use a default
        # In real system, this would come from org structure
        hrbp = self.get_manager_by_id("mgr_003")  # Lisa Anderson
        if hrbp:
            result["hrbp"] = hrbp
        
        return result

