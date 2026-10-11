import React, { useState, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { api } from '../api/client';
import './Layout.css';

export default function Layout() {
  const location = useLocation();
  const [backendState, setBackendState] = useState({
    status: 'checking',
    label: 'Connecting...',
  });

  useEffect(() => {
    let mounted = true;
    api.getHealth()
      .then((data) => {
        if (mounted) {
          setBackendState({
            status: 'online',
            label: data.status === 'healthy' ? 'Connected' : data.status,
          });
        }
      })
      .catch(() => {
        if (mounted) {
          setBackendState({
            status: 'offline',
            label: 'Disconnected',
          });
        }
      });

    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="layout">
      <header className="layout-header">
        <div className="app-container header-content">
          <div className="brand-section">
            <Link to="/" className="brand-link">
              <svg
                className="brand-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
              <span>DocumentFlow</span>
            </Link>
            <span className="brand-badge">Workspace</span>

            <nav className="nav-links">
              <Link
                to="/"
                className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
              >
                Documents
              </Link>
            </nav>
          </div>

          <div className="header-status" title={`API status: ${backendState.label}`}>
            <span
              className={`status-indicator-dot ${backendState.status}`}
              aria-hidden="true"
            />
            <span>API: {backendState.label}</span>
          </div>
        </div>
      </header>

      <main className="layout-main">
        <div className="app-container">
          <Outlet />
        </div>
      </main>

      <footer className="layout-footer">
        <div className="app-container footer-content">
          <span>DocumentFlow &bull; Document Processing & Validation Platform</span>
          <span>Ingestion, Processing & Policy Validation</span>
        </div>
      </footer>
    </div>
  );
}
