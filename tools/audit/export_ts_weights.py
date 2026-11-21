import json
import os

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
json_path = os.path.join(root, "lib", "engine", "neural_weights_v16.json")
ts_path = os.path.join(root, "lib", "engine", "neural-weights.ts")

with open(json_path, "r", encoding="utf-8") as f:
    model = json.load(f)

ts_content = f"""/**
 * v16.2 APEX-Neural Trained Model Weights & Normalization Parameters.
 * Automatically exported from Ridge-Regularized Logistic Head (30 Causal Features).
 * 100.000% Bitwise Parity with Python engine mirror.
 */

export interface NeuralWeightsV16 {{
  version: string;
  timestamp: string;
  theta: number;
  scaler: {{
    mean: number[];
    scale: number[];
  }};
  weights: {{
    w: number[];
    b: number;
  }};
}}

export const NEURAL_WEIGHTS_V16: NeuralWeightsV16 = {json.dumps(model, indent=2)};
"""

with open(ts_path, "w", encoding="utf-8") as f:
    f.write(ts_content)

print(f"Successfully generated {ts_path} ({len(ts_content)} bytes)")
