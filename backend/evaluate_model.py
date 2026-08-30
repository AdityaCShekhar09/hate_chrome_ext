"""Evaluate the model against a labeled CSV and report false positives."""

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score)

from app import classify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Labeled CSV path')
    parser.add_argument('--text-column', default='comment_text')
    parser.add_argument('--label-column', default='toxic')
    parser.add_argument('--output-dir', default='evaluation')
    args = parser.parse_args()

    data = pd.read_csv(args.data)
    labels = data[args.label_column].astype(int).tolist()
    predictions = []
    for start in range(0, len(data), 100):
        predictions.extend(classify(data[args.text_column].iloc[start:start + 100].tolist()))
    predictions = [int(value) for value in predictions]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        'precision': precision_score(labels, predictions, zero_division=0),
        'recall': recall_score(labels, predictions, zero_division=0),
        'f1': f1_score(labels, predictions, zero_division=0),
        'confusion_matrix': confusion_matrix(labels, predictions).tolist(),
        'classification_report': classification_report(labels, predictions, zero_division=0, output_dict=True),
    }
    with (output_dir / 'metrics.json').open('w', encoding='utf-8') as file:
        json.dump(metrics, file, indent=2)
    data.assign(predicted=predictions).query(f'{args.label_column} == 0 and predicted == 1').to_csv(
        output_dir / 'false_positives.csv', index=False)
    print(json.dumps(metrics, indent=2))


if __name__ == '__main__':
    main()
