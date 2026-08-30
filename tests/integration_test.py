import json
import os
import urllib.request


BASE_URL = os.getenv('API_URL', 'http://127.0.0.1:5050')


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f'{BASE_URL}{path}', data=data,
        headers={'Content-Type': 'application/json'} if data else {})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, json.loads(response.read())


def test_compose_health_and_model():
    status, health = request('/health')
    assert status == 200 and health['status'] == 'ok'
    status, result = request('/test', {'text': 'Docker integration test'})
    assert status == 200
    assert result['status'] == 'ok'
    assert isinstance(result['score'], float)
