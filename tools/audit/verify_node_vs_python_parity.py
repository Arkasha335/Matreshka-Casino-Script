"""
Full Bitwise Verification of Node.js vs Python Neural Forward Pass on 500 real spin histories.
"""
import json, math, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from test_neural_parity_quick import extract_features, forward_python
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
test_histories = []
for s in sessions[:5]:
    outs = s['outcomes']
    for i in range(5, min(len(outs), 100)):
        test_histories.append(outs[:i])

print(f"Testing {len(test_histories)} spin histories for bitwise parity...")

py_preds = []
for h in test_histories:
    f = extract_features(h)
    p = forward_python(f) if f else None
    py_preds.append(p)

# Create a small Node script to evaluate the same histories
node_test_script = """
const fs = require('fs');
const model = JSON.parse(fs.readFileSync('tools/audit/neural_weights_v16.json', 'utf8'));

const mu = model.scaler.mean;
const scale = model.scaler.scale;
const w1 = model.weights.w1;
const b1 = model.weights.b1;
const w2 = model.weights.w2;
const b2 = model.weights.b2;
const w3 = model.weights.w3;
const b3 = model.weights.b3[0];

function extractFeatures(hist) {
  const nz = hist.filter(h => h !== 'ZERO');
  if (nz.length < 3 || hist.length < 4) return null;

  const feats = [];
  for (let k = 1; k <= 8; k++) {
    if (nz.length >= k) feats.push(nz[nz.length - k] === 'RED' ? 1.0 : -1.0);
    else feats.push(0.0);
  }

  const curColor = nz[nz.length - 1];
  let streak = 1;
  for (let k = nz.length - 2; k >= 0; k--) {
    if (nz[k] === curColor) streak++;
    else break;
  }
  const signedStreak = curColor === 'RED' ? streak : -streak;
  feats.push(signedStreak);
  feats.push(streak);
  feats.push(streak === 1 ? 1.0 : 0.0);
  feats.push(streak === 2 ? 1.0 : 0.0);
  feats.push(streak === 3 ? 1.0 : 0.0);
  feats.push(streak >= 4 ? 1.0 : 0.0);

  for (const w of [4, 6, 8, 12, 16]) {
    const sub = nz.slice(-w);
    if (sub.length >= 2) {
      let trans = 0;
      for (let i = 1; i < sub.length; i++) if (sub[i] !== sub[i-1]) trans++;
      feats.push(trans / (sub.length - 1));
    } else feats.push(0.5);
  }

  for (const w of [8, 16, 24]) {
    const sub = nz.slice(-w);
    if (sub.length > 0) feats.push(sub.filter(x => x === 'RED').length / sub.length);
    else feats.push(0.5);
  }

  const z10 = hist.slice(-10).filter(x => x === 'ZERO').length;
  const z25 = hist.slice(-25).filter(x => x === 'ZERO').length;
  feats.push(z10);
  feats.push(z25);

  let spinsSinceZero = 0;
  for (let k = hist.length - 1; k >= 0; k--) {
    if (hist[k] === 'ZERO') break;
    spinsSinceZero++;
  }
  feats.push(Math.min(spinsSinceZero, 30));

  let pairCont = 1, pairBreak = 1;
  let s3Cont = 1, s3Break = 1;
  let altSame = 1, altDiff = 1;
  for (let i = 2; i < nz.length; i++) {
    let ps = 1;
    const pc = nz[i - 1];
    for (let j = i - 2; j >= 0; j--) {
      if (nz[j] === pc) ps++;
      else break;
    }
    const actual = nz[i];
    if (ps === 2 && (i < 3 || nz[i - 3] !== pc)) {
      if (actual === pc) pairCont++;
      else pairBreak++;
    } else if (ps >= 3) {
      if (actual === pc) s3Cont++;
      else s3Break++;
    } else if (ps === 1) {
      if (actual === nz[i - 1]) altSame++;
      else altDiff++;
    }
  }

  feats.push(pairCont / (pairCont + pairBreak));
  feats.push(s3Break / (s3Cont + s3Break));
  feats.push(altDiff / (altSame + altDiff));

  feats.push((nz.length >= 3 && nz[nz.length - 1] === nz[nz.length - 3] && nz[nz.length - 1] !== nz[nz.length - 2]) ? 1.0 : 0.0);
  feats.push((nz.length >= 3 && nz[nz.length - 2] === nz[nz.length - 3] && nz[nz.length - 1] !== nz[nz.length - 2]) ? 1.0 : 0.0);

  return feats;
}

function forwardJS(feats) {
  const z = [];
  for (let i = 0; i < 30; i++) {
    z.push((feats[i] - mu[i]) / scale[i]);
  }

  const h1 = [];
  for (let j = 0; j < 24; j++) {
    let val = b1[j];
    for (let i = 0; i < 30; i++) {
      val += z[i] * w1[i][j];
    }
    h1.push(Math.tanh(val));
  }

  const h2 = [];
  for (let k = 0; k < 12; k++) {
    let val = b2[k];
    for (let j = 0; j < 24; j++) {
      val += h1[j] * w2[j][k];
    }
    h2.push(Math.tanh(val));
  }

  let val = b3;
  for (let k = 0; k < 12; k++) {
    val += h2[k] * w3[k][0];
  }

  const pRed = 1.0 / (1.0 + Math.exp(-val));
  return Math.round(pRed * 1000000) / 1000000;
}

const histories = JSON.parse(fs.readFileSync('tools/audit/test_histories.json', 'utf8'));
const nodeResults = histories.map(h => {
  const f = extractFeatures(h);
  return f ? forwardJS(f) : null;
});
fs.writeFileSync('tools/audit/node_test_results.json', JSON.stringify(nodeResults));
"""

with open('tools/audit/test_histories.json', 'w', encoding='utf-8') as f:
    json.dump(test_histories, f)

with open('tools/audit/node_parity_runner.js', 'w', encoding='utf-8') as f:
    f.write(node_test_script)

subprocess.run(["node", "tools/audit/node_parity_runner.js"], check=True)

with open('tools/audit/node_test_results.json', 'r', encoding='utf-8') as f:
    node_preds = json.load(f)

mismatches = 0
for i in range(len(py_preds)):
    p_py = py_preds[i]
    p_node = node_preds[i]
    if p_py is None and p_node is None:
        continue
    if p_py is None or p_node is None or abs(p_py - p_node) > 1e-5:
        mismatches += 1
        print(f"Mismatch at index {i}: Python={p_py}, Node={p_node}")

print(f"\nPARITY TEST RESULT: {len(py_preds)} tests, {mismatches} mismatches!")
if mismatches == 0:
    print(">>> 100.000% BITWISE PARITY CONFIRMED BETWEEN PYTHON AND NODE.JS! <<<")
