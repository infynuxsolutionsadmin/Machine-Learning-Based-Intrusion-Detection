import React, { useState, useEffect } from 'react';
import { fetchPreventionSummary, fetchSimulationStatus, fetchRoutingPath } from '../services/apiService';
import { ShieldCheck, Lock, ShieldAlert, Network, ArrowRight, CheckCircle, Radio } from 'lucide-react';

const Prevention = () => {
  const [summary, setSummary] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    Promise.allSettled([
      fetchPreventionSummary(),
      fetchSimulationStatus(),
      fetchRoutingPath()
    ]).then(([sumRes, simRes, pathRes]) => {
      let anyError = false;
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value); else anyError = true;
      if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);

      if (anyError && !sumRes.value && !simRes.value) {
        setError("Unable to load data from backend.");
      }
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
      <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
      <p className="text-sm font-semibold text-slate-500">Loading Prevention Data...</p>
    </div>
  );
  
  if (error) return (
    <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
      <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load data</h3>
      <p className="text-sm text-slate-500">{error}</p>
    </div>
  );

  if (!summary) return (
    <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center text-slate-500 font-medium">
      No prevention data available from the backend. Run a simulation to generate prevention outcomes.
    </div>
  );

  const detectedNodes = [...new Set(summary.detected_low_trust_nodes || [])];
  const isolatedNodes = [...new Set(summary.blocked_or_restricted_nodes || [])];
  const groundTruthNodes = simStatus?.maliciousNodes || [];
  const totalNodes = simStatus?.nNodes || 'N/A';

  const detectedNodesSet = new Set(detectedNodes);
  let detectionResult = 'N/A';
  if (groundTruthNodes.length > 0 && detectedNodes.length > 0) {
    let matchCount = 0;
    groundTruthNodes.forEach(node => {
      if (detectedNodesSet.has(node)) matchCount++;
    });
    if (matchCount === groundTruthNodes.length && detectedNodes.length === groundTruthNodes.length) {
      detectionResult = 'Match';
    } else if (matchCount > 0) {
      detectionResult = 'Partial Match';
    } else {
      detectionResult = 'Mismatch';
    }
  } else if (groundTruthNodes.length === 0 && detectedNodes.length === 0) {
     detectionResult = 'Match (None)';
  } else if (groundTruthNodes.length > 0 && detectedNodes.length === 0) {
     detectionResult = 'Mismatch (Missed)';
  } else if (groundTruthNodes.length === 0 && detectedNodes.length > 0) {
     detectionResult = 'Mismatch (False Positives)';
  }

  const sourceNode = simStatus?.source ?? routingPath?.source ?? summary?.source ?? 'N/A';
  const destNode = simStatus?.destination ?? routingPath?.destination ?? summary?.destination ?? 'N/A';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      
      {/* Top 4 Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        
        {/* Total Nodes (Featured Gradient Card) */}
        <div className="dash-card dash-card-hover bg-gradient-to-br from-[#3b5bf6] to-[#5b4bf6] text-white p-6 rounded-3xl flex flex-col justify-between shadow-lg shadow-blue-500/20 border-0 min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-white/15 backdrop-blur-md border border-white/20 flex items-center justify-center text-white">
              <Network className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-white/20 text-white">
              MANET
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-blue-100 uppercase tracking-wider block">Total Topology Nodes</span>
            <div className="text-3xl font-black text-white tracking-tight mt-0.5">
              {totalNodes}
            </div>
            <div className="text-xs text-blue-100/90 font-medium mt-1">Network nodes monitored</div>
          </div>
        </div>

        {/* Detected Threats */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-rose-50 text-rose-600 flex items-center justify-center">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-rose-100 text-rose-700">
              Low Trust
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Detected Threats</span>
            <div className="text-3xl font-black text-rose-600 tracking-tight mt-0.5">
              {detectedNodes.length}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Classified as anomalous</div>
          </div>
        </div>

        {/* Isolated Nodes */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Lock className="w-5 h-5" />
            </div>
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-amber-100 text-amber-700">
              Enforced
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Isolated Nodes</span>
            <div className="text-3xl font-black text-slate-900 tracking-tight mt-0.5">
              {isolatedNodes.length}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Blocked from routing tree</div>
          </div>
        </div>

        {/* Prevention Status */}
        <div className="dash-card dash-card-hover p-6 rounded-3xl flex flex-col justify-between min-h-[160px]">
          <div className="flex items-center justify-between">
            <div className="w-11 h-11 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <span className={`px-3 py-1 rounded-full text-xs font-extrabold ${summary.recovery_success ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
              {summary.recovery_success ? 'Optimal' : 'Pending'}
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">Prevention Status</span>
            <div className="text-2xl font-black text-emerald-600 tracking-tight mt-0.5">
              {summary.recovery_success ? "Active Defense" : "Pending"}
            </div>
            <div className="text-xs text-slate-500 font-medium mt-1">Autonomous isolation loop</div>
          </div>
        </div>

      </div>

      {/* Middle Grid: Threat Analysis & Prevention Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Threat Analysis */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-slate-100">
              <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                <ShieldAlert className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900">Threat Analysis</h3>
                <p className="text-xs text-slate-400">Ground truth vs ML detection alignment</p>
              </div>
            </div>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center py-2 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-500">Ground Truth Attackers</span>
                <div className="flex gap-1.5 flex-wrap">
                  {groundTruthNodes.length > 0 ? (
                    groundTruthNodes.map(node => (
                      <span key={node} className="font-extrabold text-xs text-white bg-rose-500 px-2.5 py-1 rounded-full shadow-xs">
                        Node {node}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs font-bold text-slate-400">None</span>
                  )}
                </div>
              </div>
              
              <div className="flex justify-between items-center py-2 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-500">ML Detected Nodes</span>
                <div className="flex gap-1.5 flex-wrap">
                  {detectedNodes.length > 0 ? (
                    detectedNodes.map(node => (
                      <span key={node} className="font-extrabold text-xs text-white bg-rose-500 px-2.5 py-1 rounded-full shadow-xs">
                        Node {node}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs font-bold text-slate-400">None</span>
                  )}
                </div>
              </div>
              
              <div className="flex justify-between items-center py-2">
                <span className="text-sm font-medium text-slate-500">Detection Result</span>
                <span className={`px-3 py-1 rounded-full text-xs font-extrabold ${
                  detectionResult.includes('Match') && !detectionResult.includes('Mismatch') 
                    ? 'bg-emerald-100 text-emerald-700' 
                    : 'bg-rose-100 text-rose-700'
                }`}>
                  {detectionResult}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400">
            Node classification verified against attack simulation profile
          </div>
        </div>

        {/* Prevention Action */}
        <div className="dash-card p-6 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-5 pb-3 border-b border-slate-100">
              <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                <Network className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-extrabold text-slate-900">Prevention Pipeline</h3>
                <p className="text-xs text-slate-400">Stepwise execution lifecycle</p>
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <span className="font-bold text-slate-700 text-xs sm:text-sm">1. Anomaly Detection</span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">Completed</span>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <span className="font-bold text-slate-700 text-xs sm:text-sm">2. Malicious Isolation</span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
                  {isolatedNodes.length > 0 ? 'Completed' : 'Skipped (No Threats)'}
                </span>
              </div>
              
              <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <span className="font-bold text-slate-700 text-xs sm:text-sm">3. Trust Evaluation</span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">Completed</span>
              </div>
              
              <div className={`flex items-center justify-between p-3 rounded-2xl border ${summary.recovery_success ? 'bg-emerald-50/60 border-emerald-100' : 'bg-slate-50 border-slate-100'}`}>
                <span className="font-bold text-slate-700 text-xs sm:text-sm">4. Safe Trust Routing</span>
                <span className={`text-xs font-extrabold px-3 py-1 rounded-full ${summary.recovery_success ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                  {summary.recovery_success ? 'Active' : 'Pending'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400">
            Real-time policy enforcement applied to forward routing tables
          </div>
        </div>

      </div>
      
      {/* Bottom: Routing Outcome & Route Recovery */}
      <div className="dash-card rounded-3xl overflow-hidden grid grid-cols-1 md:grid-cols-[1fr_320px]">
        
        <div className="p-6 sm:p-8 space-y-5">
          <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100">
            <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Network className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900">Routing Outcome</h3>
              <p className="text-xs text-slate-400">Source to destination convergence</p>
            </div>
          </div>
          
          <div className="divide-y divide-slate-50 text-sm">
            <div className="flex items-center py-3">
              <span className="text-slate-500 font-medium w-40 shrink-0">Source Node</span>
              <span className="font-bold text-slate-900">{sourceNode}</span>
            </div>
            
            <div className="flex items-center py-3">
              <span className="text-slate-500 font-medium w-40 shrink-0">Destination Node</span>
              <span className="font-bold text-slate-900">{destNode}</span>
            </div>
            
            <div className="flex items-center py-3">
              <span className="text-slate-500 font-medium w-40 shrink-0">Safe Route</span>
              <div className="flex items-center gap-2 flex-wrap">
                {routingPath?.route_nodes?.length > 0 ? (
                  routingPath.route_nodes.map((node, index) => (
                    <React.Fragment key={index}>
                      <span className="font-bold text-xs bg-blue-50 text-blue-700 border border-blue-200 px-3 py-1 rounded-full shadow-2xs">
                        Node {node}
                      </span>
                      {index < routingPath.route_nodes.length - 1 && <ArrowRight className="w-3.5 h-3.5 text-slate-400" />}
                    </React.Fragment>
                  ))
                ) : (
                  <span className="font-bold text-xs text-slate-400 bg-slate-100 px-3 py-1 rounded-full">
                    Route unavailable
                  </span>
                )}
              </div>
            </div>
            
            <div className="flex items-center py-3">
              <span className="text-slate-500 font-medium w-40 shrink-0">Routing Method</span>
              <span className="font-bold text-slate-700 text-xs sm:text-sm">{summary.routing_method || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* Circular Route Recovery Indicator (Reference Ring Style) */}
        <div className="bg-slate-50/70 p-8 border-t md:border-t-0 md:border-l border-slate-100 flex flex-col items-center justify-center text-center space-y-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Route Recovery Status
          </div>
          
          <div className="relative w-32 h-32 flex items-center justify-center">
            {/* Concentric SVG Ring */}
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="transparent" stroke="#e2e8f0" strokeWidth="8" />
              <circle 
                cx="50" cy="50" r="42" 
                fill="transparent" 
                stroke={summary.recovery_success ? "#10b981" : "#94a3b8"} 
                strokeWidth="8" 
                strokeDasharray={`${summary.recovery_success ? 264 : 60} 264`}
                strokeLinecap="round"
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              {summary.recovery_success ? (
                <>
                  <CheckCircle className="w-8 h-8 text-emerald-500 mb-0.5" />
                  <span className="font-extrabold text-emerald-700 text-xs">Secured</span>
                </>
              ) : (
                <span className="font-bold text-slate-400 text-xs">Pending</span>
              )}
            </div>
          </div>
          
          <div>
            <div className={`font-extrabold text-xs px-3.5 py-1.5 rounded-full inline-block ${
              summary.recovery_success ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
            }`}>
              {summary.recovery_success ? 'Active Route Established' : 'Awaiting Resolution'}
            </div>
          </div>
        </div>

      </div>

    </div>
  );
};

export default Prevention;
