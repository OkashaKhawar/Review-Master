"""
Review Master - Web Server Entry Point
======================================

Run this to start the web dashboard:
    python main.py

Then open http://127.0.0.1:8000 in your browser.

To run WhatsApp campaign:
    python run_campaign.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Start the web server."""
    try:
        import uvicorn
    except ImportError:
        print("Installing uvicorn...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uvicorn", "fastapi", "python-multipart", "-q"])
        import uvicorn
    
    print("\n" + "=" * 50)
    print("   Review Master - Web Dashboard")
    print("=" * 50)
    print("\n   Starting server at http://127.0.0.1:8000")
    print("   Press Ctrl+C to stop\n")
    
    uvicorn.run(
        "src.web.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()
