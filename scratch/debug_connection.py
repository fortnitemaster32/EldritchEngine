import requests
import sys

def debug_connection(url):
    print(f"Testing {url}...")
    try:
        response = requests.get(url, timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text[:100]}")
    except Exception as e:
        print(f"Error: {e}")

debug_connection("http://localhost:1234/v1/models")
debug_connection("http://127.0.0.1:1234/v1/models")
debug_connection("http://localhost:1234/v1")
