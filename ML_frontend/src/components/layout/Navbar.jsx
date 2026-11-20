import React from 'react';
import { Menu, Bell, History, AlertTriangle, Radio } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useRun } from '../../context/RunContext';

const Navbar = ({ toggleSidebar }) => {
  const location = useLocation();
  const path = location.pathname;
  const { selectedRunId, setSelectedRunId, availableRuns, loadingRuns, runsError, refreshRuns } = useRun();
  
  let pageTitle = 'Dashboard';
  let pageSubtitle = 'Real-time MANET intelligence & overview';

  if (path === '/simulation') {
    pageTitle = 'Simulation Control';
    pageSubtitle = 'Configure parameters & run network simulations';
  } else if (path === '/network') {
    pageTitle = 'Network Topology';
    pageSubtitle = 'Interactive topology & secure routing paths';
  } else if (path === '/ml-detection') {
    pageTitle = 'ML Detection';
    pageSubtitle = 'Classical ML & LSTM trust score classification';
  } else if (path === '/prevention') {
    pageTitle = 'Prevention';
    pageSubtitle = 'Threat mitigation & automated node isolation';
  } else if (path === '/route-recovery') {
    pageTitle = 'Route Recovery';
    pageSubtitle = 'Secure alternative route convergence';
  } else if (path === '/performance') {
    pageTitle = 'Performance Metrics';
    pageSubtitle = 'Network QoS evaluation: PDR, delay & throughput';
  }

  // Format today's date cleanly like the reference image "Friday, December 15th 2023"
  const todayFormatted = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  }).format(new Date());

  return (
    <header className="py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <button 
          className="lg:hidden text-slate-600 hover:text-slate-900 bg-white p-2.5 rounded-2xl shadow-xs border border-slate-200/80 transition-colors focus:outline-none" 
          onClick={toggleSidebar}
          aria-label="Toggle Navigation"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            {pageTitle}
          </h1>
          <p className="text-xs sm:text-sm font-medium text-slate-500 mt-0.5">
            {todayFormatted} • {pageSubtitle}
          </p>
        </div>
      </div>

      {/* Top Right Controls (Historical Run Selector, Notifications, User Avatar) */}
      <div className="flex items-center gap-3">
        {/* Historical Run Selector */}
        <div className="flex items-center gap-2">
          {selectedRunId ? (
            <button 
              onClick={() => setSelectedRunId(null)}
              className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80 hover:bg-emerald-100 transition-colors shadow-xs"
              title="Return to active live simulation"
            >
              <Radio className="w-3.5 h-3.5 text-emerald-600 animate-pulse" />
              <span>Return to Live</span>
            </button>
          ) : null}

          <div className="relative flex items-center">
            <div className="flex items-center gap-2 bg-white border border-slate-200/80 shadow-xs rounded-2xl px-3 py-2 text-xs font-medium text-slate-700 hover:border-slate-300 transition-all">
              <History className={`w-4 h-4 shrink-0 ${selectedRunId ? 'text-amber-500' : 'text-slate-400'}`} />
              
              {loadingRuns ? (
                <span className="text-slate-400 text-xs">Loading runs...</span>
              ) : runsError ? (
                <div className="flex items-center gap-1.5 text-rose-600 text-xs">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Error</span>
                  <button 
                    onClick={refreshRuns}
                    className="underline ml-1 hover:text-rose-800"
                    title="Retry loading runs"
                  >
                    Retry
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5">
                  <span 
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      selectedRunId ? 'bg-amber-500' : 'bg-emerald-500 animate-pulse'
                    }`} 
                  />
                  <select
                    value={selectedRunId || ''}
                    onChange={(e) => setSelectedRunId(e.target.value ? e.target.value : null)}
                    className="bg-transparent text-slate-800 text-xs font-semibold focus:outline-none cursor-pointer max-w-[160px] sm:max-w-[220px] truncate"
                    aria-label="Select simulation run"
                  >
                    <option value="">Live Simulation (Active)</option>
                    {availableRuns.length === 0 ? (
                      <option disabled value="__empty">No historical runs</option>
                    ) : (
                      availableRuns.map((run) => (
                        <option key={run.run_id} value={run.run_id}>
                          {run.run_id.length > 20 ? run.run_id.slice(0, 18) + '…' : run.run_id} ({run.num_nodes}N • {run.attack_type || 'Attack'})
                        </option>
                      ))
                    )}
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Notifications circle icon with indicator */}
        {/* <button 
          className="w-10 h-10 rounded-full bg-white border border-slate-200/80 shadow-xs flex items-center justify-center text-slate-500 hover:text-slate-900 hover:border-slate-300 transition-all relative focus:outline-none"
          title="Notifications"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-2.5 right-2.5 w-2 h-2 rounded-full bg-rose-500 ring-2 ring-white"></span>
        </button> */}

        {/* User Profile */}
        <div className="hidden sm:flex items-center gap-3 pl-2">
          <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 p-0.5 shadow-xs">
            <div className="w-full h-full rounded-full bg-white flex items-center justify-center font-bold text-xs text-indigo-700 uppercase">
              A
            </div>
          </div>
          <div className="text-left hidden md:block">
            <div className="font-bold text-sm text-slate-900 leading-tight">Admin</div>
            {/* <div className="text-[11px] font-medium text-slate-400">Admin Operator</div> */}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
