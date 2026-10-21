import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import AppRoutes from './router/AppRoutes';
import PageWrapper from './components/layout/PageWrapper';

function App() {
  return (
    <BrowserRouter>
      <PageWrapper>
        <AppRoutes />
      </PageWrapper>
    </BrowserRouter>
  );
}

export default App;
