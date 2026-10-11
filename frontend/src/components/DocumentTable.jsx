import React from 'react';
import { useNavigate } from 'react-router-dom';
import StatusBadge from './StatusBadge';
import { formatDate, formatFileSize, formatDocumentType } from '../utils/formatters';

export default function DocumentTable({
  documents = [],
  total = 0,
  limit = 20,
  offset = 0,
  loading = false,
  error = null,
  onRetry,
  onPageChange,
}) {
  const navigate = useNavigate();

  const handleRowClick = (id) => {
    navigate(`/documents/${id}`);
  };

  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;
  const startItem = total === 0 ? 0 : offset + 1;
  const endItem = Math.min(offset + documents.length, total);

  if (loading && documents.length === 0) {
    return (
      <div className="table-card">
        <div className="table-state-box">
          <span className="spinner" />
          <span className="state-message">Loading documents...</span>
        </div>
      </div>
    );
  }

  if (error && documents.length === 0) {
    return (
      <div className="table-card">
        <div className="table-state-box error" role="alert" aria-live="assertive">
          <svg
            className="state-icon error"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          <div className="state-title">Unable to load documents</div>
          <p className="state-description">{error}</p>
          {onRetry && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onRetry}
              aria-label="Retry loading documents"
            >
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!loading && documents.length === 0) {
    return (
      <div className="table-card">
        <div className="table-state-box" role="status" aria-live="polite">
          <svg
            className="state-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <div className="state-title">No documents uploaded yet</div>
          <p className="state-description">
            Upload your first scholarship transcript, marksheet, income certificate, or identification document above.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="table-card">
      <div className="table-wrapper">
        <table className="doc-table">
          <thead>
            <tr>
              <th scope="col" className="th-doc">Document</th>
              <th scope="col" className="th-type">Type</th>
              <th scope="col" className="th-date">Uploaded</th>
              <th scope="col" className="th-status">Processing</th>
              <th scope="col" className="th-validation">Validation</th>
              <th scope="col" className="th-action"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              const docType = doc.processing_result?.document_type;
              const valStatus = doc.processing_result?.validation_result?.overall_status;
              const isPdf = doc.original_filename?.toLowerCase().endsWith('.pdf');

              return (
                <tr
                  key={doc.id}
                  className="doc-row"
                  onClick={() => handleRowClick(doc.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleRowClick(doc.id);
                    }
                  }}
                  role="link"
                  aria-label={`Inspect ${doc.original_filename}`}
                >
                  <td className="td-doc">
                    <div className="doc-meta-cell">
                      <div className="doc-icon-wrapper" aria-hidden="true">
                        {isPdf ? (
                          <svg
                            className="file-type-icon pdf"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <path d="M10 12h2a1 1 0 0 1 1 1v0a1 1 0 0 1-1 1h-2v-3" />
                            <path d="M10 15v3" />
                          </svg>
                        ) : (
                          <svg
                            className="file-type-icon img"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                            <circle cx="8.5" cy="8.5" r="1.5" />
                            <polyline points="21 15 16 10 5 21" />
                          </svg>
                        )}
                      </div>
                      <div className="doc-names">
                        <span className="doc-name" title={doc.original_filename}>
                          {doc.original_filename}
                        </span>
                        <span className="doc-size">
                          {formatFileSize(doc.file_size)}
                        </span>
                      </div>
                    </div>
                  </td>

                  <td className="td-type">
                    <span className="doc-type-text">
                      {formatDocumentType(docType)}
                    </span>
                  </td>

                  <td className="td-date">
                    <span className="doc-date-text">
                      {formatDate(doc.created_at)}
                    </span>
                  </td>

                  <td className="td-status">
                    <StatusBadge type="processing" status={doc.status} />
                  </td>

                  <td className="td-validation">
                    <StatusBadge type="validation" status={valStatus} />
                  </td>

                  <td className="td-action">
                    <span className="action-link" aria-hidden="true">
                      Inspect &rarr;
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {total > limit && (
        <div className="table-pagination">
          <span className="pagination-info">
            Showing <strong>{startItem}</strong>&ndash;<strong>{endItem}</strong> of <strong>{total}</strong> documents
          </span>
          <div className="pagination-controls">
            <button
              type="button"
              className="btn-secondary pagination-btn"
              disabled={currentPage <= 1 || loading}
              onClick={() => onPageChange(Math.max(0, offset - limit))}
              aria-label="Previous page"
            >
              &larr; Previous
            </button>
            <span className="page-indicator">
              Page {currentPage} of {totalPages}
            </span>
            <button
              type="button"
              className="btn-secondary pagination-btn"
              disabled={currentPage >= totalPages || loading}
              onClick={() => onPageChange(offset + limit)}
              aria-label="Next page"
            >
              Next &rarr;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
