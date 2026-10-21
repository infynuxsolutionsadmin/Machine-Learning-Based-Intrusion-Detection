import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlayCircle, Network, BrainCircuit, ShieldCheck, Route, Activity, X } from 'lucide-react';

const NAV_ITEMS = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Simulation', path: '/simulation', icon: PlayCircle },
  { name: 'Network Topology', path: '/network', icon: Network },
  { name: 'ML Detection', path: '/ml-detection', icon: BrainCircuit },
  { name: 'Prevention', path: '/prevention', icon: ShieldCheck },
  { name: 'Route Recovery', path: '/route-recovery', icon: Route },
  { name: 'Performance', path: '/performance', icon: Activity },
];

const Sidebar = ({ isOpen, toggleSidebar }) => {
  return (
    <>
      {isOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-20 lg:hidden transition-opacity"
          onClick={toggleSidebar}
        />
      )}
      <aside className={`
        fixed top-0 left-0 z-30 h-screen bg-[#0B1120] text-slate-300 w-64
        transition-transform duration-300 ease-in-out flex flex-col border-r border-slate-800
        ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="h-20 flex items-center px-6 border-b border-slate-800/60 shrink-0 justify-between">
          <div className="flex items-center gap-3 text-white">
            <div className="bg-blue-600/20 p-1.5 rounded-lg border border-blue-500/30">
              <Network className="h-5 w-5 text-blue-400" />
            </div>
            <span className="font-bold text-lg tracking-wide text-slate-100">ML MANET</span>
          </div>
          <button className="lg:hidden text-slate-400 hover:text-white transition-colors" onClick={toggleSidebar}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-6 px-3 space-y-1.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 group
                ${isActive 
                  ? 'bg-blue-600 text-white shadow-md shadow-blue-900/20' 
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'}
              `}
              onClick={() => {
                if (window.innerWidth < 1024) toggleSidebar();
              }}
            >
              <item.icon className="h-5 w-5 transition-transform duration-200 group-hover:scale-110" />
              {item.name}
            </NavLink>
          ))}
        </nav>
        <div className="p-5 m-4 rounded-xl bg-slate-800/30 border border-slate-800/60 text-xs text-slate-400">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
            <p className="font-bold text-slate-300 tracking-wide">ML-MANET System</p>
          </div>
          <p className="font-medium text-slate-500 leading-relaxed">Live Backend Integration</p>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
