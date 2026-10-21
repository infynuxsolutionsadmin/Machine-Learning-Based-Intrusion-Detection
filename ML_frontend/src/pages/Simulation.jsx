import React, { useState, useEffect } from 'react';
import { 
  runSimulation, fetchSimulationStatus, fetchPreventionSummary, 
  fetchMetricsComparison, fetchDynamicTrust, fetchRoutingPath 
} from '../services/apiService';
import { PlayCircle, AlertCircle, CheckCircle, Loader2, Activity, ShieldAlert, Network, Cpu, Route, BarChart3, RefreshCw } from 'lucide-react';

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
    if (state === 'completed' || state === 'safe_route_found' || state === true || state === 0) return <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded text-xs font-bold uppercase">Completed</span>;
    if (state === 'running') return <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs font-bold uppercase">Running</span>;
    if (state === 'failed' || state === false || state === 1) return <span className="px-2 py-1 bg-red-100 text-red-700 rounded text-xs font-bold uppercase">Failed</span>;
    return <span className="px-2 py-1 bg-slate-100 text-slate-500 rounded text-xs font-bold uppercase">Pending</span>;
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-10 animate-in fade-in duration-500">
      
      {/* PAGE HEADER */}
      <div className="mb-8">
        <h1 className="text-3xl font-black text-slate-800">Simulation Control</h1>
        <p className="text-slate-500 mt-1">Configure and execute the ML-MANET network simulation</p>
      </div>

      {/* TOP ROW: CONFIG & STATUS */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* SIMULATION CONFIGURATION CARD */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 lg:col-span-2 self-start">
          <h2 className="text-lg font-bold text-slate-800 mb-2 flex items-center gap-2">
            Run WSL2 NS-3 Simulation
          </h2>
          <p className="text-sm text-slate-500 mb-6">Configure network parameters and start the simulation</p>
          
          <form onSubmit={handleRun} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Number of Nodes</label>
                <input 
                  type="number" 
                  value={nnodes} 
                  onChange={e => setNnodes(e.target.value)} 
                  className="w-full border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow" 
                  min="1" 
                  required 
                  disabled={loading}
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">Malicious Nodes</label>
                <input 
                  type="text" 
                  value={maliciousNodes} 
                  onChange={e => setMaliciousNodes(e.target.value)} 
                  className="w-full border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-blue-500 focus:outline-none transition-shadow" 
                  placeholder="e.g. 2, 4" 
                  disabled={loading}
                />
                <p className="text-xs text-slate-500 mt-1">Comma separated IDs</p>
              </div>
            </div>
            
            <div className="pt-2 flex justify-end">
              <button 
                type="submit" 
                disabled={loading}
                className={`flex items-center gap-2 px-8 py-3 rounded-xl font-bold transition-all ${loading ? 'bg-slate-300 text-slate-500 cursor-not-allowed shadow-inner' : 'bg-blue-600 hover:bg-blue-700 text-white shadow hover:shadow-lg'}`}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <PlayCircle className="w-5 h-5" />}
                {loading ? 'Running Simulation...' : 'Run Simulation'}
              </button>
            </div>
          </form>
        </div>

        {/* SIMULATION STATUS */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 lg:col-span-1 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Activity className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-bold text-slate-800">Status Overview</h2>
          </div>
          <div className="space-y-4 flex-1">
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Run ID</span>
              <span className="text-xs font-mono text-slate-500 max-w-[120px] truncate" title={status?.run_id}>{status?.run_id || 'N/A'}</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Status</span>
              {renderStatusBadge(status?.status)}
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Source</span>
              <span className="text-sm font-bold text-slate-800">{status?.sourceNode !== undefined ? status.sourceNode : 'N/A'}</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Destination</span>
              <span className="text-sm font-bold text-slate-800">{status?.destinationNode !== undefined ? status.destinationNode : 'N/A'}</span>
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Pass 1 Status</span>
              {renderStatusBadge(isCompleted ? 'completed' : (status?.status === 'running' ? 'running' : 'pending'))}
            </div>
            <div className="flex justify-between items-center pb-3 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Pass 2 Status</span>
              {renderStatusBadge(isCompleted ? 'completed' : (status?.status === 'running' ? 'pending' : 'pending'))}
            </div>
            <div className="flex justify-between items-center pb-2">
              <span className="text-sm font-medium text-slate-600">Final Validation</span>
              {renderStatusBadge(routingPath?.route_available === true ? 'completed' : (isCompleted && routingPath?.route_available === false ? 'failed' : 'pending'))}
            </div>
          </div>
        </div>

      </div>

      {/* ERROR STATE */}
      {error && (
        <div className="bg-white border-l-4 border-l-red-500 shadow-sm p-6 rounded-r-2xl flex items-start gap-4">
          <AlertCircle className="w-6 h-6 shrink-0 text-red-500 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-bold text-red-800 text-lg mb-1">Simulation failed</h3>
            <p className="text-slate-600 mb-4">{error}</p>
            <button 
              onClick={handleRun}
              className="flex items-center gap-2 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 text-sm font-bold rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4" /> Retry Simulation
            </button>
          </div>
        </div>
      )}

      {/* SUCCESS RESULT CARD */}
      {successData && (
        <div className="bg-emerald-50 border border-emerald-200 p-6 rounded-2xl shadow-sm">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-white shrink-0 shadow">
              <CheckCircle className="w-6 h-6" />
            </div>
            <h3 className="font-bold text-emerald-800 text-xl">Simulation completed successfully!</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 pt-4 border-t border-emerald-200/60">
            <div className="bg-white/60 p-3 rounded-lg border border-emerald-100">
              <p className="text-xs font-semibold uppercase text-emerald-700 mb-1">Nodes</p>
              <p className="font-black text-xl text-emerald-900">{successData.nNodes !== undefined ? successData.nNodes : nnodes}</p>
            </div>
            <div className="bg-white/60 p-3 rounded-lg border border-emerald-100">
              <p className="text-xs font-semibold uppercase text-emerald-700 mb-1">Malicious Nodes</p>
              <p className="font-black text-xl text-emerald-900">{status?.maliciousNodes?.length ? status.maliciousNodes.join(', ') : 'None'}</p>
            </div>
            <div className="bg-white/60 p-3 rounded-lg border border-emerald-100">
              <p className="text-xs font-semibold uppercase text-emerald-700 mb-1">Dataset Rows</p>
              <p className="font-black text-xl text-emerald-900">{status?.classical_ml?.dataset_rows !== undefined ? status.classical_ml.dataset_rows : 'Unavailable'}</p>
            </div>
            <div className="bg-white/60 p-3 rounded-lg border border-emerald-100">
              <p className="text-xs font-semibold uppercase text-emerald-700 mb-1">Duration</p>
              <p className="font-black text-xl text-emerald-900">{successData.duration_seconds !== undefined ? successData.duration_seconds.toFixed(2) + 's' : 'Unavailable'}</p>
            </div>
            <div className="bg-white/60 p-3 rounded-lg border border-emerald-100">
              <p className="text-xs font-semibold uppercase text-emerald-700 mb-1">Exit Code</p>
              <p className="font-black text-xl text-emerald-900">{successData.error ? 1 : 0}</p>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default Simulation;
