from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import random
import time
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.metrics.pairwise import cosine_similarity

from .data import LANGUAGES, corpus, digest

SEED = 20260929


class Baseline:
    def __init__(self, kind):
        self.kind = kind
        train = [row for row in corpus() if row["split"] == "train"]
        self.labels = sorted({row["expected"] for row in train})
        texts, targets = [r["text"] for r in train], [r["expected"] for r in train]
        start = time.perf_counter()
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", sublinear_tf=True, max_features=20000)
        vectors = self.vectorizer.fit_transform(texts)
        if kind == "nlp-linear":
            self.model = LogisticRegression(C=4, max_iter=600, random_state=SEED).fit(vectors, targets)
            self.labels = self.model.classes_.tolist()
        else:
            self.centroids = np.vstack([np.asarray(vectors[np.array(targets) == label].mean(axis=0)).ravel() for label in self.labels])
        self.setup_ms = (time.perf_counter() - start) * 1000

    def predict(self, text):
        start = time.perf_counter()
        vector = self.vectorizer.transform([text])
        if self.kind == "nlp-linear":
            scores = self.model.predict_proba(vector)[0]
        else:
            scores = cosine_similarity(vector, self.centroids)[0]
        idx = int(np.argmax(scores))
        return {"intent": self.labels[idx], "score": float(scores[idx]), "scores": dict(zip(self.labels, map(float, scores))), "score_kind": "uncalibrated_probability" if self.kind == "nlp-linear" else "cosine_similarity", "latency_ms": (time.perf_counter() - start) * 1000}


def metrics(rows, labels):
    actual, pred = [r["expected"] for r in rows], [r["intent"] for r in rows]
    return {"n": len(rows), "accuracy": accuracy_score(actual, pred), "macro_f1": f1_score(actual, pred, labels=labels, average="macro", zero_division=0), "balanced_accuracy": recall_score(actual, pred, labels=labels, average="macro", zero_division=0), "p50_ms": float(np.percentile([r["latency_ms"] for r in rows], 50)), "p95_ms": float(np.percentile([r["latency_ms"] for r in rows], 95))}


def run_benchmark():
    data = corpus()
    test = [r for r in data if r["split"] == "test"]
    random.Random(SEED).shuffle(test)
    results = []
    for kind in ("nlp-centroid", "nlp-linear"):
        model = Baseline(kind)
        cold = model.predict("Consulta de saldo")
        # No tests, labels or validation rows enter fit(). Warm-up stays outside timing samples.
        predictions = []
        for case in test:
            prediction = model.predict(case["text"])
            predictions.append({**case, **prediction, "correct": prediction["intent"] == case["expected"]})
        summary = metrics(predictions, model.labels)
        calibration = None
        if kind == "nlp-linear":
            probs = np.array([[r["scores"][label] for label in model.labels] for r in predictions])
            truth = np.array([[float(r["expected"] == label) for label in model.labels] for r in predictions])
            bins = []
            for index in range(10):
                members = [r for r in predictions if index / 10 <= r["score"] < (index + 1) / 10 or (index == 9 and r["score"] == 1)]
                if members:
                    bins.append({"n": len(members), "score": float(np.mean([r["score"] for r in members])), "accuracy": float(np.mean([r["correct"] for r in members]))})
            calibration = {"brier_multiclass": float(np.mean(np.sum((probs - truth) ** 2, axis=1))), "ece_10_bins": sum(b["n"] / len(test) * abs(b["accuracy"] - b["score"]) for b in bins), "bins": bins, "calibrated": False}
        results.append({"method": kind, **summary, "setup_ms": model.setup_ms, "first_inference_ms": cold["latency_ms"], "api_cost_usd": 0, "compute_cost_usd": None, "by_language": {lang: metrics([p for p in predictions if p["language"] == lang], model.labels) for lang in LANGUAGES}, "by_slice": {part: metrics([p for p in predictions if p["slice"] == part], model.labels) for part in ("standard", "challenge")}, "calibration": calibration, "confusion": {"labels": model.labels, "counts": confusion_matrix([r["expected"] for r in predictions], [r["intent"] for r in predictions], labels=model.labels).tolist()}, "predictions": predictions})
    return {"version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "seed": SEED, "corpus_sha256": digest(), "runner_sha256": hashlib.sha256(__import__("pathlib").Path(__file__).read_bytes()).hexdigest(), "machine": {"os": platform.platform(), "python": platform.python_version(), "processor": platform.processor(), "device": "CPU", "packages": {name: importlib.metadata.version(name) for name in ("scikit-learn", "numpy", "scipy")}}, "splits": {split: sum(r["split"] == split for r in data) for split in ("train", "validation", "test")}, "protocol": {"training": "catalog definitions + authored training families", "order": "fixed shuffled order, sequential inference, one measured call per case", "labels": "provisional, awaiting human review", "selection": "no hyperparameter selection on validation or test; configuration frozen in code", "latency": "local CPU; small sample, no concurrent load or network", "winner": None}, "methods": results, "pending": ["jev", "llm", "jev+llm"]}


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_benchmark()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "splits": report["splits"], "methods": [{k: m[k] for k in ("method", "accuracy", "macro_f1", "p95_ms")} for m in report["methods"]]}, ensure_ascii=False))
