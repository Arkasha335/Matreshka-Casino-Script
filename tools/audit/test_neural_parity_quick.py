"""
Test Bitwise Parity of Neural Predictor between Node.js and Python.
"""
import json, math, os, subprocess

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

def extract_features(hist):
    nz = [h for h in hist if h != 'ZERO']
    if len(nz) < 3 or len(hist) < 4:
        return None

    feats = []
    for k in range(1, 9):
        if len(nz) >= k: feats.append(1.0 if nz[-k] == 'RED' else -1.0)
        else: feats.append(0.0)

    cur_color = nz[-1]
    streak = 1
    for k in range(len(nz) - 2, -1, -1):
        if nz[k] == cur_color: streak += 1
        else: break
    signed_streak = streak if cur_color == 'RED' else -streak
    feats.append(float(signed_streak))
    feats.append(float(streak))
    feats.append(1.0 if streak == 1 else 0.0)
    feats.append(1.0 if streak == 2 else 0.0)
    feats.append(1.0 if streak == 3 else 0.0)
    feats.append(1.0 if streak >= 4 else 0.0)

    for w in [4, 6, 8, 12, 16]:
        sub = nz[-w:]
        if len(sub) >= 2:
            trans = sum(1 for i in range(1, len(sub)) if sub[i] != sub[i-1])
            feats.append(trans / (len(sub) - 1))
        else: feats.append(0.5)

    for w in [8, 16, 24]:
        sub = nz[-w:]
        if sub: feats.append(sum(1 for x in sub if x == 'RED') / len(sub))
        else: feats.append(0.5)

    z10 = sum(1 for x in hist[-10:] if x == 'ZERO')
    z25 = sum(1 for x in hist[-25:] if x == 'ZERO')
    feats.append(float(z10))
    feats.append(float(z25))

    spins_since_zero = 0
    for k in range(len(hist) - 1, -1, -1):
        if hist[k] == 'ZERO': break
        spins_since_zero += 1
    feats.append(float(min(spins_since_zero, 30)))

    pair_cont, pair_break = 1, 1
    s3_cont, s3_break = 1, 1
    alt_same, alt_diff = 1, 1
    for i in range(2, len(nz)):
        ps = 1
        pc = nz[i - 1]
        for j in range(i - 2, -1, -1):
            if nz[j] == pc: ps += 1
            else: break
        actual = nz[i]
        if ps == 2 and (i < 3 or nz[i - 3] != pc):
            if actual == pc: pair_cont += 1
            else: pair_break += 1
        elif ps >= 3:
            if actual == pc: s3_cont += 1
            else: s3_break += 1
        elif ps == 1:
            if actual == nz[i - 1]: alt_same += 1
            else: alt_diff += 1

    feats.append(pair_cont / (pair_cont + pair_break))
    feats.append(s3_break / (s3_cont + s3_break))
    feats.append(alt_diff / (alt_same + alt_diff))

    feats.append(1.0 if (len(nz) >= 3 and nz[-1] == nz[-3] and nz[-1] != nz[-2]) else 0.0)
    feats.append(1.0 if (len(nz) >= 3 and nz[-2] == nz[-3] and nz[-1] != nz[-2]) else 0.0)

    return feats

def forward_python(feats):
    z = [(feats[i] - mu[i]) / scale[i] for i in range(30)]

    h1 = []
    for j in range(24):
        val = b1[j]
        for i in range(30):
            val += z[i] * w1[i][j]
        h1.append(math.tanh(val))

    h2 = []
    for k in range(12):
        val = b2[k]
        for j in range(24):
            val += h1[j] * w2[j][k]
        h2.append(math.tanh(val))

    val = b3
    for k in range(12):
        val += h2[k] * w3[k][0]

    p_red = 1.0 / (1.0 + math.exp(-val))
    return round(p_red, 6)

print("Python forward pass works.")
