# tests/test_benchmark.py
import pytest
from tests.benchmark import BENCHMARK_SPLITS, compute_metrics


def test_benchmark_splits_structure():
    """Verify all benchmark splits (VRSBench, RSVQA, CDVQA) are defined with necessary fields."""
    expected = {"VRSBench", "RSVQA", "CDVQA"}
    assert expected.issubset(set(BENCHMARK_SPLITS.keys()))

    for split_name, samples in BENCHMARK_SPLITS.items():
        assert len(samples) > 0
        for s in samples:
            assert "query" in s
            assert "images" in s
            assert "ground_truth" in s
            assert "expected_task" in s


def test_compute_metrics_calculation():
    """Verify accuracy, F1, and latency calculation metrics."""
    mock_preds = [
        {
            "routing_correct": True,
            "predicted_answer": "Dense vegetation and forest",
            "ground_truth": "vegetation",
            "confidence": 0.90,
            "latency_ms": 120.0
        },
        {
            "routing_correct": True,
            "predicted_answer": "Water channel visible",
            "ground_truth": "water",
            "confidence": 0.85,
            "latency_ms": 110.0
        },
        {
            "routing_correct": False,
            "predicted_answer": "Nothing found",
            "ground_truth": "building",
            "confidence": 0.70,
            "latency_ms": 130.0
        }
    ]

    metrics = compute_metrics(mock_preds)
    assert metrics["total_samples"] == 3
    assert abs(metrics["routing_accuracy"] - (2 / 3)) < 1e-3
    assert metrics["average_latency_ms"] == 120.0
    assert metrics["mean_f1"] > 0.0
