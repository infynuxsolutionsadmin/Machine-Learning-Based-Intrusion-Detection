import React, { useState, useEffect } from 'react';
import { fetchPreventionSummary, fetchSimulationStatus, fetchRoutingPath } from '../services/apiService';
import { ShieldCheck, Lock, ShieldAlert, Network, ArrowRight, CheckCircle } from 'lucide-react';

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
    <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[50vh]">
      <div className="text-slate-500 font-medium text-lg flex items-center gap-3">
        <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-blue-600 animate-spin"></span>
        Loading prevention data...
      </div>
    </div>
  );
  
  if (error) return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10">
      <h3 className="text-lg font-bold text-red-800 mb-2 flex items-center gap-2">Unable to load data</h3>
      <p className="text-slate-500">{error}</p>
    </div>
  );

  if (!summary) return <div className="p-8 text-slate-500 font-medium">No prevention data available from the backend.</div>;

  const detectedNodes = [...new Set(summary.detected_low_trust_nodes || [])];
  const isolatedNodes = [...new Set(summary.blocked_or_restricted_nodes || [])];
  const groundTruthNodes = simStatus?.maliciousNodes || [];
  const totalNodes = simStatus?.nNodes || 'N/A';

  // Calculate detection result safely
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

  // Derive source and destination safely
  const sourceNode = simStatus?.source ?? routingPath?.source ?? summary?.source ?? 'N/A';
  const destNode = simStatus?.destination ?? routingPath?.destination ?? summary?.destination ?? 'N/A';

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      
      {/* 1. Page Header */}
      <div className="mb-8 border-b border-slate-200 pb-5">
        <h1 className="text-3xl font-black text-slate-800 flex items-center gap-3">
          <ShieldCheck className="w-8 h-8 text-blue-600" />
          Prevention Dashboard
        </h1>
        <p className="text-slate-500 font-medium text-lg mt-1">Trust-based routing and malicious node isolation</p>
      </div>

      {/* 2. Top Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Total Nodes</span>
          <p className="text-3xl font-bold text-slate-800">{totalNodes}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Detected Threats</span>
          <p className="text-3xl font-bold text-red-600">{detectedNodes.length}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Isolated Nodes</span>
          <p className="text-3xl font-bold text-red-600">{isolatedNodes.length}</p>
        </div>
        <div className="bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col justify-between">
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Prevention Status</span>
          <p className="text-xl font-bold text-emerald-600 mt-2">{summary.recovery_success ? "Active" : "Pending"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 3. Middle Left - Threat Analysis */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-5 flex flex-col">
          <h3 className="font-bold text-slate-800 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-red-500" /> Threat Analysis
          </h3>
          
          <div className="space-y-4 flex-grow">
            <div className="flex justify-between items-center py-2 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Ground Truth Attackers</span>
              <div className="flex gap-2">
                {groundTruthNodes.length > 0 ? (
                  groundTruthNodes.map(node => (
                    <span key={node} className="font-bold text-sm text-white bg-red-500 px-2.5 py-0.5 rounded shadow-sm">Node {node}</span>
                  ))
                ) : (
                  <span className="text-sm font-bold text-slate-400">None</span>
                )}
              </div>
            </div>
            
            <div className="flex justify-between items-center py-2 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">ML Detected Nodes</span>
              <div className="flex gap-2">
                {detectedNodes.length > 0 ? (
                  detectedNodes.map(node => (
                    <span key={node} className="font-bold text-sm text-white bg-red-500 px-2.5 py-0.5 rounded shadow-sm">Node {node}</span>
                  ))
                ) : (
                  <span className="text-sm font-bold text-slate-400">None</span>
                )}
              </div>
            </div>
            
            <div className="flex justify-between items-center py-2 border-b border-slate-50">
              <span className="text-sm font-medium text-slate-600">Detection Result</span>
              <span className={`font-bold text-sm ${
                detectionResult.includes('Match') && !detectionResult.includes('Mismatch') ? 'text-emerald-600' : 'text-red-600'
              }`}>
                {detectionResult}
              </span>
            </div>
          </div>
        </div>

        {/* 4. Middle Right - Prevention Action */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-5 flex flex-col justify-center">
          <h3 className="font-bold text-slate-800 flex items-center gap-2 mb-2">
            <Network className="w-5 h-5 text-indigo-500" /> Prevention Action
          </h3>
          
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between p-3.5 rounded-xl border bg-emerald-50 border-emerald-200">
              <span className="font-bold text-slate-700 text-sm">1. Detection</span>
              <span className="text-xs font-bold bg-white text-emerald-700 px-2 py-1 rounded shadow-sm">Completed</span>
            </div>
            
            <div className="flex items-center justify-between p-3.5 rounded-xl border bg-emerald-50 border-emerald-200">
              <span className="font-bold text-slate-700 text-sm">2. Isolation</span>
              <span className="text-xs font-bold bg-white text-emerald-700 px-2 py-1 rounded shadow-sm">{isolatedNodes.length > 0 ? 'Completed' : 'Skipped (No Threats)'}</span>
            </div>
            
            <div className="flex items-center justify-between p-3.5 rounded-xl border bg-emerald-50 border-emerald-200">
              <span className="font-bold text-slate-700 text-sm">3. Trust Evaluation</span>
              <span className="text-xs font-bold bg-white text-emerald-700 px-2 py-1 rounded shadow-sm">Completed</span>
            </div>
            
            <div className={`flex items-center justify-between p-3.5 rounded-xl border ${summary.recovery_success ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'}`}>
              <span className="font-bold text-slate-700 text-sm">4. Safe Routing</span>
              <span className={`text-xs font-bold bg-white px-2 py-1 rounded shadow-sm ${summary.recovery_success ? 'text-emerald-700' : 'text-slate-500'}`}>{summary.recovery_success ? 'Active' : 'Pending'}</span>
            </div>
          </div>
        </div>
        
        {/* 5. Bottom - Routing Outcome */}
        <div className="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200 grid grid-cols-1 md:grid-cols-[1fr_300px] overflow-hidden">
          
          <div className="p-6 space-y-5">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Network className="w-5 h-5 text-blue-500" /> Routing Outcome
            </h3>
            
            <div className="flex flex-col gap-0">
              <div className="flex items-center py-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Source Node</span>
                <span className="font-bold text-slate-800">{sourceNode}</span>
              </div>
              
              <div className="flex items-center py-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Destination Node</span>
                <span className="font-bold text-slate-800">{destNode}</span>
              </div>
              
              <div className="flex items-center py-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Safe Route</span>
                <div className="flex items-center gap-2 flex-wrap">
                  {routingPath?.route_nodes?.length > 0 ? (
                    routingPath.route_nodes.map((node, index) => (
                      <React.Fragment key={index}>
                        <span className="font-bold text-sm bg-blue-50 text-blue-700 border border-blue-100 px-2.5 py-1 rounded shadow-sm">{node}</span>
                        {index < routingPath.route_nodes.length - 1 && <ArrowRight className="w-4 h-4 text-slate-400" />}
                      </React.Fragment>
                    ))
                  ) : (
                    <span className="font-bold text-slate-500 bg-slate-100 px-3 py-1 rounded">Route unavailable</span>
                  )}
                </div>
              </div>
              
              <div className="flex items-center py-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600 w-36 flex-shrink-0">Routing Method</span>
                <span className="font-bold text-slate-700 text-sm leading-relaxed">{summary.routing_method || 'N/A'}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-50/50 p-6 border-t md:border-t-0 md:border-l border-slate-100 flex flex-col items-center justify-center space-y-6">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 self-start md:self-center w-full md:w-auto">
              <Lock className="w-5 h-5 text-slate-400 md:hidden" /> Route Recovery
            </h3>
            
            <div className={`relative w-32 h-32 rounded-full border-[8px] flex flex-col items-center justify-center bg-white shadow-sm ${summary.recovery_success ? 'border-emerald-500' : 'border-slate-200'}`}>
               {summary.recovery_success ? (
                 <>
                   <CheckCircle className="w-8 h-8 text-emerald-500 mb-1" />
                   <span className="font-bold text-emerald-700 text-sm">Successful</span>
                 </>
               ) : (
                 <span className="font-bold text-slate-500 text-sm">Pending</span>
               )}
            </div>
            
            <div className="text-center">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Recovery Status</div>
              <div className={`font-bold text-xs px-3 py-1.5 rounded-full inline-block border ${summary.recovery_success ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-white text-slate-600 border-slate-200'}`}>
                {summary.recovery_success ? 'Active Route Established' : 'Awaiting Resolution'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Prevention;
