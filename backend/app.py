import json
import logging
import os
import re
import time
from pathlib import Path

import numpy as np
import tensorflow as tf
from flask import Flask, current_app, jsonify, request, send_from_directory
from flask_cors import CORS
from tensorflow.keras.layers import TextVectorization
from werkzeug.exceptions import HTTPException

BASE_DIR = Path(__file__).resolve().parent


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        })


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO').upper(), handlers=[handler])


def create_app(model=None, vectorizer=None):
    configure_logging()
    app = Flask(__name__)
    app.config.update({
        'MODEL': model,
        'VECTORIZER': vectorizer,
        'MODEL_PATH': Path(os.getenv('MODEL_PATH', BASE_DIR / 'toxicity.h5')),
        'VOCABULARY_PATH': Path(os.getenv('VOCABULARY_PATH', BASE_DIR / 'vocabulary.json')),
        'MAX_FEATURES': int(os.getenv('MAX_FEATURES', '200000')),
        'SEQUENCE_LENGTH': int(os.getenv('SEQUENCE_LENGTH', '1800')),
        'TOXICITY_THRESHOLD': float(os.getenv('TOXICITY_THRESHOLD', '0.5')),
        'MAX_TEXT_LENGTH': int(os.getenv('MAX_TEXT_LENGTH', '10000')),
        'MAX_BATCH_SIZE': int(os.getenv('MAX_BATCH_SIZE', '100')),
    })

    cors_origins = os.getenv('CORS_ORIGINS', '').strip()
    if cors_origins:
        CORS(app, origins=[origin.strip() for origin in cors_origins.split(',')])

    @app.before_request
    def start_timer():
        request.start_time = time.perf_counter()

    @app.after_request
    def log_request(response):
        duration_ms = (time.perf_counter() - request.start_time) * 1000
        app.logger.info('request_complete %s %s %.2fms', request.method,
                        request.path, duration_ms)
        response.headers['X-Request-Duration-Ms'] = f'{duration_ms:.2f}'
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception('request_failed')
        return jsonify({'error': 'Internal server error'}), 500

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({'status': 'ok'})

    @app.route('/openapi.yaml', methods=['GET'])
    def openapi():
        return send_from_directory(BASE_DIR.parent, 'openapi.yaml', mimetype='text/yaml')

    @app.route('/test', methods=['GET', 'POST'])
    def test_model():
        if request.method == 'GET':
            text = request.args.get('text', 'This is a test message.')
            try:
                validate_text(text)
            except ValueError as error:
                return jsonify({'error': str(error)}), 400
        else:
            texts, error = get_texts()
            if error:
                return error
            text = texts[0]
        toxic, scores = classify_with_scores([text])
        return jsonify({'status': 'ok', 'text': text, 'toxic': toxic[0], 'score': scores[0]})

    @app.route('/detect', methods=['POST'])
    def detect():
        texts, error = get_texts()
        if error:
            return error
        return jsonify({'toxic': classify(texts)[0]})

    @app.route('/detect-batch', methods=['POST'])
    def detect_batch():
        data = request.get_json(silent=True)
        texts = data.get('texts') if isinstance(data, dict) else None
        if not isinstance(texts, list) or not texts or len(texts) > current_app.config['MAX_BATCH_SIZE']:
            return jsonify({'error': f"texts must be a non-empty list of at most {current_app.config['MAX_BATCH_SIZE']} strings"}), 400
        try:
            for text in texts:
                validate_text(text)
        except ValueError as error:
            return jsonify({'error': str(error)}), 400
        if any(len(text) > current_app.config['MAX_TEXT_LENGTH'] for text in texts):
            return jsonify({'error': f"each text must be at most {current_app.config['MAX_TEXT_LENGTH']} characters"}), 413
        return jsonify({'toxic': classify(texts)})

    return app


def get_texts():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({'error': 'Request body must be JSON'}), 400)
    text = data.get('text')
    try:
        validate_text(text)
    except ValueError as error:
        return None, (jsonify({'error': str(error)}), 400)
    if len(text) > current_app.config['MAX_TEXT_LENGTH']:
        return None, (jsonify({'error': f"text must be at most {current_app.config['MAX_TEXT_LENGTH']} characters"}), 413)
    return [text], None


def validate_text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('text must be a non-empty string')


def get_inference_components():
    if current_app.config['MODEL'] is None:
        current_app.config['MODEL'] = tf.keras.models.load_model(
            current_app.config['MODEL_PATH'], compile=False)
    if current_app.config['VECTORIZER'] is None:
        vocabulary_path = current_app.config['VOCABULARY_PATH']
        if not vocabulary_path.exists():
            raise FileNotFoundError(f'{vocabulary_path} is missing')
        with vocabulary_path.open(encoding='utf-8') as vocabulary_file:
            vocabulary = json.load(vocabulary_file)
        current_app.config['VECTORIZER'] = TextVectorization(
            max_tokens=current_app.config['MAX_FEATURES'],
            output_sequence_length=current_app.config['SEQUENCE_LENGTH'],
            output_mode='int',
            vocabulary=vocabulary)
    return current_app.config['MODEL'], current_app.config['VECTORIZER']


def preprocess_text(text):
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def classify(texts):
    results, _ = classify_with_scores(texts)
    return results


def classify_with_scores(texts):
    model, vectorizer = get_inference_components()
    vectors = []
    sentence_counts = []
    for text in texts:
        sentences = preprocess_text(text)
        sentence_counts.append(len(sentences))
        vectors.append(np.vstack([vectorizer([sentence]) for sentence in sentences]))

    predictions = model.predict(np.vstack(vectors), verbose=0)
    results = []
    scores = []
    offset = 0
    for sentence_count in sentence_counts:
        sentence_predictions = predictions[offset:offset + sentence_count]
        sentence_scores = [float(np.asarray(prediction).reshape(-1)[0])
                           for prediction in sentence_predictions]
        score = max(sentence_scores)
        scores.append(score)
        results.append(score > current_app.config['TOXICITY_THRESHOLD'])
        offset += sentence_count
    return results, scores


app = create_app()

if __name__ == '__main__':
    app.run(host=os.getenv('HOST', '0.0.0.0'),
            port=int(os.getenv('PORT', '5050')))
