import pandas as pd
from flask import Flask, request, jsonify
import re
from flask_cors import CORS
import tensorflow as tf
import numpy as np
from tensorflow.keras.layers import TextVectorization

df = pd.read_csv('comments.csv')
X = df['comment_text']

MAX_FEATURES = 200000 # number of words in the vocab

vectorizer = TextVectorization(max_tokens=MAX_FEATURES,
                               output_sequence_length=1800,
                               output_mode='int')

vectorizer.adapt(X.values)
app = Flask(__name__)
CORS(app)

model = tf.keras.models.load_model('toxicity.h5')

def preprocess_text(text):
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)
    return sentences

@app.route('/detect', methods=['POST'])
def detect():
    data = request.get_json()
    text = data['text']
    
    sentences = preprocess_text(text)
    preprocessed_sentences = [vectorizer([sentence]) for sentence in sentences]

    # Predict toxicity for all sentences in one batch
    predictions = model.predict(np.vstack(preprocessed_sentences))
    is_toxic = any(prediction[0] > 0.5 for prediction in predictions)  # Adjust based on your model's output shape

    return jsonify({'toxic': is_toxic})

@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.get_json()
    text = data['text']
    
    preprocessed_sentences = vectorizer([text])

    # Predict toxicity for all sentences in one batch
    predictions = model.predict(np.vstack(preprocessed_sentences))
    is_toxic = any(prediction[0] > 0.5 for prediction in predictions)
    print(is_toxic)

    return jsonify({"message": "Text received", "text": is_toxic})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)