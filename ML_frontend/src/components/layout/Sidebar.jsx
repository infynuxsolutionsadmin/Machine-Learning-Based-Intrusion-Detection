import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, PlayCircle, Network, BrainCircuit, 
  ShieldCheck, Activity, X, Sparkles
} from 'lucide-react';

const MENU_ITEMS = [
  { name: 'Dashboard', path: '/', icon: LayoutDashboard },
  { name: 'Simulation', path: '/simulation', icon: PlayCircle },
  { name: 'Network Topology', path: '/network', icon: Network },
];

const ANALYTICS_ITEMS = [
  { name: 'ML Detection', path: '/ml-detection', icon: BrainCircuit },
  { name: 'Prevention', path: '/prevention', icon: ShieldCheck },
  { name: 'Performance', path: '/performance', icon: Activity },
];

const Sidebar = ({ isOpen, toggleSidebar }) => {
  return (
    <>
      {isOpen && (
        <div 
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-30 lg:hidden transition-opacity"
          onClick={toggleSidebar}
        />
      )}
      <aside className={`
        fixed top-0 left-0 z-40 h-screen w-68 bg-white
        transition-transform duration-300 ease-in-out flex flex-col
        border-r border-slate-200/80 shadow-[0_10px_35px_rgba(0,0,0,0.03)]
        ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Brand Header */}
        <div className="h-22 flex items-center px-6 shrink-0 justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-md shadow-blue-500/25">
              <Network className="h-5 w-5" />
            </div>
            <div>
              <div className="font-extrabold text-lg tracking-tight text-slate-900 flex items-center gap-1.5">
                ML MANET
              </div>
              <p className="text-[11px] font-medium text-slate-400">Intelligent Defense</p>
            </div>
          </div>
          <button 
            className="lg:hidden text-slate-400 hover:text-slate-700 p-1.5 rounded-xl hover:bg-slate-100 transition-colors" 
            onClick={toggleSidebar}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-4 py-2 space-y-6">
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 pb-2.5">
              Menu
            </div>
            <div className="space-y-1">
              {MENU_ITEMS.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) => `
                    flex items-center gap-3.5 px-3.5 py-3 rounded-2xl text-sm font-semibold transition-all duration-200 group
                    ${isActive 
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-500/25' 
                      : 'text-slate-500 hover:bg-slate-100/80 hover:text-slate-900'}
                  `}
                  onClick={() => {
                    if (window.innerWidth < 1024) toggleSidebar();
                  }}
                >
                  {({ isActive }) => (
                    <>
                      <item.icon className={`h-5 w-5 transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-700'}`} />
                      <span>{item.name}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>

          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 px-3 pb-2.5">
              Intelligence & Security
            </div>
            <div className="space-y-1">
              {ANALYTICS_ITEMS.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) => `
                    flex items-center gap-3.5 px-3.5 py-3 rounded-2xl text-sm font-semibold transition-all duration-200 group
                    ${isActive 
                      ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-500/25' 
                      : 'text-slate-500 hover:bg-slate-100/80 hover:text-slate-900'}
                  `}
                  onClick={() => {
                    if (window.innerWidth < 1024) toggleSidebar();
                  }}
                >
                  {({ isActive }) => (
                    <>
                      <item.icon className={`h-5 w-5 transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-700'}`} />
                      <span>{item.name}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        </nav>

        {/* Reference Bottom Card (Dark rounded card with pill button) */}
        <div className="p-4 shrink-0">
          <div className="rounded-2xl bg-[#11131a] p-4 text-white relative overflow-hidden shadow-lg shadow-slate-900/10">
            {/* Soft decorative background circles */}
            <div className="absolute -top-6 -right-6 w-24 h-24 bg-blue-500/10 rounded-full blur-xl pointer-events-none"></div>
            <div className="absolute -bottom-6 -left-6 w-24 h-24 bg-purple-500/10 rounded-full blur-xl pointer-events-none"></div>

            <div className="relative z-10">
              {/* <div className="w-8 h-8 rounded-xl bg-white/10 border border-white/15 flex items-center justify-center text-white mb-3">
                <Sparkles className="w-4 h-4 text-blue-400" />
              </div> */}
              <h4 className="font-bold text-sm text-white tracking-tight">MANET Engine</h4>
              <p className="text-[11px] text-slate-400 mt-1 mb-3 leading-relaxed">
                Autonomous trust routing and dynamic anomaly mitigation
              </p>
              <div className="w-full py-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-xs font-bold rounded-xl text-center shadow-xs flex items-center justify-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Live System Active</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
