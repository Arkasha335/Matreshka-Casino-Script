import datetime
import json
import math
import os

p = r"d:\Downloads\matreshka_session_2026-11-12.json"
with open(p, "r", encoding="utf-8") as f:
    d = json.load(f)
logs = d["logs"]
t0 = logs[0]["timestamp"] / 1000.0
t1 = logs[-1]["timestamp"] / 1000.0
dt0 = datetime.datetime.fromtimestamp(t0, datetime.timezone.utc)
dt1 = datetime.datetime.fromtimestamp(t1, datetime.timezone.utc)
print(f"Start: {dt0.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"End:   {dt1.strftime('%Y-%m-%d %H:%M:%S')} UTC")
print(f"Minutes: {(t1 - t0) / 60:.2f}")

# Check minutes passing through :00
print(f"Start minute: {dt0.minute}, End minute: {dt1.minute}")
if dt0.hour != dt1.hour or dt0.minute > dt1.minute:
    print(f"Notice: Session crossed an hour boundary! {dt0.hour:02d}:xx -> {dt1.hour:02d}:xx")
