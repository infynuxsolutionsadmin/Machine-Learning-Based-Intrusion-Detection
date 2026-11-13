import React, { useState, useEffect } from 'react';
import { 
  fetchHealth, fetchSimulationStatus, fetchPreventionSummary, 
  fetchMetricsComparison, fetchDynamicTrust, fetchRoutingPath 
} from '../services/apiService';
import { 
  Activity, ShieldAlert, Network, Cpu, Route, 
  BarChart3, AlertCircle, ShieldCheck, Zap
} from 'lucide-react';

const Dashboard = () => {
  const [health, setHealth] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [preventionSummary, setPreventionSummary] = useState(null);
  const [metricsComp, setMetricsComp] = useState(null);
  const [dynamicTrust, setDynamicTrust] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const loadData = async () => {
    try {
      const [healthRes, simRes, prevRes, metRes, trustRes, routeRes] = await Promise.allSettled([
        fetchHealth(),
        fetchSimulationStatus(),
        fetchPreventionSummary(),
        fetchMetricsComparison(),
        fetchDynamicTrust(),
        fetchRoutingPath()
      ]);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value);
      if (prevRes.status === 'fulfilled') setPreventionSummary(prevRes.value);
      if (metRes.status === 'fulfilled') setMetricsComp(metRes.value);
      if (trustRes.status === 'fulfilled') setDynamicTrust(trustRes.value);
      if (routeRes.status === 'fulfilled') setRoutingPath(routeRes.value);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
      setRunning(false);
    }
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
        <p className="text-sm font-semibold text-slate-500">Loading Dashboard Data...</p>
      </div>
    );
  }

  const isConnected = health?.status === 'healthy';
  
  const handleRunSimulation = async () => {
    setRunning(true);
    window.location.href = '/simulation';
  };

  const totalNodes = simStatus?.nNodes ?? 'N/A';
  const maliciousNodes = simStatus?.maliciousNodes || [];
  const safeNodes = typeof totalNodes === 'number' ? totalNodes - maliciousNodes.length : 'N/A';
  const datasetRows = simStatus?.classical_ml?.dataset_rows ?? 'N/A';
  const sourceNode = simStatus?.sourceNode ?? 'N/A';
  const destNode = simStatus?.destinationNode ?? 'N/A';
  
  const detectedMalicious = [...new Set(preventionSummary?.detected_low_trust_nodes || [])];
  const forbiddenNodes = [...new Set(preventionSummary?.blocked_or_restricted_nodes || [])];
  
  const routeNodes = routingPath?.route_nodes || preventionSummary?.recovered_route || [];
  const selectedNextHop = routeNodes.length > 1 ? routeNodes[1] : 'N/A';
  const safeNeighbors = preventionSummary?.trust_scores ? Object.keys(preventionSummary.trust_scores).filter(n => !forbiddenNodes.includes(Number(n)) && Number(n) !== sourceNode) : [];

  const renderStatusBadge = (status) => {
    if (status === 'completed' || status === 'safe_route_found' || status === true) {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-bold">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> Completed
        </span>
      );
    }
    if (status === 'running') {
      return (
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-xs font-bold animate-pulse">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Running
        </span>
      );
    }
    if (status === 'failed' || status === false) {
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

  // Safe percentage calculation for circular graphic
  const safePercent = typeof totalNodes === 'number' && totalNodes > 0 
    ? Math.round((safeNodes / totalNodes) * 100) 
    : 100;

  return (
    <div className="space-y-6 pb-8 animate-in fade-in duration-300">
      
      {/* TOP SECTION: STAT CARDS + RADIAL BREAKDOWN (Reference Layout) */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: 4 Stats Cards (with Top Left Gradient Card) */}
        <div className="xl:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-5">
          
          {/* Card 1: Featured Gradient Card (DealDeck Blue Card Style) */}
          <div className="dash-card dash-card-hover bg-gradient-to-br from-[#3b5bf6] via-[#4355f6] to-[#5b4bf6] text-white p-6 rounded-3xl relative overflow-hidden shadow-lg shadow-blue-500/20 border-0 flex flex-col justify-between min-h-[170px]">
            {/* Soft decorative background circles */}
            <div className="absolute top-0 right-0 -mr-8 -mt-8 w-36 h-36 bg-white/10 rounded-full blur-xl pointer-events-none"></div>
            
            <div className="flex items-center justify-between relative z-10">
              <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 flex items-center justify-center text-white">
                <Network className="w-5 h-5 text-white" />
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-extrabold ${isConnected ? 'bg-emerald-400/20 text-emerald-200 border border-emerald-400/30' : 'bg-rose-400/20 text-rose-200 border border-rose-400/30'}`}>
                {isConnected ? '● Healthy' : '● Offline'}
              </span>
            </div>

            <div className="mt-4 relative z-10">
              <span className="text-xs font-semibold text-blue-100 uppercase tracking-wider block">Network Environment</span>
              <div className="text-3xl font-black text-white tracking-tight mt-0.5">
                {totalNodes} <span className="text-lg font-medium text-blue-100">Total Nodes</span>
              </div>
              <div className="text-xs text-blue-100/90 font-medium mt-1">
                Safe: <span className="font-bold text-white">{safeNodes}</span> • Malicious: <span className="font-bold text-white">{maliciousNodes.length}</span>
              </div>
            </div>
          </div>

          {/* Card 2: Safe Nodes (Clean White Card) */}
          <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[170px]">
            <div className="flex items-center justify-between">
              <div className="w-11 h-11 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-100 text-emerald-700">
                {safePercent}% Safe
              </span>
            </div>
            <div className="mt-4">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Operational Nodes</span>
              <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
                {safeNodes} <span className="text-sm font-medium text-slate-400">nodes</span>
              </div>
              <div className="text-xs text-slate-500 font-medium mt-1">
                Active in trusted topology
              </div>
            </div>
          </div>

          {/* Card 3: Malicious Nodes (Clean White Card with Red Pill) */}
          <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[170px]">
            <div className="flex items-center justify-between">
              <div className="w-11 h-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-rose-100 text-rose-700">
                {maliciousNodes.length > 0 ? `-${maliciousNodes.length} Detected` : '0 Threats'}
              </span>
            </div>
            <div className="mt-4">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Threat Vector</span>
              <div className="text-2xl font-black text-rose-600 tracking-tight mt-0.5 truncate" title={`[${maliciousNodes.join(', ')}]`}>
                {maliciousNodes.length > 0 ? `[${maliciousNodes.join(', ')}]` : 'None'}
              </div>
              <div className="text-xs text-slate-500 font-medium mt-1">
                Isolated from communication
              </div>
            </div>
          </div>

          {/* Card 4: Dataset & Routing (Clean White Card) */}
          <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[170px]">
            <div className="flex items-center justify-between">
              <div className="w-11 h-11 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Cpu className="w-5 h-5" />
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-blue-100 text-blue-700">
                Node {sourceNode} &rarr; {destNode}
              </span>
            </div>
            <div className="mt-4">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Dataset & Session</span>
              <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
                {datasetRows} <span className="text-sm font-medium text-slate-400">rows</span>
              </div>
              <div className="text-xs text-slate-500 font-medium mt-1 truncate">
                Route: <span className="font-semibold text-slate-700">{routeNodes.length > 0 ? routeNodes.join(' → ') : 'N/A'}</span>
              </div>
            </div>
          </div>

        </div>

        {/* Right Col: Concentric / Radial Statistics Card (Like Reference "Product Statistic") */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-extrabold text-slate-900 text-lg">Topology Statistic</h3>
                <p className="text-xs text-slate-400 font-medium">Track your network distribution</p>
              </div>
              <div className="px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">
                Live State
              </div>
            </div>

            {/* Concentric Circular Arcs Visualization */}
            <div className="flex items-center justify-center my-4 relative">
              <svg className="w-48 h-48 -rotate-90" viewBox="0 0 100 100">
                {/* Background tracks */}
                <circle cx="50" cy="50" r="40" fill="transparent" stroke="#f1f5f9" strokeWidth="6" />
                <circle cx="50" cy="50" r="30" fill="transparent" stroke="#f1f5f9" strokeWidth="6" />
                <circle cx="50" cy="50" r="20" fill="transparent" stroke="#f1f5f9" strokeWidth="6" />
                
                {/* Outer Ring: Safe Nodes (Blue) */}
                <circle 
                  cx="50" cy="50" r="40" 
                  fill="transparent" 
                  stroke="#3b5bf6" 
                  strokeWidth="6" 
                  strokeDasharray={`${(safePercent / 100) * 251.2} 251.2`}
                  strokeLinecap="round"
                />
                
                {/* Middle Ring: Malicious Nodes (Rose / Red) */}
                <circle 
                  cx="50" cy="50" r="30" 
                  fill="transparent" 
                  stroke="#ef4444" 
                  strokeWidth="6" 
                  strokeDasharray={`${typeof totalNodes === 'number' && totalNodes > 0 ? (maliciousNodes.length / totalNodes) * 188.4 : 0} 188.4`}
                  strokeLinecap="round"
                />
                
                {/* Inner Ring: Recovered Route Hops (Emerald) */}
                <circle 
                  cx="50" cy="50" r="20" 
                  fill="transparent" 
                  stroke="#10b981" 
                  strokeWidth="6" 
                  strokeDasharray={`${routeNodes.length > 0 ? 95 : 0} 125.6`}
                  strokeLinecap="round"
                />
              </svg>

              {/* Centered Statistic Number */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
                <span className="text-2xl font-black text-slate-900 leading-none">{totalNodes}</span>
                <span className="text-[8px] uppercase font-bold text-slate-400 mt-0.5">Nodes Active</span>
                <span className="mt-1 px-2 py-0.5 rounded-full text-[6px] font-bold bg-emerald-100 text-emerald-700">
                  {isConnected ? 'Optimal' : 'Offline'}
                </span>
              </div>
            </div>
          </div>

          {/* Breakdown Legend with Pills (matching Reference Image) */}
          <div className="space-y-2.5 pt-3 border-t border-slate-100">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                <span className="font-semibold text-slate-700">Safe Network Nodes</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">{safeNodes}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-700">
                  {safePercent}%
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                <span className="font-semibold text-slate-700">Isolated Malicious</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">{maliciousNodes.length}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-700">
                  {typeof totalNodes === 'number' && totalNodes > 0 ? ((maliciousNodes.length / totalNodes) * 100).toFixed(0) : 0}%
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span className="font-semibold text-slate-700">Active Route Hops</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-slate-900">{routeNodes.length > 0 ? routeNodes.length - 1 : 0}</span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-700">
                  Secured
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>

      {/* MIDDLE SECTION: SIMULATION & ML INTELLIGENCE */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Simulation Control & Status */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-slate-900">Simulation Status</h3>
                  <p className="text-xs text-slate-400">Current execution lifecycle</p>
                </div>
              </div>
              {renderStatusBadge(simStatus?.status)}
            </div>

            <div className="space-y-3.5 mb-6">
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Run ID</span>
                <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2.5 py-1 rounded-lg max-w-[200px] truncate" title={simStatus?.run_id}>
                  {simStatus?.run_id || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Pass 1 Status (Attack Simulation)</span>
                {renderStatusBadge(simStatus?.status === 'completed' ? 'completed' : 'pending')}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Pass 2 Status (Secured Simulation)</span>
                {renderStatusBadge(simStatus?.status === 'completed' ? 'completed' : 'pending')}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">WSL2 NS-3 Engine</span>
                <span className="font-bold text-xs text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg">
                  {isConnected ? 'Available' : 'Offline'}
                </span>
              </div>
            </div>
          </div>

          <button 
            onClick={handleRunSimulation}
            disabled={running || !isConnected}
            className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-slate-300 disabled:to-slate-400 text-white font-bold rounded-2xl shadow-md shadow-blue-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-[0.99]"
          >
            {running ? <Activity className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />} 
            {running ? 'Launching Simulation...' : 'Run New Simulation'}
          </button>
        </div>

        {/* ML & Threat Intelligence */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                  <Cpu className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-extrabold text-slate-900">ML & Anomaly Detection</h3>
                  <p className="text-xs text-slate-400">Classical ML and LSTM classification</p>
                </div>
              </div>
              <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700">
                Hybrid Architecture
              </span>
            </div>

            <div className="space-y-3.5">
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Classical ML Classifier</span>
                {renderStatusBadge(simStatus?.classical_ml?.status)}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">LSTM Temporal Trust Engine</span>
                {renderStatusBadge(dynamicTrust?.status)}
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Total Predictions</span>
                <span className="font-bold text-slate-800">{dynamicTrust?.nodes?.length || 'N/A'} nodes evaluated</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
                <span className="text-slate-500 font-medium">Detected Malicious</span>
                <span className="font-bold text-rose-600">[{detectedMalicious.join(', ')}]</span>
              </div>
              <div className="flex justify-between items-center text-sm py-1">
                <span className="text-slate-500 font-medium">Trust Scores Generation</span>
                {renderStatusBadge(preventionSummary?.trust_scores ? 'completed' : 'pending')}
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Model: <span className="font-semibold text-slate-700">RandomForest + LSTM</span></span>
            <span className="font-bold text-emerald-600">Automated Pipeline</span>
          </div>
        </div>

      </div>

      {/* LOWER SECTION: PREVENTION & ROUTE RECOVERY */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Prevention Status Card */}
        <div className="dash-card p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900">Prevention Status</h3>
                <p className="text-xs text-slate-400">Node isolation & restriction</p>
              </div>
            </div>
            {renderStatusBadge(preventionSummary?.recovery_success)}
          </div>

          <div className="space-y-3.5">
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Detected Threats</span>
              <span className="font-bold text-rose-600">[{detectedMalicious.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Forbidden Nodes</span>
              <span className="font-bold text-slate-800">[{forbiddenNodes.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Excluded Count</span>
              <span className="font-bold text-slate-800">{forbiddenNodes.length}</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1">
              <span className="text-slate-500 font-medium">Isolation State</span>
              <span className="font-bold text-emerald-600">
                {forbiddenNodes.length > 0 ? 'Enforced in NS-3' : 'Clear'}
              </span>
            </div>
          </div>
        </div>

        {/* Route Recovery Card */}
        <div className="dash-card p-6 rounded-3xl">
          <div className="flex items-center justify-between mb-5 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <Route className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900">Route Recovery</h3>
                <p className="text-xs text-slate-400">Safe multi-hop path selection</p>
              </div>
            </div>
            {renderStatusBadge(routingPath?.route_available)}
          </div>

          <div className="space-y-3.5">
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Route Request</span>
              <span className="font-bold text-slate-800">{sourceNode} &rarr; {destNode}</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Eligible Safe Neighbors</span>
              <span className="font-bold text-slate-800 truncate max-w-[200px]">[{safeNeighbors.join(', ')}]</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Selected Next Hop</span>
              <span className="font-bold text-blue-600">{selectedNextHop}</span>
            </div>
            <div className="flex justify-between items-center text-sm py-1">
              <span className="text-slate-500 font-medium">Recovered Safe Route</span>
              <span className="font-extrabold text-emerald-600">
                {routeNodes.length > 0 ? routeNodes.join(' → ') : 'None'}
              </span>
            </div>
          </div>
        </div>

      </div>

      {/* PERFORMANCE OVERVIEW (Reference Card & Bars Style) */}
      <div className="dash-card p-6 rounded-3xl">
        <div className="flex items-center justify-between mb-6 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900">Performance Overview</h3>
              <p className="text-xs text-slate-400">QoS comparison between attack and baseline</p>
            </div>
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">
            Baseline vs Attack
          </div>
        </div>
        
        {metricsComp?.baseline ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-4">
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Baseline PDR</p>
              <p className="text-xl font-black text-emerald-600">{metricsComp.baseline.pdr_percent?.toFixed(1)}%</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Attack PDR</p>
              <p className="text-xl font-black text-rose-600">{metricsComp.attack.pdr_percent?.toFixed(1)}%</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Baseline Delay</p>
              <p className="text-xl font-black text-slate-800">{metricsComp.baseline.mean_delay_ms?.toFixed(1)}ms</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Attack Delay</p>
              <p className="text-xl font-black text-slate-800">{metricsComp.attack.mean_delay_ms?.toFixed(1)}ms</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Base T-Put</p>
              <p className="text-xl font-black text-slate-800">{metricsComp.baseline.throughput_kbps?.toFixed(1)}k</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Attack T-Put</p>
              <p className="text-xl font-black text-slate-800">{metricsComp.attack.throughput_kbps?.toFixed(1)}k</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">Packet Loss</p>
              <p className="text-xl font-black text-rose-600">{metricsComp.attack.lost_packets}</p>
            </div>
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100/80">
              <p className="text-[11px] text-slate-400 font-bold uppercase mb-1">PDR Drop</p>
              <p className="text-xl font-black text-amber-500">{metricsComp.pdr_drop_percent?.toFixed(1)}%</p>
            </div>
          </div>
        ) : (
          <div className="p-8 text-center bg-slate-50 rounded-2xl text-slate-500 flex flex-col items-center justify-center">
             <AlertCircle className="w-8 h-8 mb-2 text-slate-300" />
             <p className="font-medium text-sm">Performance metrics not available yet. Run a simulation.</p>
          </div>
        )}
      </div>

    </div>
  );
};

export default Dashboard;
