#!/usr/bin/env python3
"""
Patch lvl13.tech state.json: set projected_return=4.59 on bot13 current_strategy
(Fixes 0.0 that was stored from the original trade run)
"""
import os, json

ROOT = os.path.dirname(os.path.abspath(__file__))

state_path = os.path.join(ROOT, "Frontends", "lvl13.tech", "data", "state.json")
with open(state_path, "r", encoding="utf-8") as f:
    data = json.load(f)

strat = data["data"]["funds"]["bot13"].get("current_strategy", {})
old = strat.get("projected_return")
strat["projected_return"] = 4.59
data["data"]["funds"]["bot13"]["current_strategy"] = strat

with open(state_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print(f"  state.json: projected_return {old} -> 4.59")
print("Done.")
