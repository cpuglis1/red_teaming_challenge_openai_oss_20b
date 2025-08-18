"""
Example pipeline script for running synthetic + PII-mixed data generation.
"""
from src import generate_mixed_dataset

if __name__ == "__main__":
    out_path = generate_mixed_dataset(n_patients=5, include_non_pii=True, seed=123)
    print(f"Mixed dataset saved to: {out_path}")
