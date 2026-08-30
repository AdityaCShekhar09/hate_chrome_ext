import numpy as np

from backend.app import create_app


class FakeVectorizer:
    def __call__(self, values):
        return np.ones((len(values), 4))


class FakeModel:
    def __init__(self, score=0.8):
        self.score = score

    def predict(self, values, verbose=0):
        return np.full((len(values), 1), self.score)


def make_client(score=0.8, **config):
    app = create_app(model=FakeModel(score), vectorizer=FakeVectorizer())
    app.config.update(TESTING=True, **config)
    return app.test_client()


def test_health():
    response = make_client().get('/health')
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}


def test_test_endpoint_returns_model_score():
    response = make_client().post('/test', json={'text': 'example'})
    assert response.status_code == 200
    assert response.json['toxic'] is True
    assert response.json['score'] == 0.8


def test_detect_and_batch():
    client = make_client()
    assert client.post('/detect', json={'text': 'example'}).json == {'toxic': True}
    response = client.post('/detect-batch', json={'texts': ['one', 'two']})
    assert response.json == {'toxic': [True, True]}


def test_validation():
    client = make_client()
    assert client.post('/detect', json={}).status_code == 400
    assert client.post('/detect', json={'text': ''}).status_code == 400
    assert client.post('/detect-batch', json={'texts': []}).status_code == 400


def test_threshold_is_configurable():
    client = make_client(score=0.4, TOXICITY_THRESHOLD=0.3)
    response = client.post('/test', json={'text': 'example'})
    assert response.json['toxic'] is True
