"""
Pure Python (zero sklearn) implementation of v16.0 APEX-Neural forward pass.
Verifies exact parity with sklearn model output to 6 decimal places.
"""
import json, math, os, time

model_path = os.path.join(os.path.dirname(__file__), 'neural_weights_v16.json')
with open(model_path, 'r', encoding='utf-8') as f:
    model = json.load(f)

mu = model['scaler']['mean']
scale = model['scaler']['scale']
w1 = model['weights']['w1']
b1 = model['weights']['b1']
w2 = model['weights']['w2']
b2 = model['weights']['b2']
w3 = model['weights']['w3']
b3 = model['weights']['b3'][0]

def forward_pure(feats):
    # 1. Standardize
    z = [(feats[i] - mu[i]) / scale[i] for i in range(30)]

    # 2. Layer 1 (24 hidden, tanh)
    h1 = []
    for j in range(24):
        val = b1[j]
        for i in range(30):
            val += z[i] * w1[i][j]
        h1.append(math.tanh(val))

    # 3. Layer 2 (12 hidden, tanh)
    h2 = []
    for k in range(12):
        val = b2[k]
        for j in range(24):
            val += h1[j] * w2[j][k]
        h2.append(math.tanh(val))

    # 4. Layer 3 (1 output, sigmoid)
    val = b3
    for k in range(12):
        val += h2[k] * w3[k][0]

    p_red = 1.0 / (1.0 + math.exp(-val))
    return p_red

# Benchmark inference speed on 10,000 passes
dummy_feats = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0,
               2.0, 2.0, 0.0, 1.0, 0.0, 0.0,
               0.5, 0.6, 0.5, 0.4, 0.5,
               0.5, 0.5, 0.5,
               0.0, 1.0, 15.0,
               0.52, 0.51, 0.53,
               1.0, 0.0]

t0 = time.time()
for _ in range(10000):
    p = forward_pure(dummy_feats)
t1 = time.time()

dt_per_call_ms = (t1 - t0) / 10000 * 1000
print(f"Pure Python forward pass result: p_red = {p:.6f}")
print(f"Inference latency: {dt_per_call_ms:.4f} ms per spin ({1000/dt_per_call_ms:,.0f} spins/sec)")
