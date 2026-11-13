import React, { useState, useEffect } from 'react';
import { fetchPreventionSummary, fetchSimulationStatus, fetchRoutingPath, fetchNetworkNodes } from '../services/apiService';
import { Radio } from 'lucide-react';

const NetworkTopology = () => {
  const [summary, setSummary] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [networkNodes, setNetworkNodes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadData = () => {
    Promise.all([fetchPreventionSummary(), fetchSimulationStatus(), fetchRoutingPath(), fetchNetworkNodes()])
      .then(([summaryData, statusData, routingData, networkData]) => {
        setSummary(summaryData);
        setSimStatus(statusData);
        setRoutingPath(routingData);
        setNetworkNodes(networkData);
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    window.addEventListener('simulation-completed', loadData);
    return () => window.removeEventListener('simulation-completed', loadData);
  }, []);

  if (loading) return (
    <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
      <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
      <p className="text-sm font-semibold text-slate-500">Loading Network Topology...</p>
    </div>
  );
  
  if (error) return (
    <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
      <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load network topology</h3>
      <p className="text-sm text-slate-500">{error}</p>
    </div>
  );
  
  if (!simStatus || simStatus.status !== 'completed') return (
    <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center">
      <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
        <Radio className="w-6 h-6" />
      </div>
      <p className="text-slate-900 font-extrabold text-lg mb-1">No completed simulation data available</p>
      <p className="text-sm text-slate-500">Run a simulation from the Simulation Control tab to render the interactive network graph.</p>
    </div>
  );

  const sourceNode = simStatus?.sourceNode ?? 0;
  const destNode = simStatus?.destinationNode ?? (simStatus?.nNodes ? simStatus.nNodes - 1 : 9);
  
  const isMalicious = (id) => simStatus?.maliciousNodes?.includes(id);
  const pathNodes = routingPath?.route_nodes || summary?.recovered_route || [];
  const isRouteNode = (id) => pathNodes.includes(id);

  const nNodes = simStatus?.nNodes || 0;
  const maliciousCount = simStatus?.maliciousNodes?.length || 0;
  const safeNodesCount = Math.max(0, nNodes - maliciousCount);
  
  // Render ALL nodes 0 to nNodes - 1
  const allNodes = Array.from({ length: nNodes }, (_, i) => i);

  // Stable Graph Node Positioning using a distributed MANET-style layout
  const getPos = (id) => {
    const posMap = {
      0: { left: 10, top: 50 },  // Source Node (Far Left)
      5: { left: 22, top: 22 },  // Top Row (Malicious)
      8: { left: 50, top: 20 },  // Top Row
      4: { left: 78, top: 22 },  // Top Row
      2: { left: 35, top: 50 },  // Route Node
      3: { left: 65, top: 50 },  // Route Node
      6: { left: 22, top: 78 },  // Bottom Row
      1: { left: 50, top: 80 },  // Bottom Row (Malicious)
      7: { left: 78, top: 78 },  // Bottom Row
      9: { left: 90, top: 50 },  // Destination Node (Far Right)
    };
    
    if (posMap[id]) return posMap[id];
    
    // Fallback for any dynamic additional nodes > 9
    const cols = Math.ceil(Math.sqrt(Math.max(1, nNodes - 10)));
    const row = Math.floor((id - 10) / cols);
    const col = (id - 10) % cols;
    return { 
      left: 20 + (col * 15) % 60, 
      top: 15 + (row * 15) % 70 
    };
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      <style>{`
        @keyframes routeFlow {
          from { stroke-dashoffset: 24; }
          to { stroke-dashoffset: 0; }
        }
        .animate-route-flow {
          animation: routeFlow 0.8s linear infinite;
        }
      `}</style>

      {/* Summary Banner */}
      <div className="dash-card p-5 rounded-3xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-md shadow-blue-500/25">
            <Radio className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-extrabold text-slate-900 text-base">Distributed MANET Topology</h2>
            <p className="text-xs text-slate-500">
              {nNodes} nodes deployed • {maliciousCount} attackers isolated • Safe route: <span className="font-bold text-emerald-600">{pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">
            Source: Node {sourceNode}
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-purple-100 text-purple-700">
            Dest: Node {destNode}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Network Map */}
        <div className="lg:col-span-2 dash-card rounded-3xl overflow-hidden relative min-h-[560px] flex items-center justify-center p-8 bg-white">
           {/* Subtle high-end grid canvas background */}
           <div className="absolute inset-0 opacity-40 bg-[radial-gradient(#cbd5e1_1px,transparent_1px)] [background-size:24px_24px]"></div>
           
           <div className="relative z-10 w-full h-full flex flex-col items-center justify-center">
             
             <div className="relative w-full max-w-3xl aspect-video md:aspect-[21/9]">
               {/* Base/Background Edges (Subtle) */}
               <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-visible">
                 {(() => {
                   let knownEdges = networkNodes?.network_edges || simStatus?.edges || summary?.edges || routingPath?.edges || routingPath?.network_edges;
                   
                   if (!knownEdges && summary?.trust_scores) {
                     knownEdges = [];
                     const seen = new Set();
                     Object.entries(summary.trust_scores).forEach(([u, neighbors]) => {
                       Object.keys(neighbors).forEach(v => {
                         const edgeKey = [parseInt(u), parseInt(v)].sort().join('-');
                         if (!seen.has(edgeKey)) {
                           seen.add(edgeKey);
                           knownEdges.push([parseInt(u), parseInt(v)]);
                         }
                       });
                     });
                   }
                   if (!knownEdges) knownEdges = [];

                   return knownEdges.map((edge, idx) => {
                     const u = edge[0] ?? edge.source;
                     const v = edge[1] ?? edge.target;
                     if (u === undefined || v === undefined) return null;
                     
                     const p1 = getPos(u);
                     const p2 = getPos(v);
                     
                     const isRouteEdge = pathNodes.includes(u) && pathNodes.includes(v) && Math.abs(pathNodes.indexOf(u) - pathNodes.indexOf(v)) === 1;
                     if (isRouteEdge) return null; // Drawn on top
                     
                     const isBlocked = isMalicious(u) || isMalicious(v);
                     
                     return (
                       <line 
                         key={`bg-edge-${idx}`}
                         x1={`${p1.left}%`} y1={`${p1.top}%`} x2={`${p2.left}%`} y2={`${p2.top}%`}
                         stroke={isBlocked ? "#fca5a5" : "#e2e8f0"} 
                         strokeWidth={isBlocked ? "2" : "2"}
                         strokeDasharray={isBlocked ? "6,6" : "none"}
                       />
                     );
                   });
                 })()}

                 {/* Active Safe Route Edges (Vibrant Green with Flowing Pulse) */}
                 {pathNodes.map((nodeId, idx) => {
                   if (idx === 0) return null;
                   const prevId = pathNodes[idx - 1];
                   
                   const p1 = getPos(prevId);
                   const p2 = getPos(nodeId);
                   
                   return (
                     <g key={`route-${idx}`}>
                       <line 
                         x1={`${p1.left}%`} y1={`${p1.top}%`} x2={`${p2.left}%`} y2={`${p2.top}%`}
                         stroke="#10b981" strokeWidth="5" className="drop-shadow-sm"
                       />
                       <line 
                         x1={`${p1.left}%`} y1={`${p1.top}%`} x2={`${p2.left}%`} y2={`${p2.top}%`}
                         stroke="#ffffff" strokeWidth="2.5" strokeDasharray="4 16"
                         className="opacity-80 motion-reduce:hidden animate-route-flow"
                       />
                     </g>
                   );
                 })}
               </svg>

               {/* Nodes */}
               {allNodes.map((id) => {
                 const pos = getPos(id);
                 const malicious = isMalicious(id);
                 const isSource = id === sourceNode;
                 const isDest = id === destNode;
                 const inRoute = pathNodes.includes(id);
                 
                 let nodeBg = 'bg-white border-slate-300 text-slate-700 shadow-sm';
                 if (malicious) {
                   nodeBg = 'bg-gradient-to-tr from-rose-500 to-red-600 border-rose-600 text-white shadow-md shadow-rose-500/30';
                 } else if (inRoute) {
                   nodeBg = 'bg-emerald-500 border-emerald-600 text-white shadow-md shadow-emerald-500/30';
                 }
                 
                 return (
                   <div 
                     key={id}
                     className="absolute flex flex-col items-center justify-center -ml-5 -mt-5 z-10 select-none"
                     style={{ left: `${pos.left}%`, top: `${pos.top}%` }}
                   >
                     {isSource && (
                       <span className="absolute -top-7 text-[10px] font-black bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-2 py-0.5 rounded-full whitespace-nowrap shadow-xs">
                         SOURCE
                       </span>
                     )}
                     {isDest && (
                       <span className="absolute -bottom-7 text-[10px] font-black bg-gradient-to-r from-purple-600 to-indigo-600 text-white px-2 py-0.5 rounded-full whitespace-nowrap shadow-xs">
                         DEST
                       </span>
                     )}
                     {malicious && !isSource && !isDest && (
                       <span className="absolute -top-7 text-[9px] font-bold text-rose-700 tracking-wider whitespace-nowrap bg-rose-100 border border-rose-200 px-2 py-0.5 rounded-full shadow-xs">
                         ATTACKER
                       </span>
                     )}

                     <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm border-2 transition-all hover:scale-115 z-10 cursor-pointer ${nodeBg}`}>
                       {id}
                     </div>
                   </div>
                 );
               })}
             </div>
             
             {/* Floating Safe Route Pill (Bottom Center) */}
             <div className="absolute bottom-5 left-1/2 -translate-x-1/2 bg-white/95 backdrop-blur-md border border-slate-200/80 px-6 py-2.5 rounded-full z-20 shadow-lg shadow-slate-900/5 flex items-center gap-2.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-slate-600 text-xs font-semibold">
                  Safe Route: <span className="font-extrabold text-emerald-600 ml-1">{pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}</span>
                </span>
             </div>
           </div>
        </div>

        {/* Legend & Stats */}
        <div className="space-y-6">
          <div className="dash-card p-6 rounded-3xl">
            <h3 className="font-extrabold text-slate-900 mb-4 pb-3 border-b border-slate-100 text-sm">
              Legend
            </h3>
            <div className="space-y-3.5">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full bg-white border-2 border-slate-300"></div>
                <span className="text-xs font-semibold text-slate-600">Normal Active Node</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full bg-rose-500 border-2 border-rose-600"></div>
                <span className="text-xs font-semibold text-slate-600">Malicious Attacker Node</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-1.5 bg-emerald-500 rounded-full"></div>
                <span className="text-xs font-semibold text-slate-600">Active Safe Route</span>
              </div>
              <div className="flex items-center gap-3 opacity-70">
                <div className="w-6 h-[2px] bg-rose-300 border border-dashed border-rose-300"></div>
                <span className="text-xs font-semibold text-slate-600">Blocked / Excluded Connection</span>
              </div>
              <div className="flex items-center gap-3 opacity-70">
                <div className="w-6 h-[2px] bg-slate-300"></div>
                <span className="text-xs font-semibold text-slate-600">Normal Connection</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">SOURCE</span>
                <span className="text-xs font-semibold text-slate-600">Source Node</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">DEST</span>
                <span className="text-xs font-semibold text-slate-600">Destination Node</span>
              </div>
            </div>
          </div>

          <div className="dash-card p-6 rounded-3xl">
            <h3 className="font-extrabold text-slate-900 mb-4 pb-3 border-b border-slate-100 text-sm">
              Network Topology Stats
            </h3>
            <div className="space-y-3.5">
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Total Nodes</span>
                <span className="font-bold text-slate-900">{nNodes}</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Malicious Attackers</span>
                <span className="font-bold text-rose-600">{maliciousCount}</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Excluded Nodes</span>
                <span className="font-mono font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded max-w-[120px] truncate" title={simStatus?.maliciousNodes?.join(', ') || 'None'}>
                  {maliciousCount > 0 ? simStatus.maliciousNodes.join(', ') : 'None'}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs py-1">
                <span className="font-medium text-slate-500">Route Validation</span>
                <span className={`px-2.5 py-0.5 rounded-full font-bold ${routingPath?.route_available ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                  {routingPath?.route_available ? 'PASS' : 'FAIL'}
                </span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default NetworkTopology;
