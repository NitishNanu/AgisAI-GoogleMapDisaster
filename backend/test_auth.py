import json
import urllib.error
import urllib.request

url = 'http://127.0.0.1:8000/api/v1/auth/register'
data = json.dumps({
    'name': 'Commander Alpha',
    'email': 'commander@aegis.local',
    'password': 'Password123!',
    'role': 'COMMANDER'
}).encode('utf-8')

req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTPError:", e.code)
    print("Error Body:", e.read().decode('utf-8'))
