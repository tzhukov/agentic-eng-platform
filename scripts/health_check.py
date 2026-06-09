import requests
import time
import sys

SERVICES = {
    "LangFuse": "http://localhost:3000/api/public/health",
    "Qdrant": "http://localhost:6333/healthz"
}
TIMEOUT = 120 # 2 minutes

def check_services():
    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        all_healthy = True
        for name, url in SERVICES.items():
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    print(f"{name} returned {resp.status_code}")
                    all_healthy = False
            except requests.exceptions.RequestException:
                print(f"{name} is not reachable yet...")
                all_healthy = False
        
        if all_healthy:
            print("All services healthy!")
            sys.exit(0)
        
        time.sleep(5)
    
    print("Health check timed out after 120 seconds.")
    sys.exit(1)

if __name__ == "__main__":
    check_services()
