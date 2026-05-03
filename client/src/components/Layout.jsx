import React from 'react';
import Header from './Header';

function Layout({ children }) {
  return (
    <div className="layout">
      <Header />
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

export default Layout;