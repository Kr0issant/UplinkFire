import json
import requests

def dict_to_dpaste(data_dict: dict, expiry_days: int = 30) -> str:
    api_url = "https://dpaste.com/api/v2/"
    
    json_content = json.dumps(data_dict, indent=4)
    
    payload = {
        'content': json_content,
        'syntax': 'json',
        'expiry_days': expiry_days
    }
    
    headers = {'User-Agent': 'PythonDpasteV2Wrapper/1.0'}
    
    response = requests.post(api_url, data=payload, headers=headers)
    response.raise_for_status()
    
    return response.text.strip()


def dpaste_to_dict(dpaste_url: str) -> dict:
    if not dpaste_url.endswith(".txt"):
        dpaste_url = f"{dpaste_url.rstrip('/')}.txt"
        
    headers = {'User-Agent': 'PythonDpasteV2Wrapper/1.0'}
    
    response = requests.get(dpaste_url, headers=headers)
    response.raise_for_status()
    
    return json.loads(response.text)


a = {
    "text": "hello",
    3: [1, 2, 3],
    "yes": False
}
