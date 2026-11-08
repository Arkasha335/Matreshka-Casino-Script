import os, sys, math, json, glob
sys.path.append(os.path.dirname(__file__))
from run_config_matrix import run_simulation

def profile_apex(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (3000, 9), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2000, 9), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

def profile_turbo(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (3500, 9), 'TRANSITION': (1800, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (2500, 9), 'TRANSITION': (1500, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1500, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

def profile_shield(mode, b):
    if b >= 3_000_000:
        return {'ZEBRA': (2000, 10), 'TRANSITION': (1200, 10), 'DANGER': (1000, 10)}[mode]
    elif b >= 1_800_000:
        return {'ZEBRA': (1500, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]
    else:
        return {'ZEBRA': (1000, 10), 'TRANSITION': (1000, 10), 'DANGER': (1000, 10)}[mode]

print("="*75)
print("PROFILE: APEX_IDEAL")
run_simulation("APEX_IDEAL", profile_apex)
print("="*75)
print("PROFILE: TURBO_HARVEST")
run_simulation("TURBO_HARVEST", profile_turbo)
print("="*75)
print("PROFILE: SHIELD_CONSERVATIVE")
run_simulation("SHIELD_CONSERVATIVE", profile_shield)
print("="*75)
