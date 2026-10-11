import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="card not-found-container">
      <div className="not-found-code">404</div>
      <h1 className="page-title" style={{ marginBottom: '8px' }}>Page Not Found</h1>
      <p className="placeholder-text">
        The requested page or route does not exist within the DocumentFlow workspace.
      </p>
      <Link to="/" className="btn-primary" style={{ marginTop: '8px' }}>
        Return to Documents &rarr;
      </Link>
    </div>
  );
}
