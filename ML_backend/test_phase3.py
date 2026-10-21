import urllib.request
import urllib.error
import json
import time
import subprocess
import sys
import os

def test_endpoints():
    print("Starting uvicorn server...")
    # Start server in background
    venv_python = r"C:\Users\divya\OneDrive\Desktop\MANET\manet-backend\.venv\Scripts\python.exe"
    server_process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=r"C:\Users\divya\OneDrive\Desktop\MANET\manet-backend"
    )
    
    try:
        # Wait for server to start
        time.sleep(4)
        
        base_url = "http://127.0.0.1:8000"
        
        endpoints = [
            "/api/health",
            "/api/simulation/summary",
            "/api/network/nodes",
            "/api/security/malicious-nodes",
            "/api/routing",
            "/api/metrics",
            "/api/metrics/comparison"
        ]
        
        all_passed = True
        for ep in endpoints:
            url = f"{base_url}{ep}"
            print(f"Testing {url}...")
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as response:
                    status = response.getcode()
                    data = json.loads(response.read().decode('utf-8'))
                    if status == 200:
                        print(f"  PASS (200 OK)")
                        print(f"  Response: {str(data)[:100]}...")
                    else:
                        print(f"  FAIL ({status})")
                        print(f"  Response: {data}")
                        all_passed = False
            except urllib.error.HTTPError as e:
                print(f"  FAIL ({e.code})")
                try:
                    error_data = json.loads(e.read().decode('utf-8'))
                    print(f"  Response: {error_data}")
                except:
                    print(f"  Response: {e.read()}")
                all_passed = False
            except Exception as e:
                print(f"  ERROR: {str(e)}")
                all_passed = False
                
        if all_passed:
            print("\nALL TESTS PASSED!")
        else:
            print("\nSOME TESTS FAILED!")
            
    finally:
        print("Terminating server...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    test_endpoints()
