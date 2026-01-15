"""
Utility functions for API request validation
"""
import re
from fastapi import HTTPException


def validate_run_id(run_id: str) -> str:
    """
    Validate simulation run_id format.
    
    Expected format: sim-YYYYMMDD-HHMMSS
    Example: sim-20251217-143025
    
    Args:
        run_id: Run ID string to validate
        
    Returns:
        The validated run_id
        
    Raises:
        HTTPException: If run_id format is invalid
    """
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    
    # Regex pattern for sim-YYYYMMDD-HHMMSS
    pattern = r'^sim-\d{8}-\d{6}$'
    
    if not re.match(pattern, run_id):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid run_id format. Expected 'sim-YYYYMMDD-HHMMSS', got '{run_id}'"
        )
    
    return run_id
