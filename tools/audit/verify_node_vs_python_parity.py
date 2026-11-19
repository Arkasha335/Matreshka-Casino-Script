"""
Full Bitwise Verification of Node.js vs Python on 1,000+ real spin histories.
Directly tests:
Node.js: bot/engine_dist/prng-detector.js (PrngDetector.getRecommendationAndConfidence)
Python: tools/audit/engine_mirror.py (PrngDetectorMirror.get_recommendation_and_confidence)
"""
import json, math, os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'audit'))
from engine_mirror import PrngDetectorMirror
from audit_versions_head_to_head import load_all_unique_sessions

sessions = load_all_unique_sessions()
test_histories = []
for s in sessions:
    outs = s['outcomes']
    for i in range(4, min(len(outs), 100), 3):
        test_histories.append(outs[:i])

print(f"Testing {len(test_histories)} spin histories across all sessions for bitwise parity...")

py_results = []
for h in test_histories:
    rec, conf, state = PrngDetectorMirror.get_recommendation_and_confidence(h)
    py_results.append({
        'rec': rec,
        'conf': conf,
        'state': state
    })

# Save test histories for Node
input_path = os.path.join(os.path.dirname(__file__), 'parity_test_input.json')
with open(input_path, 'w', encoding='utf-8') as f:
    json.dump(test_histories, f)

# Node runner calling bot/engine_dist/prng-detector.js
node_script = """
const fs = require('fs');
const path = require('path');
const { PrngDetector } = require('../../bot/engine_dist/prng-detector');

const histories = JSON.parse(fs.readFileSync('tools/audit/parity_test_input.json', 'utf8'));
const results = histories.map(h => {
  const res = PrngDetector.getRecommendationAndConfidence(h.map(x => ({ outcome: x })));
  return {
    rec: res.recommendation,
    conf: res.confidence,
    state: res.state
  };
});

fs.writeFileSync('tools/audit/parity_test_output.json', JSON.stringify(results));
"""

node_script_path = os.path.join(os.path.dirname(__file__), 'run_node_parity.js')
with open(node_script_path, 'w', encoding='utf-8') as f:
    f.write(node_script)

res = subprocess.run(['node', node_script_path], capture_output=True, text=True)
if res.returncode != 0:
    print("Node error:", res.stderr)
    sys.exit(1)

with open(os.path.join(os.path.dirname(__file__), 'parity_test_output.json'), 'r', encoding='utf-8') as f:
    node_results = json.load(f)

mismatches = 0
for idx, (py, node) in enumerate(zip(py_results, node_results)):
    if py['rec'] != node['rec'] or py['conf'] != node['conf'] or py['state'] != node['state']:
        mismatches += 1
        if mismatches <= 5:
            print(f"Mismatch at history #{idx} (len {len(test_histories[idx])}):")
            print(f"  Python: {py}")
            print(f"  Node:   {node}")
            print(f"  Tail:   {test_histories[idx][-10:]}")

# Clean up temporary test files
for p in [input_path, node_script_path, os.path.join(os.path.dirname(__file__), 'parity_test_output.json')]:
    if os.path.exists(p): os.remove(p)

print(f"\nPARITY TEST RESULT: {len(test_histories)} tests, {mismatches} mismatches!")
if mismatches == 0:
    print(">>> 100.000% BITWISE PARITY CONFIRMED BETWEEN PYTHON AND NODE.JS! <<<")
else:
    print(f"FAILED with {mismatches} mismatches!")
    sys.exit(1)
