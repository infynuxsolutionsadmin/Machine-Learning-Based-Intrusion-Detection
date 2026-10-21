import re
with open('C:\\Users\\divya\\OneDrive\\Desktop\\MANET\\manet-backend\\app\\services\\simulation_runner.py', 'r') as f:
    content = f.read()

# Fix get_wsl_cmd
wsl_replacement = """        def get_wsl_cmd(trust_file_arg="", malicious_override=None, route_trace_override=None):
            mal = malicious_override if malicious_override is not None else malicious_str
            rt_file = route_trace_override if route_trace_override else route_tr_name
            route_tr_dest_wsl = _win_to_wsl(os.path.join(DYNAMIC_RESULTS_DIR, rt_file))
            return (
                f"cd '{NS3_DIR_WSL}' && "
                f"./ns3 run 'scratch/manet-sim "
                f"--nNodes={nNodes} "
                f"--simulationTime=50.0 "
                f"--maliciousNode={mal} "
                f"--RngSeed={rng_seed} "
                f"--outputFile={xml_filename} "
                f"--traceFile={trace_filename} "
                f"--routeTraceFile={rt_file} "
                f"{trust_file_arg}' && "
                f"mkdir -p '{dyn_wsl_dir}' && "
"""
content = re.sub(r'        def get_wsl_cmd.*?f"mkdir -p \'{dyn_wsl_dir}\' && "', wsl_replacement, content, flags=re.DOTALL)

with open('C:\\Users\\divya\\OneDrive\\Desktop\\MANET\\manet-backend\\app\\services\\simulation_runner.py', 'w') as f:
    f.write(content)
