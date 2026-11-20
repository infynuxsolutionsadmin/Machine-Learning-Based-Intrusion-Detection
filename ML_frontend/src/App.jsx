import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import AppRoutes from './router/AppRoutes';
import PageWrapper from './components/layout/PageWrapper';
import { RunProvider } from './context/RunContext';

function App() {
  return (
    <BrowserRouter>
      <RunProvider>
        <PageWrapper>
          <AppRoutes />
        </PageWrapper>
      </RunProvider>
    </BrowserRouter>
  );
}

export default App;
