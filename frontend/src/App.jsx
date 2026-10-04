import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [backendStatus, setBackendStatus] = useState('Checking...');

  useEffect(() => {
    fetch('http://localhost:8000/health')
      .then((res) => res.json())
      .then((data) => setBackendStatus(data.status || 'Online'))
      .catch(() => setBackendStatus('Offline (Backend not running)'));
  }, []);

  return (
    <div className="container">
      <header className="header">
        <h1>DocumentFlow</h1>
        <p className="subtitle">Cloud-Ready Document Processing & Validation Platform</p>
        <span className="badge">Phase 0: Project Setup</span>
      </header>

      <main className="content">
        <div className="card">
          <h2>System Status</h2>
          <div className="status-item">
            <span>Frontend:</span> <strong className="status-online">Online (Vite + React)</strong>
          </div>
          <div className="status-item">
            <span>Backend API:</span>{' '}
            <strong className={backendStatus.includes('Online') ? 'status-online' : 'status-offline'}>
              {backendStatus}
            </strong>
          </div>
        </div>

        <div className="card">
          <h2>Architecture Overview</h2>
          <p>Workflow pipeline under setup:</p>
          <div className="pipeline">
            <span className="step">Upload</span> &rarr;
            <span className="step">Store</span> &rarr;
            <span className="step">Queue</span> &rarr;
            <span className="step">Process</span> &rarr;
            <span className="step">Validate</span> &rarr;
            <span className="step">Result</span> &rarr;
            <span className="step">Notify</span>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;

