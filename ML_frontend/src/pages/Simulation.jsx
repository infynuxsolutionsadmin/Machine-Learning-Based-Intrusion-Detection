import React, { useState, useEffect } from 'react';
import { 
  runSimulation, fetchSimulationStatus, fetchPreventionSummary, 
  fetchMetricsComparison, fetchDynamicTrust, fetchRoutingPath 
} from '../services/apiService';
import { 
  PlayCircle, AlertCircle, Loader2, Activity, 
  RefreshCw, Zap
} from 'lucide-react';

const Simulation = () => {
  const [nnodes, setNnodes] = useState(8);
  const [simulationTime, setSimulationTime] = useState(60.0);
  const [maliciousNodes, setMaliciousNodes] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successData, setSuccessData] = useState(null);
  
  // State for all dashboard-level statuses
  const [status, setStatus] = useState(null);
  const [preventionSummary, setPreventionSummary] = useState(null);
  const [metricsComp, setMetricsComp] = useState(null);
  const [dynamicTrust, setDynamicTrust] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);

  const loadData = async () => {
    try {
      const simRes = await fetchSimulationStatus();
      setStatus(simRes);
      if (simRes?.status === 'completed') {
        const [prevRes, metRes, trustRes, routeRes] = await Promise.allSettled([
          fetchPreventionSummary(),
          fetchMetricsComparison(),
          fetchDynamicTrust(),
          fetchRoutingPath()
        ]);
        if (prevRes.status === 'fulfilled') setPreventionSummary(prevRes.value);
        if (metRes.status === 'fulfilled') setMetricsComp(metRes.value);
        if (trustRes.status === 'fulfilled') setDynamicTrust(trustRes.value);
        if (routeRes.status === 'fulfilled') setRoutingPath(routeRes.value);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  const handleRun = async (e) => {
    e.preventDefault();
    if (nnodes <= 0 || simulationTime <= 0) {
      setError("Nodes and time must be greater than 0");
      return;
    }
    
    setLoading(true);
    setError(null);
    setSuccessData(null);
    
    // Reset pipeline states visually before new run
    setStatus({status: 'running'});
    
    try {
      const res = await runSimulation(parseInt(nnodes), parseFloat(simulationTime), maliciousNodes.trim());
      setSuccessData(res);
      await loadData(); // Reload all data after success
      window.dispatchEvent(new CustomEvent('simulation-completed'));
    } catch (err) {
      setError(err.message || "Failed to run simulation");
      setStatus(null); // Reset to allow viewing older data or show failed pipeline
    } finally {
      setLoading(false);
    }
  };

  const isCompleted = status?.status === 'completed';

  const renderStatusBadge = (state) => {
    if (state === 'completed' || state === 'safe_route_found' || state === true || state === 0) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-bold">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Completed
        </span>
      );
    }
    if (state === 'running') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-bold animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Running
        </span>
      );
    }
    if (state === 'failed' || state === false || state === 1) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-rose-100 text-rose-700 rounded-full text-xs font-bold">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> Failed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-3 py-1 bg-slate-100 text-slate-500 rounded-full text-xs font-bold">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Pending
      </span>
    );
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10 animate-in fade-in duration-300">
      
      {/* TOP ROW: CONFIG & STATUS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SIMULATION CONFIGURATION CARD */}
        <div className="dash-card p-6 rounded-3xl lg:col-span-2 self-start">
          <div className="flex items-center gap-2.5 mb-2">
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Zap className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-extrabold text-slate-900">
              Run WSL2 NS-3 Simulation
            </h2>
          </div>
          <p className="text-xs text-slate-500 mb-6 font-medium">Configure network topology parameters and execute simulation passes</p>
          
          <form onSubmit={handleRun} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Number of Nodes
                </label>
                <input 
                  type="number" 
                  value={nnodes} 
                  onChange={e => setNnodes(e.target.value)} 
                  className="w-full border border-slate-200 bg-slate-50/60 rounded-xl px-4 py-3 text-sm font-semibold text-slate-800 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all" 
                  min="1" 
                  required 
                  disabled={loading}
                />
                <p className="text-[11px] text-slate-400 mt-1.5">Total nodes deployed in MANET</p>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Malicious Nodes
                </label>
                <input 
                  type="text" 
                  value={maliciousNodes} 
                  onChange={e => setMaliciousNodes(e.target.value)} 
                  className="w-full border border-slate-200 bg-slate-50/60 rounded-xl px-4 py-3 text-sm font-semibold text-slate-800 focus:bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all placeholder:text-slate-400" 
                  placeholder="e.g. 2, 4" 
                  disabled={loading}
                />
                <p className="text-[11px] text-slate-400 mt-1.5">Comma-separated node IDs to act as attackers</p>
              </div>
            </div>
            
            <div className="pt-2 flex justify-end">
              <button 
                type="submit" 
                disabled={loading}
                className={`flex items-center gap-2 px-8 py-3.5 rounded-2xl font-bold text-sm transition-all cursor-pointer ${
                  loading 
                    ? 'bg-slate-200 text-slate-500 cursor-not-allowed shadow-inner' 
                    : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white shadow-md shadow-blue-500/25 active:scale-[0.99]'
                }`}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <PlayCircle className="w-5 h-5" />}
                {loading ? 'Running Simulation...' : 'Run Simulation'}
              </button>
            </div>
          </form>
        </div>

        {/* SIMULATION STATUS */}
        <div className="dash-card p-6 rounded-3xl lg:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-slate-100">
              <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Activity className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-extrabold text-slate-900">Status Overview</h2>
            </div>
            
            <div className="space-y-3.5">
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Run ID</span>
                <span className="text-xs font-mono text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md max-w-[120px] truncate" title={status?.run_id}>
                  {status?.run_id || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Status</span>
                {renderStatusBadge(status?.status)}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Source Node</span>
                <span className="font-bold text-slate-800">{status?.sourceNode !== undefined ? status.sourceNode : 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Destination</span>
                <span className="font-bold text-slate-800">{status?.destinationNode !== undefined ? status.destinationNode : 'N/A'}</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Pass 1 Status</span>
                {renderStatusBadge(isCompleted ? 'completed' : (status?.status === 'running' ? 'running' : 'pending'))}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Pass 2 Status</span>
                {renderStatusBadge(isCompleted ? 'completed' : (status?.status === 'running' ? 'pending' : 'pending'))}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Database Ingestion</span>
                {renderStatusBadge((status?.persistence?.core?.status === 'SUCCESS' || status?.persistence?.core?.status === 'ALREADY_INGESTED') ? 'completed' : (status?.status === 'running' ? 'running' : (isCompleted ? 'completed' : 'pending')))}
              </div>
              <div className="flex justify-between items-center text-sm py-1">
                <span className="font-medium text-slate-500">Final Validation</span>
                {renderStatusBadge(routingPath?.route_available === true ? 'completed' : (isCompleted && routingPath?.route_available === false ? 'failed' : 'pending'))}
              </div>
            </div>
          </div>

          <div className="mt-6 pt-3 border-t border-slate-100 text-center">
            <span className="text-[11px] font-semibold text-slate-400">
              Live NS-3 backend loop via WSL2
            </span>
          </div>
        </div>

      </div>

      {/* ERROR STATE */}
      {error && (
        <div className="dash-card border-rose-200 bg-rose-50/60 p-6 rounded-3xl flex items-start gap-4 shadow-sm">
          <div className="w-10 h-10 rounded-2xl bg-rose-100 text-rose-600 flex items-center justify-center shrink-0">
            <AlertCircle className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <h3 className="font-extrabold text-rose-900 text-base mb-1">Simulation failed</h3>
            <p className="text-slate-600 text-sm mb-4 leading-relaxed">{error}</p>
            <button 
              onClick={handleRun}
              className="flex items-center gap-2 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold rounded-xl transition-all shadow-xs cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" /> Retry Simulation
            </button>
          </div>
        </div>
      )}

    </div>
  );
};

export default Simulation;
