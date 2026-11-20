import React, { useState, useEffect, useMemo } from 'react';
import { fetchPreventionSummary, fetchSimulationStatus, fetchRoutingPath, fetchNetworkNodes } from '../services/apiService';
import { useRun } from '../context/RunContext';
import { Radio, AlertTriangle } from 'lucide-react';

const NetworkTopology = () => {
  const { selectedRunId } = useRun();

  const [summary, setSummary] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [networkNodes, setNetworkNodes] = useState(null);
  const [loadedRunId, setLoadedRunId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isCurrent = true;
    setLoading(true);
    setError(null);

    const promises = [
      fetchNetworkNodes(selectedRunId),
      fetchPreventionSummary(selectedRunId),
      fetchRoutingPath(selectedRunId),
    ];

    if (!selectedRunId) {
      promises.push(fetchSimulationStatus());
    }

    Promise.allSettled(promises)
      .then(([netRes, sumRes, pathRes, simRes]) => {
        if (!isCurrent) return;

        let anyError = false;
        if (netRes.status === 'fulfilled') setNetworkNodes(netRes.value); else anyError = true;
        if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;
        if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
        if (simRes && simRes.status === 'fulfilled') setSimStatus(simRes.value);

        if (anyError && !netRes.value && !sumRes.value) {
          setError("Unable to load network topology data.");
        }
        setLoadedRunId(selectedRunId);
        setLoading(false);
      })
      .catch((err) => {
        if (!isCurrent) return;
        setError(err.message || "Failed to load network topology.");
        setLoading(false);
      });

    const handleSimulationCompleted = () => {
      if (!selectedRunId && isCurrent) {
        Promise.allSettled([
          fetchNetworkNodes(),
          fetchPreventionSummary(),
          fetchRoutingPath(),
          fetchSimulationStatus(),
        ]).then(([netRes, sumRes, pathRes, simRes]) => {
          if (!isCurrent) return;
          if (netRes.status === 'fulfilled') setNetworkNodes(netRes.value);
          if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
          if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
          if (simRes.status === 'fulfilled') setSimStatus(simRes.value);
        });
      }
    };

    if (!selectedRunId) {
      window.addEventListener('simulation-completed', handleSimulationCompleted);
    }

    return () => {
      isCurrent = false;
      if (!selectedRunId) {
        window.removeEventListener('simulation-completed', handleSimulationCompleted);
      }
    };
  }, [selectedRunId]);

  // Compute normalized authentic coordinates for historical runs
  const nodePositions = useMemo(() => {
    if (!selectedRunId) {
      return null; // In live mode, use posMap default
    }

    const rawPos = networkNodes?.nodes_pos;
    if (!rawPos || typeof rawPos !== 'object') return null;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    const parsed = {};

    for (const [idStr, pos] of Object.entries(rawPos)) {
      const id = parseInt(idStr, 10);
      if (isNaN(id)) continue;

      let x = null, y = null;
      if (Array.isArray(pos) && pos.length >= 2) {
        x = parseFloat(pos[0]);
        y = parseFloat(pos[1]);
      } else if (pos && typeof pos === 'object') {
        x = parseFloat(pos.x ?? pos.left);
        y = parseFloat(pos.y ?? pos.top);
      }

      if (x !== null && y !== null && Number.isFinite(x) && Number.isFinite(y)) {
        parsed[id] = { x, y };
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
      }
    }

    const validIds = Object.keys(parsed);
    if (validIds.length === 0) return null;

    const spanX = maxX - minX;
    const spanY = maxY - minY;

    // Viewport padding percentages inside SVG container
    const padX = 12;
    const padY = 15;
    const widthSpan = 100 - 2 * padX;
    const heightSpan = 100 - 2 * padY;

    const normalized = {};
    for (const [id, { x, y }] of Object.entries(parsed)) {
      const left = spanX > 0.0001 ? padX + ((x - minX) / spanX) * widthSpan : 50;
      const top = spanY > 0.0001 ? padY + ((y - minY) / spanY) * heightSpan : 50;
      normalized[id] = { left: Number(left.toFixed(2)), top: Number(top.toFixed(2)) };
    }

    return normalized;
  }, [selectedRunId, networkNodes]);

  // Strict intermediate render isolation
  if (loading || loadedRunId !== selectedRunId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
        <p className="text-sm font-semibold text-slate-500">
          {selectedRunId ? `Loading Historical Topology (${selectedRunId.slice(0, 15)}...)...` : 'Loading Network Topology...'}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
        <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">Unable to load network topology</h3>
        <p className="text-sm text-slate-500">{error}</p>
      </div>
    );
  }

  // Live mode gating: only active runner requires completed status
  if (!selectedRunId && (!simStatus || simStatus.status !== 'completed')) {
    return (
      <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center">
        <div className="w-12 h-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-3">
          <Radio className="w-6 h-6" />
        </div>
        <p className="text-slate-900 font-extrabold text-lg mb-1">No completed simulation data available</p>
        <p className="text-sm text-slate-500">Run a simulation from the Simulation Control tab to render the interactive network graph.</p>
      </div>
    );
  }

  // Historical mode missing coordinates handling: clear unavailable state instead of fabricated positions
  if (selectedRunId && !nodePositions) {
    return (
      <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center">
        <div className="w-12 h-12 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-3">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <p className="text-slate-900 font-extrabold text-lg mb-1">Topology Data Unavailable</p>
        <p className="text-sm text-slate-500">
          Authentic node coordinates could not be loaded for simulation run{' '}
          <span className="font-mono font-semibold text-slate-700">{selectedRunId}</span>.
        </p>
      </div>
    );
  }

  // Derive node IDs strictly from authentic nodePositions keys in historical mode
  const allNodes = selectedRunId
    ? (nodePositions ? Object.keys(nodePositions).map(Number).sort((a, b) => a - b) : [])
    : Array.from({ length: simStatus?.nNodes || 0 }, (_, i) => i);

  const nNodes = selectedRunId ? allNodes.length : (simStatus?.nNodes || 0);

  // Derive malicious nodes list without falling back to live simStatus in historical mode
  const maliciousNodesList = selectedRunId
    ? (summary?.blocked_or_restricted_nodes || summary?.detected_low_trust_nodes || [])
    : (simStatus?.maliciousNodes || []);

  const isMalicious = (id) => maliciousNodesList.includes(id);
  const maliciousCount = maliciousNodesList.length;

  const sourceNode = selectedRunId
    ? (summary?.source ?? routingPath?.source ?? (allNodes.length > 0 ? allNodes[0] : 0))
    : (simStatus?.sourceNode ?? 0);

  const destNode = selectedRunId
    ? (summary?.destination ?? routingPath?.destination ?? (allNodes.length > 0 ? allNodes[allNodes.length - 1] : 9))
    : (simStatus?.destinationNode ?? (simStatus?.nNodes ? simStatus.nNodes - 1 : 9));

  const pathNodes = routingPath?.route_nodes || summary?.recovered_route || [];

  // Stable Node Positioning
  const getPos = (id) => {
    if (selectedRunId && nodePositions) {
      if (nodePositions[id]) return nodePositions[id];
    }

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

    // Fallback for dynamic nodes
    const cols = Math.ceil(Math.sqrt(Math.max(1, nNodes - 10)));
    const row = Math.floor((id - 10) / cols);
    const col = (id - 10) % cols;
    return {
      left: 20 + (col * 15) % 60,
      top: 15 + (row * 15) % 70,
    };
  };

  // Derive known nominal connectivity edges
  let knownEdges = networkNodes?.network_edges || networkNodes?.edges || simStatus?.edges || summary?.edges || routingPath?.edges || routingPath?.network_edges;

  if (!knownEdges && summary?.trust_scores) {
    knownEdges = [];
    const seen = new Set();
    Object.entries(summary.trust_scores).forEach(([u, neighbors]) => {
      if (neighbors && typeof neighbors === 'object') {
        Object.keys(neighbors).forEach((v) => {
          const edgeKey = [parseInt(u, 10), parseInt(v, 10)].sort().join('-');
          if (!seen.has(edgeKey)) {
            seen.add(edgeKey);
            knownEdges.push([parseInt(u, 10), parseInt(v, 10)]);
          }
        });
      }
    });
  }
  if (!knownEdges) knownEdges = [];

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
            <div className="flex items-center gap-2">
              <h2 className="font-extrabold text-slate-900 text-base">Distributed MANET Topology</h2>
              {selectedRunId && (
                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-800">
                  Historical Run: {selectedRunId.slice(0, 15)}...
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              {nNodes} nodes deployed • {maliciousCount} attackers isolated • Safe route:{' '}
              <span className="font-bold text-emerald-600">
                {pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}
              </span>
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
              {/* Base/Background Edges (Nominal Transmission Connectivity) */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none z-0 overflow-visible">
                {knownEdges.map((edge, idx) => {
                  const u = edge[0] ?? edge.source;
                  const v = edge[1] ?? edge.target;
                  if (u === undefined || v === undefined) return null;

                  const p1 = getPos(u);
                  const p2 = getPos(v);
                  if (!p1 || !p2) return null;

                  const isRouteEdge =
                    pathNodes.includes(u) &&
                    pathNodes.includes(v) &&
                    Math.abs(pathNodes.indexOf(u) - pathNodes.indexOf(v)) === 1;
                  if (isRouteEdge) return null; // Rendered in safe route layer

                  const isBlocked = isMalicious(u) || isMalicious(v);

                  return (
                    <line
                      key={`bg-edge-${idx}`}
                      x1={`${p1.left}%`}
                      y1={`${p1.top}%`}
                      x2={`${p2.left}%`}
                      y2={`${p2.top}%`}
                      stroke={isBlocked ? '#fca5a5' : '#e2e8f0'}
                      strokeWidth={isBlocked ? '2' : '2'}
                      strokeDasharray={isBlocked ? '6,6' : 'none'}
                    />
                  );
                })}

                {/* Active Safe Route Edges (Vibrant Green with Flowing Pulse) */}
                {pathNodes.map((nodeId, idx) => {
                  if (idx === 0) return null;
                  const prevId = pathNodes[idx - 1];

                  const p1 = getPos(prevId);
                  const p2 = getPos(nodeId);
                  if (!p1 || !p2) return null;

                  return (
                    <g key={`route-${idx}`}>
                      <line
                        x1={`${p1.left}%`}
                        y1={`${p1.top}%`}
                        x2={`${p2.left}%`}
                        y2={`${p2.top}%`}
                        stroke="#10b981"
                        strokeWidth="5"
                        className="drop-shadow-sm"
                      />
                      <line
                        x1={`${p1.left}%`}
                        y1={`${p1.top}%`}
                        x2={`${p2.left}%`}
                        y2={`${p2.top}%`}
                        stroke="#ffffff"
                        strokeWidth="2.5"
                        strokeDasharray="4 16"
                        className="opacity-80 motion-reduce:hidden animate-route-flow"
                      />
                    </g>
                  );
                })}
              </svg>

              {/* Nodes */}
              {allNodes.map((id) => {
                const pos = getPos(id);
                if (!pos) return null;

                const malicious = isMalicious(id);
                const isSource = id === sourceNode;
                const isDest = id === destNode;
                const inRoute = pathNodes.includes(id);

                let nodeBg = 'bg-white border-slate-300 text-slate-700 shadow-sm';
                if (malicious) {
                  nodeBg =
                    'bg-gradient-to-tr from-rose-500 to-red-600 border-rose-600 text-white shadow-md shadow-rose-500/30';
                } else if (inRoute) {
                  nodeBg =
                    'bg-emerald-500 border-emerald-600 text-white shadow-md shadow-emerald-500/30';
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

                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm border-2 transition-all hover:scale-115 z-10 cursor-pointer ${nodeBg}`}
                    >
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
                Safe Route:{' '}
                <span className="font-extrabold text-emerald-600 ml-1">
                  {pathNodes.length > 0 ? pathNodes.join(' → ') : 'None'}
                </span>
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
                <span className="text-xs font-semibold text-slate-600" title="Nominal wireless connectivity (range <= 60% area)">
                  Nominal Wireless Link
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">
                  SOURCE
                </span>
                <span className="text-xs font-semibold text-slate-600">Source Node</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                  DEST
                </span>
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
                <span
                  className="font-mono font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded max-w-[120px] truncate"
                  title={maliciousNodesList.length > 0 ? maliciousNodesList.join(', ') : 'None'}
                >
                  {maliciousNodesList.length > 0 ? maliciousNodesList.join(', ') : 'None'}
                </span>
              </div>
              <div className="flex justify-between items-center text-xs py-1 border-b border-slate-50">
                <span className="font-medium text-slate-500">Nominal Wireless Links</span>
                <span className="font-bold text-slate-900">{knownEdges.length}</span>
              </div>
              <div className="flex justify-between items-center text-xs py-1">
                <span className="font-medium text-slate-500">Route Validation</span>
                <span
                  className={`px-2.5 py-0.5 rounded-full font-bold ${
                    routingPath?.route_available || pathNodes.length > 0
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-rose-100 text-rose-700'
                  }`}
                >
                  {routingPath?.route_available || pathNodes.length > 0 ? 'PASS' : 'FAIL'}
                </span>
              </div>
            </div>
            <p className="mt-4 pt-3 border-t border-slate-100 text-[10px] text-slate-400 leading-normal">
              * Nominal wireless links reflect Euclidean transmission range connectivity and are distinct from multi-hop packet forwarding routes.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkTopology;
