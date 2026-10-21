import requests
import time
import subprocess
import sys

def run_tests():
    print("Starting uvicorn server...")
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"])
    time.sleep(3) # Wait for server to start
    
    endpoints = [
        "/api/trust/scores",
        "/api/trust/prediction",
        "/api/ml/metrics"
    ]
    
    all_passed = True
    for endpoint in endpoints:
        url = f"http://127.0.0.1:8000{endpoint}"
        print(f"Testing {url}...")
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("  PASS (200 OK)")
                print(f"  Response: {str(response.json())[:100]}...")
            else:
                print(f"  FAIL (Status {response.status_code})")
                print(f"  Response: {response.text}")
                all_passed = False
        except Exception as e:
            print(f"  FAIL (Exception: {e})")
            all_passed = False
            
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED."))
    
    print("Terminating server...")
    server.terminate()
    server.wait()

if __name__ == "__main__":
    run_tests()
