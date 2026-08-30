from pathlib import Path
import json
import re

import numpy as np
import pandas as pd
import tensorflow as tf
from flask import Flask, jsonify, request
from flask_cors import CORS
from tensorflow.keras.layers import TextVectorization

BASE_DIR = Path(__file__).resolve().parent

MAX_FEATURES = 200000 # number of words in the vocab
VOCABULARY_PATH = BASE_DIR / 'vocabulary.json'

if not VOCABULARY_PATH.exists():
    raise FileNotFoundError(
        f'{VOCABULARY_PATH} is missing. Run '
        '`python build_vocabulary.py` from the backend directory first.'
    )

with VOCABULARY_PATH.open(encoding='utf-8') as vocabulary_file:
    vocabulary = json.load(vocabulary_file)

vectorizer = TextVectorization(max_tokens=MAX_FEATURES,
                               output_sequence_length=1800,
                               output_mode='int',
                               vocabulary=vocabulary)
app = Flask(__name__)
CORS(app)

model = tf.keras.models.load_model(BASE_DIR / 'toxicity.h5', compile=False)

def preprocess_text(text):
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def get_texts():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({'error': 'Request body must be JSON'}), 400)

    text = data.get('text')
    if not isinstance(text, str) or not text.strip():
        return None, (jsonify({'error': 'text must be a non-empty string'}), 400)
    if len(text) > 10000:
        return None, (jsonify({'error': 'text must be at most 10,000 characters'}), 413)
    return [text], None


def classify(texts):
    results, _ = classify_with_scores(texts)
    return results


def classify_with_scores(texts):
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
        results.append(score > 0.5)
        offset += sentence_count
    return results, scores


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/test', methods=['GET', 'POST'])
def test_model():
    if request.method == 'GET':
        text = request.args.get('text', 'This is a test message.')
        if not text.strip():
            return jsonify({'error': 'text must be a non-empty query parameter'}), 400
        if len(text) > 10000:
            return jsonify({'error': 'text must be at most 10,000 characters'}), 413
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
    if not isinstance(texts, list) or not texts or len(texts) > 100:
        return jsonify({'error': 'texts must be a non-empty list of at most 100 strings'}), 400
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        return jsonify({'error': 'every item in texts must be a non-empty string'}), 400
    if any(len(text) > 10000 for text in texts):
        return jsonify({'error': 'each text must be at most 10,000 characters'}), 413
    return jsonify({'toxic': classify(texts)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)
