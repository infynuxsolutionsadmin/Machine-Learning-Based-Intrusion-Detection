import React, { useState, useEffect } from 'react';
import { fetchPreventionSummary, fetchSimulationStatus, fetchRoutingPath, fetchNetworkNodes } from '../services/apiService';
import { Server, AlertTriangle } from 'lucide-react';

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
    <div className="p-8 max-w-7xl mx-auto flex items-center justify-center min-h-[50vh]">
      <div className="text-slate-500 font-medium text-lg flex items-center gap-3">
        <span className="w-5 h-5 rounded-full border-2 border-slate-300 border-t-blue-600 animate-spin"></span>
        Loading network topology...
      </div>
    </div>
  );
  
  if (error) return (
    <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10">
      <h3 className="text-lg font-bold text-red-800 mb-2 flex items-center gap-2">Unable to load network topology</h3>
      <p className="text-slate-500">{error}</p>
    </div>
  );
  
  if (!simStatus || simStatus.status !== 'completed') return (
    <div className="bg-white p-8 rounded-2xl shadow-sm border border-slate-100 max-w-xl mx-auto mt-10 text-center">
      <p className="text-slate-800 font-bold text-xl mb-2">No completed simulation data available.</p>
      <p className="text-slate-500">Run a simulation to view the network topology.</p>
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
    // We use a carefully crafted distributed layout to minimize overlap,
    // keep nodes distinct, and ensure readable labels.
    const posMap = {
      0: { left: 10, top: 50 },  // Source Node (Far Left)
      5: { left: 20, top: 20 },  // Top Row (Malicious)
      8: { left: 50, top: 20 },  // Top Row
      4: { left: 80, top: 20 },  // Top Row
      2: { left: 35, top: 50 },  // Route Node
      3: { left: 65, top: 50 },  // Route Node
      6: { left: 20, top: 80 },  // Bottom Row
      1: { left: 50, top: 80 },  // Bottom Row (Malicious)
      7: { left: 80, top: 80 },  // Bottom Row
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
    <div className="space-y-6 max-w-7xl mx-auto pb-10">
      <style>{`
        @keyframes routeFlow {
          from { stroke-dashoffset: 24; }
          to { stroke-dashoffset: 0; }
        }
        .animate-route-flow {
          animation: routeFlow 0.8s linear infinite;
        }
      `}</style>
      <div className="mb-8">
        <h1 className="text-3xl font-black text-slate-800">Network Topology</h1>
        <p className="text-slate-600 font-bold text-lg mt-1">ML-MANET Network Topology</p>
        <p className="text-slate-500 font-medium mt-1">
          {nNodes} nodes • {maliciousCount} malicious • Safe route: {pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Network Map */}
        <div className="lg:col-span-2 bg-white rounded-2xl overflow-hidden border border-slate-200 relative min-h-[550px] flex items-center justify-center p-8 shadow-sm">
           {/* Grid background */}
           <div className="absolute inset-0 opacity-40 bg-[linear-gradient(rgba(0,0,0,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(0,0,0,0.05)_1px,transparent_1px)] bg-[size:40px_40px]"></div>
           
           <div className="relative z-10 w-full h-full flex flex-col items-center justify-center">
             
             <div className="relative w-full max-w-3xl aspect-video md:aspect-[21/9]">
               {/* Base/Background Edges (Subtle) */}
               <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-visible">
                 {(() => {
                   // Pull exact physical connections from NS-3 simulation data directly
                   let knownEdges = networkNodes?.network_edges || simStatus?.edges || summary?.edges || routingPath?.edges || routingPath?.network_edges;
                   
                   // Fallback: extract from trust_scores if edges array isn't explicitly provided
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

                   // If we have known edges, draw them
                   return knownEdges.map((edge, idx) => {
                     const u = edge[0] ?? edge.source;
                     const v = edge[1] ?? edge.target;
                     if (u === undefined || v === undefined) return null;
                     
                     const p1 = getPos(u);
                     const p2 = getPos(v);
                     
                     // Check if this edge is part of the active route
                     const isRouteEdge = pathNodes.includes(u) && pathNodes.includes(v) && Math.abs(pathNodes.indexOf(u) - pathNodes.indexOf(v)) === 1;
                     if (isRouteEdge) return null; // Drawn later sequentially on top
                     
                     // Check if it involves a malicious node
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

                 {/* Active Safe Route Edges (Strong Green with Animated Flow) */}
                 {pathNodes.map((nodeId, idx) => {
                   if (idx === 0) return null;
                   const prevId = pathNodes[idx - 1];
                   
                   const p1 = getPos(prevId);
                   const p2 = getPos(nodeId);
                   
                   return (
                     <g key={`route-${idx}`}>
                       {/* Static base line for reduced motion or gaps */}
                       <line 
                         x1={`${p1.left}%`} y1={`${p1.top}%`} x2={`${p2.left}%`} y2={`${p2.top}%`}
                         stroke="#22c55e" strokeWidth="5" className="drop-shadow-sm"
                       />
                       {/* Animated flow effect */}
                       <line 
                         x1={`${p1.left}%`} y1={`${p1.top}%`} x2={`${p2.left}%`} y2={`${p2.top}%`}
                         stroke="#ffffff" strokeWidth="2.5" strokeDasharray="4 20"
                         className="opacity-70 motion-reduce:hidden animate-route-flow"
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
                 if (malicious) nodeBg = 'bg-red-500 border-red-600 text-white shadow-red-500/30 shadow-md';
                 else if (inRoute) nodeBg = 'bg-emerald-50 border-emerald-500 text-emerald-800 shadow-emerald-500/20 shadow-md border-[3px]';
                 
                 return (
                   <div 
                     key={id}
                     className="absolute flex flex-col items-center justify-center -ml-5 -mt-5 z-10"
                     style={{ left: `${pos.left}%`, top: `${pos.top}%` }}
                   >
                     {isSource && <span className="absolute -top-7 text-[10px] font-black bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded border border-blue-200 whitespace-nowrap shadow-sm">SOURCE</span>}
                     {isDest && <span className="absolute -bottom-7 text-[10px] font-black bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded border border-indigo-200 whitespace-nowrap shadow-sm">DEST</span>}
                     {malicious && !isSource && !isDest && <span className="absolute -top-7 text-[9px] font-bold text-red-600 tracking-wider whitespace-nowrap bg-red-50 border border-red-200 px-1 rounded shadow-sm">MALICIOUS</span>}

                     <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm border-2 transition-transform hover:scale-110 z-10 ${nodeBg}`}>
                       {id}
                     </div>
                   </div>
                 );
               })}
             </div>
             
             <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white border border-slate-200 px-5 py-2.5 rounded-full z-20 shadow-lg flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="text-slate-600 text-sm font-medium">Safe Route: <span className="font-black text-emerald-600 ml-1">{pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}</span></span>
             </div>
           </div>
        </div>

        {/* Legend & Stats */}
        <div className="space-y-6">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="font-bold text-slate-800 mb-4 pb-3 border-b border-slate-100">Legend</h3>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full bg-white border-2 border-slate-300"></div>
                <span className="text-sm font-medium text-slate-700">Normal Node</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-full bg-red-500 border-2 border-red-600"></div>
                <span className="text-sm font-medium text-slate-700">Malicious Node</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-6 h-1 bg-emerald-500 rounded-full drop-shadow-sm"></div>
                <span className="text-sm font-medium text-slate-700">Active Safe Route</span>
              </div>
              <div className="flex items-center gap-3 opacity-70">
                <div className="w-6 h-[2px] bg-red-300 border border-dashed border-red-300"></div>
                <span className="text-sm font-medium text-slate-700">Blocked / Excluded Connection</span>
              </div>
              <div className="flex items-center gap-3 opacity-70">
                <div className="w-6 h-[3px] bg-slate-300"></div>
                <span className="text-sm font-medium text-slate-700">Normal Connection</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded border border-blue-200">SOURCE</span>
                <span className="text-sm font-medium text-slate-700">Source Node</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded border border-indigo-200">DEST</span>
                <span className="text-sm font-medium text-slate-700">Destination Node</span>
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-100">
            <h3 className="font-bold text-slate-800 mb-4 pb-3 border-b border-slate-100">Network Stats</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Total Nodes</span>
                <span className="font-bold text-slate-800">{nNodes}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Malicious Nodes</span>
                <span className="font-bold text-slate-800">{maliciousCount}</span>
              </div>
              {/* <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Safe Nodes</span>
                <span className="font-bold text-slate-800">{safeNodesCount}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Source</span>
                <span className="font-bold text-slate-800">{sourceNode}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Destination</span>
                <span className="font-bold text-slate-800">{destNode}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Active Route</span>
                <span className="font-bold text-slate-800 max-w-[120px] truncate" title={pathNodes.join(' → ')}>{pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}</span>
              </div>
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Route Hops</span>
                <span className="font-bold text-slate-800">{pathNodes.length > 0 ? pathNodes.length - 1 : 0}</span>
              </div> */}
              <div className="flex justify-between items-center pb-3 border-b border-slate-50">
                <span className="text-sm font-medium text-slate-600">Excluded Nodes</span>
                <span className="font-bold text-slate-800 max-w-[100px] truncate" title={simStatus?.maliciousNodes?.join(', ') || 'None'}>{maliciousCount > 0 ? simStatus.maliciousNodes.join(', ') : 'None'}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-slate-600">Validation</span>
                <span className={`font-bold ${routingPath?.route_available ? 'text-emerald-600' : 'text-red-600'}`}>{routingPath?.route_available ? 'PASS' : 'FAIL'}</span>
              </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default NetworkTopology;
