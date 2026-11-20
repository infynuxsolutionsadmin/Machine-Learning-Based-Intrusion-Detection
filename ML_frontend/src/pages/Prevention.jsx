import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchPreventionSummary,
  fetchSimulationStatus,
  fetchRoutingPath,
  fetchPreventionEvents,
} from '../services/apiService';
import { useRun } from '../context/RunContext';
import {
  ShieldCheck,
  Lock,
  ShieldAlert,
  Network,
  ArrowRight,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  ListFilter,
} from 'lucide-react';

const PAGE_SIZE = 25;

const Prevention = () => {
  const { selectedRunId } = useRun();

  const [summary, setSummary] = useState(null);
  const [simStatus, setSimStatus] = useState(null);
  const [routingPath, setRoutingPath] = useState(null);
  const [loadedRunId, setLoadedRunId] = useState(null);

  // Prevention Events state
  const [eventsData, setEventsData] = useState(null); // { total_events, events }
  const [eventsOffset, setEventsOffset] = useState(0);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load summary and initial events for active selectedRunId
  useEffect(() => {
    let isCurrent = true;
    setLoading(true);
    setError(null);
    setEventsOffset(0);
    setEventsError(null);
    setEventsLoading(true);

    const summaryPromises = [
      fetchPreventionSummary(selectedRunId),
      fetchRoutingPath(selectedRunId),
    ];

    if (!selectedRunId) {
      summaryPromises.push(fetchSimulationStatus());
    }

    Promise.allSettled(summaryPromises).then(([sumRes, pathRes, simRes]) => {
      if (!isCurrent) return;

      let anyError = false;
      if (sumRes.status === 'fulfilled') setSummary(sumRes.value); else anyError = true;
      if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
      if (simRes && simRes.status === 'fulfilled') setSimStatus(simRes.value);

      if (anyError && !sumRes.value) {
        setError('Unable to load prevention summary data from backend.');
      }
      setLoadedRunId(selectedRunId);
      setLoading(false);
    });

    // Fetch initial event page (offset = 0)
    const eventPromise = selectedRunId
      ? fetchPreventionEvents(selectedRunId, { offset: 0, limit: PAGE_SIZE })
      : fetchPreventionEvents({ offset: 0, limit: PAGE_SIZE });

    eventPromise
      .then((data) => {
        if (!isCurrent) return;
        setEventsData(data);
        setEventsError(null);
      })
      .catch((err) => {
        if (!isCurrent) return;
        if (!selectedRunId) {
          // In live mode with no active simulation run, missing events is normal
          setEventsData(null);
        } else {
          setEventsError(err.message || 'Failed to fetch prevention events.');
          setEventsData(null);
        }
      })
      .finally(() => {
        if (isCurrent) setEventsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedRunId]);

  // Page navigation handler for event table
  const handlePageChange = useCallback(
    (newOffset) => {
      setEventsLoading(true);
      setEventsError(null);

      const fetchPromise = selectedRunId
        ? fetchPreventionEvents(selectedRunId, { offset: newOffset, limit: PAGE_SIZE })
        : fetchPreventionEvents({ offset: newOffset, limit: PAGE_SIZE });

      fetchPromise
        .then((data) => {
          setEventsData(data);
          setEventsOffset(newOffset);
        })
        .catch((err) => {
          setEventsError(err.message || 'Failed to load page.');
        })
        .finally(() => {
          setEventsLoading(false);
        });
    },
    [selectedRunId]
  );

  // Live mode polling: strictly disabled when selectedRunId is active
  useEffect(() => {
    if (selectedRunId) return; // Disabled in historical mode

    const interval = setInterval(() => {
      fetchSimulationStatus()
        .then((status) => {
          setSimStatus(status);
          if (status?.status === 'running' || status?.status === 'completed') {
            fetchPreventionSummary().then(setSummary).catch(() => {});
            fetchRoutingPath().then(setRoutingPath).catch(() => {});
            fetchPreventionEvents({ offset: eventsOffset, limit: PAGE_SIZE })
              .then(setEventsData)
              .catch(() => {});
          }
        })
        .catch(() => {});
    }, 3000);

    return () => clearInterval(interval);
  }, [selectedRunId, eventsOffset]);

  // Event listener for live simulation completion
  useEffect(() => {
    const handleSimComplete = () => {
      if (!selectedRunId) {
        Promise.allSettled([
          fetchPreventionSummary(),
          fetchSimulationStatus(),
          fetchRoutingPath(),
          fetchPreventionEvents({ offset: 0, limit: PAGE_SIZE }),
        ]).then(([sumRes, simRes, pathRes, evRes]) => {
          if (sumRes.status === 'fulfilled') setSummary(sumRes.value);
          if (simRes.status === 'fulfilled') setSimStatus(simRes.value);
          if (pathRes.status === 'fulfilled') setRoutingPath(pathRes.value);
          if (evRes.status === 'fulfilled') setEventsData(evRes.value);
        });
      }
    };

    window.addEventListener('simulation-completed', handleSimComplete);
    return () => window.removeEventListener('simulation-completed', handleSimComplete);
  }, [selectedRunId]);

  // Intermediate render isolation
  if (loading || loadedRunId !== selectedRunId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
        <div className="w-10 h-10 rounded-full border-3 border-blue-600/20 border-t-blue-600 animate-spin"></div>
        <p className="text-sm font-semibold text-slate-500">
          {selectedRunId ? `Loading Historical Prevention Data (${selectedRunId.slice(0, 15)}...)...` : 'Loading Prevention Data...'}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dash-card p-6 rounded-3xl max-w-xl mx-auto mt-8 border-rose-200 bg-rose-50/50">
        <h3 className="text-base font-extrabold text-rose-800 mb-1 flex items-center gap-2">
          Unable to load data
        </h3>
        <p className="text-sm text-slate-500">{error}</p>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="dash-card p-8 rounded-3xl max-w-xl mx-auto mt-8 text-center text-slate-500 font-medium">
        No prevention data available from the backend. Run a simulation to generate prevention outcomes.
      </div>
    );
  }

  const detectedNodes = [...new Set(summary.detected_low_trust_nodes || [])];
  const isolatedNodes = [...new Set(summary.blocked_or_restricted_nodes || [])];

  const groundTruthNodes = selectedRunId
    ? (summary?.ground_truth_nodes ?? summary?.malicious_nodes ?? [])
    : (summary?.ground_truth_nodes ?? summary?.malicious_nodes ?? simStatus?.maliciousNodes ?? []);

  const totalNodes = selectedRunId
    ? (summary?.num_nodes ?? summary?.total_nodes ?? summary?.nNodes ?? 'N/A')
    : (summary?.num_nodes ?? summary?.total_nodes ?? summary?.nNodes ?? simStatus?.nNodes ?? 'N/A');

  const hasTrustData = Boolean(summary?.trust_scores && Object.keys(summary.trust_scores).length > 0);
  const detectedNodesSet = new Set(detectedNodes);
  let detectionResult = 'N/A';
  if (!hasTrustData) {
    detectionResult = 'Insufficient Data';
  } else if (groundTruthNodes.length > 0 && detectedNodes.length > 0) {
    let matchCount = 0;
    groundTruthNodes.forEach((node) => {
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

  const sourceNode = selectedRunId
    ? summary?.source ?? routingPath?.source ?? 'N/A'
    : simStatus?.source ?? routingPath?.source ?? summary?.source ?? 'N/A';

  const destNode = selectedRunId
    ? summary?.destination ?? routingPath?.destination ?? 'N/A'
    : simStatus?.destination ?? routingPath?.destination ?? summary?.destination ?? 'N/A';

  // Events pagination metrics
  const totalEvents = eventsData?.total_events ?? 0;
  const eventsList = eventsData?.events ?? [];
  const totalPages = Math.ceil(totalEvents / PAGE_SIZE) || 1;
  const currentPage = Math.floor(eventsOffset / PAGE_SIZE) + 1;
  const hasPrev = eventsOffset > 0;
  const hasNext = eventsOffset + PAGE_SIZE < totalEvents;

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-10 animate-in fade-in duration-300">
      {/* Historical Selection Banner if active */}
      {selectedRunId && (
        <div className="dash-card p-4 rounded-3xl bg-amber-50/60 border border-amber-200/80 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 animate-pulse"></span>
            <span className="text-xs font-bold text-amber-900">
              Viewing Historical Simulation Run:
            </span>
            <span className="font-mono text-xs font-semibold text-amber-800">
              {selectedRunId}
            </span>
          </div>
          <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-amber-200/60 text-amber-900">
            Historical Data
          </span>
        </div>
      )}

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
            <span className="text-xs font-semibold text-blue-100 uppercase tracking-wider block">
              Total Topology Nodes
            </span>
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
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Detected Threats
            </span>
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
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Isolated Nodes
            </span>
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
            <span
              className={`px-3 py-1 rounded-full text-xs font-extrabold ${
                summary.recovery_success
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-slate-100 text-slate-500'
              }`}
            >
              {summary.recovery_success ? 'Optimal' : 'Pending'}
            </span>
          </div>
          <div className="mt-4">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block">
              Prevention Status
            </span>
            <div className="text-2xl font-black text-emerald-600 tracking-tight mt-0.5">
              {summary.recovery_success ? 'Active Defense' : 'Pending'}
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
                    groundTruthNodes.map((node) => (
                      <span
                        key={node}
                        className="font-extrabold text-xs text-white bg-rose-500 px-2.5 py-1 rounded-full shadow-xs"
                      >
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
                    detectedNodes.map((node) => (
                      <span
                        key={node}
                        className="font-extrabold text-xs text-white bg-rose-500 px-2.5 py-1 rounded-full shadow-xs"
                      >
                        Node {node}
                      </span>
                    ))
                  ) : !hasTrustData ? (
                    <span className="text-xs font-bold text-amber-500">Data Unavailable</span>
                  ) : (
                    <span className="text-xs font-bold text-slate-400">None</span>
                  )}
                </div>
              </div>

              <div className="flex justify-between items-center py-2">
                <span className="text-sm font-medium text-slate-500">Detection Result</span>
                <span
                  className={`px-3 py-1 rounded-full text-xs font-extrabold ${
                    detectionResult.includes('Match') && !detectionResult.includes('Mismatch')
                      ? 'bg-emerald-100 text-emerald-700'
                      : detectionResult === 'Insufficient Data'
                      ? 'bg-amber-100 text-amber-800'
                      : 'bg-rose-100 text-rose-700'
                  }`}
                >
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
                <span className="font-bold text-slate-700 text-xs sm:text-sm">
                  1. Anomaly Detection
                </span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
                  Completed
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <span className="font-bold text-slate-700 text-xs sm:text-sm">
                  2. Malicious Isolation
                </span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
                  {isolatedNodes.length > 0 ? 'Completed' : 'Skipped (No Threats)'}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 rounded-2xl bg-slate-50 border border-slate-100">
                <span className="font-bold text-slate-700 text-xs sm:text-sm">
                  3. Trust Evaluation
                </span>
                <span className="text-xs font-extrabold bg-emerald-100 text-emerald-700 px-3 py-1 rounded-full">
                  Completed
                </span>
              </div>

              <div
                className={`flex items-center justify-between p-3 rounded-2xl border ${
                  summary.recovery_success
                    ? 'bg-emerald-50/60 border-emerald-100'
                    : 'bg-slate-50 border-slate-100'
                }`}
              >
                <span className="font-bold text-slate-700 text-xs sm:text-sm">
                  4. Safe Trust Routing
                </span>
                <span
                  className={`text-xs font-extrabold px-3 py-1 rounded-full ${
                    summary.recovery_success
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
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

      {/* Middle-Bottom: Routing Outcome & Route Recovery */}
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
                      {index < routingPath.route_nodes.length - 1 && (
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                      )}
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
              <span className="font-bold text-slate-700 text-xs sm:text-sm">
                {summary.routing_method || 'N/A'}
              </span>
            </div>
          </div>
        </div>

        {/* Circular Route Recovery Indicator */}
        <div className="bg-slate-50/70 p-8 border-t md:border-t-0 md:border-l border-slate-100 flex flex-col items-center justify-center text-center space-y-4">
          <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Route Recovery Status
          </div>

          <div className="relative w-32 h-32 flex items-center justify-center">
            <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="transparent" stroke="#e2e8f0" strokeWidth="8" />
              <circle
                cx="50"
                cy="50"
                r="42"
                fill="transparent"
                stroke={summary.recovery_success ? '#10b981' : '#94a3b8'}
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
            <div
              className={`font-extrabold text-xs px-3.5 py-1.5 rounded-full inline-block ${
                summary.recovery_success
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-slate-200 text-slate-700'
              }`}
            >
              {summary.recovery_success ? 'Active Route Established' : 'Awaiting Resolution'}
            </div>
          </div>
        </div>
      </div>

      {/* Prevention & Mitigation Event Ledger (Stage 8C-3 Paginated Event Table) */}
      <div className="dash-card rounded-3xl p-6 sm:p-8 space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <ListFilter className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-slate-900 text-base">
                Prevention & Mitigation Event Ledger
              </h3>
              <p className="text-xs text-slate-400">
                Authentic chronological NS-3 prevention and mitigation event records
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-indigo-50 text-indigo-700 border border-indigo-100">
              Total Events: {totalEvents}
            </span>
          </div>
        </div>

        {eventsError ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-center gap-3 text-sm">
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-600" />
            <div className="flex-1">
              <span className="font-bold block">Failed to load prevention events</span>
              <span className="text-xs text-rose-700">{eventsError}</span>
            </div>
          </div>
        ) : eventsLoading ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-indigo-600/20 border-t-indigo-600 animate-spin"></div>
            <p className="text-xs font-semibold text-slate-400">Loading events page...</p>
          </div>
        ) : totalEvents === 0 ? (
          <div className="p-8 rounded-2xl bg-slate-50 border border-slate-100 text-center text-slate-500 text-sm font-medium">
            No prevention events recorded for this run.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="overflow-x-auto rounded-2xl border border-slate-100">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50 text-slate-600 font-bold uppercase tracking-wider border-b border-slate-100">
                    <th className="py-3 px-4">Sequence</th>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4">Event Type</th>
                    <th className="py-3 px-4">Source Node</th>
                    <th className="py-3 px-4">Target Node</th>
                    <th className="py-3 px-4">Action Taken</th>
                    <th className="py-3 px-4">Reason</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700 font-medium">
                  {eventsList.map((ev, idx) => {
                    const seq = ev.sequence ?? 'N/A';
                    const time =
                      ev.time_sec != null
                        ? `${Number(ev.time_sec).toFixed(2)}s`
                        : 'N/A';
                    const eventType = ev.action_type || 'N/A';
                    const source = ev.source_node != null ? `Node ${ev.source_node}` : 'N/A';
                    const target = ev.node_id != null ? `Node ${ev.node_id}` : 'N/A';
                    const actionTaken = ev.execution_status
                      ? `${ev.action_type} (${ev.execution_status})`
                      : ev.action_type || 'N/A';
                    const reason = ev.trigger_source || ev.details || 'N/A';

                    const isSuccess = ev.execution_status === 'SUCCESS';
                    const isIgnored = ev.execution_status === 'DUPLICATE_IGNORED';

                    return (
                      <tr
                        key={ev.id || `${seq}-${idx}`}
                        className="hover:bg-slate-50/80 transition-colors"
                      >
                        <td className="py-3 px-4 font-mono font-bold text-slate-900">
                          #{seq}
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-600">{time}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-slate-100 text-slate-700">
                            {eventType}
                          </span>
                        </td>
                        <td className="py-3 px-4">{source}</td>
                        <td className="py-3 px-4">
                          {ev.node_id != null ? (
                            <span className="font-bold text-rose-600 bg-rose-50 px-2 py-0.5 rounded-full">
                              {target}
                            </span>
                          ) : (
                            'N/A'
                          )}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                              isSuccess
                                ? 'bg-emerald-100 text-emerald-800'
                                : isIgnored
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {actionTaken}
                          </span>
                        </td>
                        <td
                          className="py-3 px-4 max-w-xs truncate text-slate-500"
                          title={reason}
                        >
                          {reason}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2">
              <span className="text-xs text-slate-500 font-medium">
                Showing{' '}
                <span className="font-bold text-slate-900">
                  {totalEvents === 0 ? 0 : eventsOffset + 1}
                </span>{' '}
                to{' '}
                <span className="font-bold text-slate-900">
                  {Math.min(eventsOffset + PAGE_SIZE, totalEvents)}
                </span>{' '}
                of <span className="font-bold text-slate-900">{totalEvents}</span> events
              </span>

              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 mr-2 font-medium">
                  Page <span className="font-bold text-slate-900">{currentPage}</span> of{' '}
                  <span className="font-bold text-slate-900">{totalPages}</span>
                </span>

                <button
                  type="button"
                  onClick={() => handlePageChange(Math.max(0, eventsOffset - PAGE_SIZE))}
                  disabled={!hasPrev || eventsLoading}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </button>

                <button
                  type="button"
                  onClick={() => handlePageChange(eventsOffset + PAGE_SIZE)}
                  disabled={!hasNext || eventsLoading}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Prevention;
