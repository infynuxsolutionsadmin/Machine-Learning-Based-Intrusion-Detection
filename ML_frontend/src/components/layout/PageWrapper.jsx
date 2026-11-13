import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Navbar from './Navbar';

const PageWrapper = ({ children }) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const toggleSidebar = () => {
    setIsSidebarOpen(!isSidebarOpen);
  };

  return (
    <div className="min-h-screen bg-[#ebedf7] text-slate-800 flex flex-col lg:flex-row font-sans selection:bg-blue-100 selection:text-blue-900">
      <Sidebar isOpen={isSidebarOpen} toggleSidebar={toggleSidebar} />
      
      <div className="flex-1 flex flex-col min-w-0 lg:pl-68 transition-all duration-300">
        <Navbar toggleSidebar={toggleSidebar} />
        
        <main className="flex-1 px-4 sm:px-6 lg:px-8 pb-12 overflow-y-auto">
          <div className="max-w-[1400px] mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

export default PageWrapper;
