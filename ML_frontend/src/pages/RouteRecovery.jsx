import React, { useState, useEffect } from 'react';
import { Route, ArrowRight, CheckCircle, XCircle, AlertCircle, Info, ShieldCheck } from 'lucide-react';
import { fetchPreventionSummary, fetchRoutingPath, fetchSimulationStatus } from '../services/apiService';

const RouteRecovery = () => {
  const [summary, setSummary] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    Promise.allSettled([
      fetchPreventionSummary(),
      fetchRoutingPath(),
      fetchSimulationStatus()
    ]).then(([sumRes, pathRes, simRes]) => {
      let anyError = false;
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;
      if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
      if (simRes.status === 'fulfilled') setSimStatus(simRes.value); else anyError = true;
      
      if (anyError && !sumRes.value && !pathRes.value) {
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
      <p className="text-sm font-semibold text-slate-500">Loading Route Data...</p>
    </div>
  );
  
  if (error) return (
    <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
      <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load data</h3>
      <p className="text-sm text-slate-500">{error}</p>
    </div>
  );

  if (!summary && !routingPath) return (
    <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center text-slate-500 font-medium">
      No route recovery data available from backend. Run a simulation to establish alternative routing.
    </div>
  );

  const afterNodes = routingPath?.route_nodes || [];
  const isRecoverySuccessful = summary?.recovery_success;
  const sourceNode = simStatus?.source ?? routingPath?.source ?? summary?.source ?? 'N/A';
  const destNode = simStatus?.destination ?? routingPath?.destination ?? summary?.destination ?? 'N/A';
  const routingMethod = summary?.routing_method || 'N/A';
  const maliciousNodesSet = new Set(simStatus?.maliciousNodes || []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      
      {/* Recovery Status Banner */}
      {isRecoverySuccessful === true && afterNodes.length > 0 ? (
        <div className="dash-card bg-emerald-50/80 border-emerald-200/80 p-5 rounded-3xl flex items-center justify-between gap-4 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-emerald-500 text-white flex items-center justify-center shadow-md shadow-emerald-500/25">
              <CheckCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-emerald-950 text-base">Route Recovery Successful</h3>
              <p className="text-xs text-emerald-700 font-medium">Autonomous trust-based routing has bypassed all detected malicious nodes</p>
            </div>
          </div>
          <span className="px-3.5 py-1.5 rounded-full text-xs font-black bg-emerald-600 text-white shadow-xs">
            Path Secured
          </span>
        </div>
      ) : isRecoverySuccessful !== undefined && afterNodes.length === 0 ? (
        <div className="dash-card bg-slate-50 p-5 rounded-3xl flex items-center gap-3 shadow-sm">
          <Info className="w-5 h-5 text-slate-500 shrink-0" />
          <h3 className="font-extrabold text-slate-800 text-sm">Recovery Status Available (Route Data Unavailable)</h3>
        </div>
      ) : isRecoverySuccessful === false ? (
        <div className="dash-card bg-rose-50/80 border-rose-200 p-5 rounded-3xl flex items-center gap-3 shadow-sm">
          <XCircle className="w-5 h-5 text-rose-600 shrink-0" />
          <h3 className="font-extrabold text-rose-900 text-sm">Recovery Failed or Not Required</h3>
        </div>
      ) : (
        <div className="dash-card bg-slate-50 p-5 rounded-3xl flex items-center gap-3 shadow-sm">
          <AlertCircle className="w-5 h-5 text-slate-400 shrink-0" />
          <h3 className="font-extrabold text-slate-600 text-sm">Route Status Unknown</h3>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Route Information Card */}
        <div className="dash-card p-6 sm:p-8 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2.5 mb-6 pb-3 border-b border-slate-100">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                <Route className="w-5 h-5" />
              </div>
              <h3 className="font-extrabold text-slate-900">Route Information</h3>
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
                  {afterNodes.length > 0 ? (
                    afterNodes.map((node, idx) => (
                      <React.Fragment key={idx}>
                        <span className="font-extrabold text-xs bg-emerald-50 text-emerald-800 border border-emerald-200 px-3 py-1 rounded-full shadow-2xs">
                          Node {node}
                        </span>
                        {idx < afterNodes.length - 1 && <ArrowRight className="w-3.5 h-3.5 text-slate-400" />}
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
                <span className="font-bold text-slate-700 text-xs sm:text-sm">{routingMethod}</span>
              </div>
              
              <div className="flex items-center py-3">
                <span className="text-slate-500 font-medium w-40 shrink-0">Recovery Status</span>
                <span className={`px-3 py-0.5 rounded-full text-xs font-extrabold ${isRecoverySuccessful ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                  {isRecoverySuccessful ? 'Successful' : 'Pending'}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-6 pt-3 border-t border-slate-100 text-xs text-slate-400">
            AODV dynamic neighbor recovery with trust factor weighting
          </div>
        </div>

        {/* Route Visualization Card */}
        <div className="dash-card p-6 sm:p-8 rounded-3xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-6 pb-3 border-b border-slate-100 flex-wrap gap-2">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <h3 className="font-extrabold text-slate-900">Route Flow Sequence</h3>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded-full bg-emerald-500"></div><span className="text-[11px] font-bold text-slate-500">Safe</span></div>
                <div className="flex items-center gap-1.5"><div className="w-2.5 h-2.5 rounded-full bg-rose-500"></div><span className="text-[11px] font-bold text-slate-500">Malicious</span></div>
              </div>
            </div>
            
            <div className="min-h-[220px] flex flex-col items-center justify-center bg-[#f8f9fe] rounded-2xl border border-slate-200/60 p-6 relative">
               {afterNodes.length > 0 ? (
                  <div className="w-full">
                    <div className="text-[11px] font-extrabold text-slate-400 uppercase tracking-wider text-center mb-6">
                      Sequential Safe Traversal
                    </div>
                    <div className="flex flex-wrap gap-x-2 gap-y-4 items-center justify-center">
                      {afterNodes.map((n, i) => {
                        const isMalicious = maliciousNodesSet.has(n);
                        return (
                          <React.Fragment key={i}>
                            <div className={`w-11 h-11 rounded-2xl border-2 flex items-center justify-center text-sm font-black shadow-xs z-10 transition-transform hover:scale-110 ${
                              isMalicious 
                                ? 'bg-rose-50 border-rose-300 text-rose-700' 
                                : 'bg-white border-emerald-500 text-emerald-800'
                            }`}>
                              {n}
                            </div>
                            {i < afterNodes.length - 1 && (
                              <div className="flex items-center">
                                <div className="h-1 w-6 sm:w-10 bg-emerald-300"></div>
                                <ArrowRight className="w-4 h-4 text-emerald-500 -ml-1.5" />
                              </div>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </div>
                  </div>
               ) : (
                  <div className="text-slate-400 text-sm font-semibold flex flex-col items-center gap-2">
                    <Route className="w-8 h-8 opacity-40 text-slate-400" />
                    <span>No active route sequence</span>
                  </div>
               )}
            </div>
          </div>

          <div className="mt-6 pt-3 border-t border-slate-100 text-center text-xs text-slate-400">
            End-to-end multi-hop connectivity verified
          </div>
        </div>
      </div>
    </div>
  );
};

export default RouteRecovery;
