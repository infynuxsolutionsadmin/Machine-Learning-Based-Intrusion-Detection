import sys
import os

base_dir = r"C:\Users\divya\OneDrive\Desktop\ML_MANET\manet-backend"
sys.path.insert(0, base_dir)

from app.services.simulation_runner import run_simulation, current_simulation

print("Imports passed.")

res = run_simulation(nNodes=4, attackEnabled=True, maliciousNodes=[2], seed=42)
print("Simulation result:", res)
print("Current simulation state:", current_simulation.get("classical_ml"))
