import React from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from '../pages/Dashboard';
import Simulation from '../pages/Simulation';
import NetworkTopology from '../pages/NetworkTopology';
import MLDetection from '../pages/MLDetection';
import Prevention from '../pages/Prevention';
import RouteRecovery from '../pages/RouteRecovery';
import PerformanceMetrics from '../pages/PerformanceMetrics';

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/simulation" element={<Simulation />} />
      <Route path="/network" element={<NetworkTopology />} />
      <Route path="/ml-detection" element={<MLDetection />} />
      <Route path="/prevention" element={<Prevention />} />
      <Route path="/route-recovery" element={<RouteRecovery />} />
      <Route path="/performance" element={<PerformanceMetrics />} />
    </Routes>
  );
};

export default AppRoutes;
