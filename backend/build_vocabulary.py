"""Build the inference vocabulary from the training comments once."""

import json
from pathlib import Path

import pandas as pd
import tensorflow as tf
from tensorflow.keras.layers import TextVectorization

BASE_DIR = Path(__file__).resolve().parent
MAX_FEATURES = 200000

comments_path = BASE_DIR / 'comments.csv'
vocabulary_path = BASE_DIR / 'vocabulary.json'

comments = pd.read_csv(comments_path)['comment_text']
vectorizer = TextVectorization(max_tokens=MAX_FEATURES,
                               output_sequence_length=1800,
                               output_mode='int')
vectorizer.adapt(comments.values)

with vocabulary_path.open('w', encoding='utf-8') as vocabulary_file:
    json.dump(vectorizer.get_vocabulary(), vocabulary_file, ensure_ascii=False)

print(f'Wrote {len(vectorizer.get_vocabulary())} tokens to {vocabulary_path}')
