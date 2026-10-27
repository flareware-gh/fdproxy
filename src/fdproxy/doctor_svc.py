"""Doctor command implementation."""

import sys
from typing import List

from fdproxy.config import get_supabase_url, get_supabase_service_role_key
from fdproxy.models import DoctorCheck
from fdproxy.timeutil import now_et, find_nearest_slot, is_rth


def run_checks() -> List[DoctorCheck]:
    """Run all doctor checks."""
    checks = []
    
    # Check Python version
    checks.append(check_python_version())
    
    # Check imports
    checks.append(check_yfinance_import())
    
    # Check environment variables
    checks.append(check_supabase_env())
    
    # Check Supabase connectivity (optional)
    checks.append(check_supabase_connectivity())
    
    # Check Yahoo connectivity
    checks.append(check_yahoo_connectivity())
    
    # Check time/slot info
    checks.append(check_time_info())
    
    return checks


def check_python_version() -> DoctorCheck:
    """Check Python version >= 3.11."""
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 11
    
    return DoctorCheck(
        name="python_version",
        ok=ok,
        detail=f"Python {version.major}.{version.minor}.{version.micro}" + 
               ("" if ok else " (requires >= 3.11)")
    )


def check_yfinance_import() -> DoctorCheck:
    """Check yfinance can be imported."""
    try:
        import yfinance
        return DoctorCheck(
            name="yfinance_import",
            ok=True,
            detail=f"yfinance {getattr(yfinance, '__version__', 'unknown')}"
        )
    except ImportError as e:
        return DoctorCheck(
            name="yfinance_import",
            ok=False,
            detail=f"Import failed: {e}"
        )


def check_supabase_env() -> DoctorCheck:
    """Check Supabase environment variables."""
    url = get_supabase_url()
    key = get_supabase_service_role_key()
    
    if url and key:
        # Mask key for display
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
        return DoctorCheck(
            name="supabase_env",
            ok=True,
            detail=f"URL: {url}, KEY: {masked_key}"
        )
    else:
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        
        return DoctorCheck(
            name="supabase_env",
            ok=False,
            detail=f"Missing: {', '.join(missing)}"
        )


def check_supabase_connectivity() -> DoctorCheck:
    """Test Supabase connectivity."""
    url = get_supabase_url()
    key = get_supabase_service_role_key()
    
    if not url or not key:
        return DoctorCheck(
            name="supabase_connectivity",
            ok=False,
            detail="Skipped (env not set)"
        )
    
    try:
        from fdproxy import db
        
        ping_ok = db.ping()
        if ping_ok:
            return DoctorCheck(
                name="supabase_connectivity",
                ok=True,
                detail="Connection successful"
            )
        else:
            return DoctorCheck(
                name="supabase_connectivity",
                ok=False,
                detail="Ping failed"
            )
    except Exception as e:
        return DoctorCheck(
            name="supabase_connectivity",
            ok=False,
            detail=f"Error: {e}"
        )


def check_yahoo_connectivity() -> DoctorCheck:
    """Test Yahoo Finance connectivity."""
    try:
        import yfinance as yf
        
        ticker = yf.Ticker("SPY")
        info = ticker.fast_info
        
        # Try to get current price
        last_price = getattr(info, 'last_price', None)
        
        if last_price:
            return DoctorCheck(
                name="yahoo_connectivity",
                ok=True,
                detail=f"SPY last: ${last_price:.2f}"
            )
        else:
            return DoctorCheck(
                name="yahoo_connectivity",
                ok=False,
                detail="Could not fetch SPY price"
            )
    except Exception as e:
        return DoctorCheck(
            name="yahoo_connectivity",
            ok=False,
            detail=f"Error: {e}"
        )


def check_time_info() -> DoctorCheck:
    """Check current ET time and slot info."""
    try:
        now = now_et()
        nearest_slot = find_nearest_slot(now)
        in_rth = is_rth(now)
        
        detail_parts = [
            f"ET: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"RTH: {in_rth}",
        ]
        
        if nearest_slot:
            detail_parts.append(f"Nearest slot: {nearest_slot}")
        else:
            detail_parts.append("No slot within ±5min")
        
        return DoctorCheck(
            name="time_info",
            ok=True,
            detail=", ".join(detail_parts)
        )
    except Exception as e:
        return DoctorCheck(
            name="time_info",
            ok=False,
            detail=f"Error: {e}"
        )
