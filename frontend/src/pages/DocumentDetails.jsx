import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import StatusBadge from '../components/StatusBadge';
import { api } from '../api/client';
import {
  formatDate,
  formatFileSize,
  formatDocumentType,
  formatKeyName,
} from '../utils/formatters';

const POLL_INTERVAL_MS = 2500;

export default function DocumentDetails() {
  const { id } = useParams();

  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const [isRetrying, setIsRetrying] = useState(false);
  const [retryError, setRetryError] = useState(null);
  const [copiedId, setCopiedId] = useState(false);
  const [copiedText, setCopiedText] = useState(false);
  const [isTextExpanded, setIsTextExpanded] = useState(false);

  const isMountedRef = useRef(true);
  const isPollingRef = useRef(false);
  const consecutivePollFailuresRef = useRef(0);
  const activeDocIdRef = useRef(id);
  const isLoadingRef = useRef(loading);

  // Synchronize refs outside of render body
  useEffect(() => {
    activeDocIdRef.current = id;
    isLoadingRef.current = loading;
  }, [id, loading]);

  // Fetch document details on mount, id change, or explicit refresh
  useEffect(() => {
    isMountedRef.current = true;
    let cancelled = false;

    if (!id) {
      return;
    }

    api.getDocument(id)
      .then((data) => {
        if (!cancelled && isMountedRef.current) {
          consecutivePollFailuresRef.current = 0;
          setDocument(data);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled && isMountedRef.current) {
          const isNotFound = err.status === 404;
          setError({
            message: isNotFound
              ? 'Document not found. The specified document does not exist or may have been removed.'
              : err.message || 'Failed to retrieve document details.',
            isNotFound,
          });
          setLoading(false);
          // Preserve existing document if already loaded during failed refresh
        }
      });

    return () => {
      cancelled = true;
      isMountedRef.current = false;
    };
  }, [id, refreshTrigger]);

  // Determine if document processing is actively running
  const hasActiveJob =
    document &&
    (document.status === 'UPLOADED' ||
      document.status === 'PROCESSING' ||
      document.processing_job?.status === 'QUEUED' ||
      document.processing_job?.status === 'PROCESSING');

  // Background polling for active jobs
  useEffect(() => {
    if (!hasActiveJob || !id) {
      return;
    }

    const timer = setInterval(() => {
      if (isPollingRef.current) {
        return;
      }
      // Pause polling after 5 consecutive failures to prevent uncontrolled loops
      if (consecutivePollFailuresRef.current >= 5) {
        return;
      }

      isPollingRef.current = true;

      api.getDocument(id)
        .then((data) => {
          consecutivePollFailuresRef.current = 0;
          // Guard against stale response overwriting an updated document id or foreground refresh
          if (
            isMountedRef.current &&
            activeDocIdRef.current === id &&
            !isLoadingRef.current
          ) {
            setDocument(data);
          }
        })
        .catch(() => {
          consecutivePollFailuresRef.current += 1;
        })
        .finally(() => {
          isPollingRef.current = false;
        });
    }, POLL_INTERVAL_MS);

    return () => {
      clearInterval(timer);
    };
  }, [hasActiveJob, id]);

  const handleCopyId = () => {
    if (!id) return;
    navigator.clipboard.writeText(id);
    setCopiedId(true);
    setTimeout(() => {
      if (isMountedRef.current) {
        setCopiedId(false);
      }
    }, 2000);
  };

  const handleCopyText = (text) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedText(true);
    setTimeout(() => {
      if (isMountedRef.current) {
        setCopiedText(false);
      }
    }, 2000);
  };

  // Strictly guarded retry job submission to prevent duplicate concurrent executions
  const handleRetryJob = async () => {
    if (!id || isRetrying) return;
    setIsRetrying(true);
    setRetryError(null);

    try {
      const updatedDoc = await api.retryJob(id);
      if (isMountedRef.current) {
        setDocument(updatedDoc);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setRetryError(err.message || 'Failed to retry processing job. Please check connection and try again.');
      }
    } finally {
      if (isMountedRef.current) {
        setIsRetrying(false);
      }
    }
  };

  const handleManualRefresh = () => {
    setLoading(true);
    setRefreshTrigger((prev) => prev + 1);
  };

  if (!id) {
    return (
      <div className="details-container">
        <Link to="/" className="back-nav" aria-label="Return to documents list">
          &larr; Back to documents
        </Link>
        <div className="card table-state-box error" role="alert">
          <div className="state-title">No Document ID Specified</div>
          <p className="state-description">Please choose a valid document from the dashboard.</p>
          <Link to="/" className="btn-primary" style={{ marginTop: '12px' }}>
            &larr; Return to Documents
          </Link>
        </div>
      </div>
    );
  }

  if (loading && !document) {
    return (
      <div className="details-container">
        <Link to="/" className="back-nav" aria-label="Return to documents list">
          &larr; Back to documents
        </Link>
        <div className="card table-state-box" role="status" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          <span className="state-message">Loading document details...</span>
        </div>
      </div>
    );
  }

  if (error && !document) {
    return (
      <div className="details-container">
        <Link to="/" className="back-nav" aria-label="Return to documents list">
          &larr; Back to documents
        </Link>
        <div className="card table-state-box error" role="alert" aria-live="assertive">
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
          <div className="state-title">
            {error.isNotFound ? 'Document Not Found' : 'Error Loading Document'}
          </div>
          <p className="state-description">{error.message}</p>
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <Link to="/" className="btn-primary">
              &larr; Return to Documents
            </Link>
            {!error.isNotFound && (
              <button
                type="button"
                className="btn-secondary"
                onClick={handleManualRefresh}
                aria-label="Retry loading document details"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const job = document?.processing_job;
  const result = document?.processing_result;
  const validation = result?.validation_result;
  const isFailed = job?.status === 'FAILED' || document?.status === 'FAILED';
  const canRetry = isFailed && job != null && (job.attempts || 0) < 3;
  const maxAttemptsReached = isFailed && job != null && (job.attempts || 0) >= 3;

  const extractedDataEntries =
    result?.extracted_data && typeof result.extracted_data === 'object'
      ? Object.entries(result.extracted_data)
      : [];

  const matchedSignalsList = Array.isArray(result?.matched_signals)
    ? result.matched_signals
    : [];

  return (
    <div className="details-container">
      <Link to="/" className="back-nav" aria-label="Return to documents list">
        <svg
          className="back-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="19" y1="12" x2="5" y2="12" />
          <polyline points="12 19 5 12 12 5" />
        </svg>
        <span>Back to documents</span>
      </Link>

      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="details-header-title-row">
            <h1 className="page-title">{document.original_filename}</h1>
            <div className="doc-id-pill" title="Document identifier">
              <code>{document.id}</code>
              <button
                type="button"
                className="btn-copy-id"
                onClick={handleCopyId}
                aria-label={copiedId ? 'Document ID copied to clipboard' : 'Copy Document ID'}
              >
                <span aria-live="polite">{copiedId ? 'Copied' : 'Copy ID'}</span>
              </button>
            </div>
          </div>
          <p className="page-description">
            Uploaded on {formatDate(document.created_at)} &bull; {formatFileSize(document.file_size)}
          </p>
        </div>

        <div className="header-actions">
          {hasActiveJob && (
            <span className="live-status-pill" title="Polling for active processing job">
              <span className="badge-dot badge-dot-processing pulse" />
              Processing active
            </span>
          )}

          {canRetry && (
            <button
              type="button"
              className="btn-primary"
              onClick={handleRetryJob}
              disabled={isRetrying}
              aria-busy={isRetrying}
              aria-label={isRetrying ? 'Retrying processing job' : 'Retry failed processing job'}
            >
              {isRetrying ? (
                <>
                  <span className="spinner" aria-hidden="true" />
                  Retrying...
                </>
              ) : (
                'Retry Processing'
              )}
            </button>
          )}

          {maxAttemptsReached && (
            <span className="badge badge-failed" title="Maximum retries exceeded">
              Max retries reached (3/3)
            </span>
          )}

          <button
            type="button"
            className="btn-secondary"
            onClick={handleManualRefresh}
            title="Refresh document state"
            aria-label="Refresh document details"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Display non-destructive alert if refresh fails while retaining existing document view */}
      {error && document && (
        <div className="alert alert-error" role="alert" aria-live="polite" style={{ marginBottom: '20px' }}>
          <svg
            className="alert-icon"
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
          <div className="alert-body">
            <span className="alert-message">
              <strong>Failed to refresh document details: </strong>{error.message}
            </span>
            <button
              type="button"
              className="alert-retry-btn"
              onClick={handleManualRefresh}
            >
              Retry
            </button>
          </div>
          <button
            type="button"
            className="alert-dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss refresh error notification"
          >
            &times;
          </button>
        </div>
      )}

      {/* Retry Job Error Alert */}
      {retryError && (
        <div className="alert alert-error" role="alert" aria-live="assertive" style={{ marginBottom: '20px' }}>
          <svg
            className="alert-icon"
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
          <div className="alert-body">
            <span className="alert-message">
              <strong>Job retry failed: </strong>{retryError}
            </span>
            <button
              type="button"
              className="alert-retry-btn"
              onClick={handleRetryJob}
              disabled={isRetrying}
            >
              Retry
            </button>
          </div>
          <button
            type="button"
            className="alert-dismiss"
            onClick={() => setRetryError(null)}
            aria-label="Dismiss retry error notification"
          >
            &times;
          </button>
        </div>
      )}

      {/* Main Grid: Overview & Pipeline Meta */}
      <div className="details-grid">
        {/* Document Overview Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Document & Job Status</h2>
            <p className="card-subtitle">File specifications and pipeline execution</p>
          </div>

          <div className="details-meta-grid">
            <div className="meta-item">
              <div className="meta-label">Document Status</div>
              <div className="meta-value">
                <StatusBadge type="processing" status={document.status} />
              </div>
            </div>

            <div className="meta-item">
              <div className="meta-label">Processing Job</div>
              <div className="meta-value">
                {job ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <StatusBadge type="processing" status={job.status} />
                    <span className="meta-subtext">
                      (Attempt {job.attempts}/3)
                    </span>
                  </div>
                ) : (
                  'No job created'
                )}
              </div>
            </div>

            <div className="meta-item">
              <div className="meta-label">Content Type</div>
              <div className="meta-value">
                <code>{document.content_type}</code>
              </div>
            </div>

            <div className="meta-item">
              <div className="meta-label">File Size</div>
              <div className="meta-value">
                {formatFileSize(document.file_size)}
              </div>
            </div>
          </div>

          {job?.error && (
            <div className="job-error-box">
              <div className="job-error-label">Job Error Details</div>
              <div className="job-error-message">{job.error}</div>
            </div>
          )}
        </div>

        {/* Classification & Detection Card */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Type Detection</h2>
            <p className="card-subtitle">Automated classification and heuristic signals</p>
          </div>

          {result ? (
            <div className="details-meta-grid">
              <div className="meta-item">
                <div className="meta-label">Detected Type</div>
                <div className="meta-value">
                  <strong>{formatDocumentType(result.document_type)}</strong>
                </div>
              </div>

              <div className="meta-item">
                <div className="meta-label">Detection Score</div>
                <div className="meta-value">
                  {result.detection_score != null ? (
                    <span><strong>{result.detection_score}</strong> / 100</span>
                  ) : (
                    '—'
                  )}
                </div>
              </div>

              <div className="meta-item" style={{ gridColumn: '1 / -1' }}>
                <div className="meta-label">Matched Heuristic Signals</div>
                <div className="signals-container">
                  {matchedSignalsList.length > 0 ? (
                    matchedSignalsList.map((sig, idx) => (
                      <span key={idx} className="signal-chip">
                        {sig}
                      </span>
                    ))
                  ) : (
                    <span className="meta-subtext">No explicit signals recorded</span>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="section-empty-notice">
              {hasActiveJob
                ? 'Type detection will appear once document processing completes.'
                : 'No processing result recorded for this document.'}
            </div>
          )}
        </div>
      </div>

      {/* Validation Results Section (Presented Separately from Processing) */}
      <div className="card section-spacing">
        <div className="card-header validation-header-row">
          <div>
            <h2 className="card-title">Policy Validation Evaluation</h2>
            <p className="card-subtitle">
              {validation ? (
                <>
                  Evaluated under policy <strong>{validation.policy_id}</strong> (v{validation.policy_version})
                </>
              ) : (
                'Validation outcome is evaluated independently from job completion'
              )}
            </p>
          </div>

          {validation && (
            <div className="validation-overall-badge">
              <span className="meta-label" style={{ marginBottom: 0 }}>Outcome:</span>
              <StatusBadge type="validation" status={validation.overall_status} />
            </div>
          )}
        </div>

        {validation ? (
          validation.checks && validation.checks.length > 0 ? (
            <div className="table-wrapper">
              <table className="doc-table checks-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: '160px' }}>Rule</th>
                    <th scope="col" style={{ width: '110px' }}>Status</th>
                    <th scope="col" style={{ width: '130px' }}>Expected</th>
                    <th scope="col" style={{ width: '130px' }}>Actual</th>
                    <th scope="col">Evaluation Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {validation.checks.map((check, idx) => (
                    <tr key={idx} className="check-row">
                      <td className="td-rule">
                        <code>{check.rule_id}</code>
                      </td>
                      <td>
                        <StatusBadge type="validation" status={check.status} />
                      </td>
                      <td className="td-expected">
                        <code>{check.expected || '—'}</code>
                      </td>
                      <td className="td-actual">
                        <code>{check.actual || '—'}</code>
                      </td>
                      <td className="td-reason">
                        {check.reason || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="section-empty-notice">
              No individual policy checks recorded.
            </div>
          )
        ) : (
          <div className="section-empty-notice">
            {hasActiveJob
              ? 'Policy validation evaluation is in progress...'
              : 'No validation evaluation exists for this document.'}
          </div>
        )}
      </div>

      {/* Extracted Structured Data Section */}
      <div className="card section-spacing">
        <div className="card-header">
          <h2 className="card-title">Extracted Structured Information</h2>
          <p className="card-subtitle">Deterministic parsed fields from document content</p>
        </div>

        {extractedDataEntries.length > 0 ? (
          <div className="key-value-grid">
            {extractedDataEntries.map(([key, val]) => (
              <div key={key} className="kv-item">
                <div className="kv-key">{formatKeyName(key)}</div>
                <div className="kv-value">
                  {typeof val === 'object' && val !== null ? (
                    <code>{JSON.stringify(val)}</code>
                  ) : (
                    String(val)
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="section-empty-notice">
            {hasActiveJob
              ? 'Structured data extraction will populate upon job completion.'
              : 'No structured fields were extracted from this document.'}
          </div>
        )}
      </div>

      {/* Extracted Text Section (Expandable/Collapsible) */}
      <div className="card section-spacing">
        <div className="card-header text-header-row">
          <div>
            <h2 className="card-title">Extracted Document Text</h2>
            <p className="card-subtitle">
              {result?.extracted_text
                ? `Extracted text length: ${result.extracted_text.length} characters`
                : 'Raw text extracted by parser'}
            </p>
          </div>

          {result?.extracted_text && (
            <div className="header-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => handleCopyText(result.extracted_text)}
                aria-label={copiedText ? 'Extracted text copied to clipboard' : 'Copy extracted text'}
              >
                <span aria-live="polite">{copiedText ? 'Copied Text' : 'Copy Text'}</span>
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setIsTextExpanded((prev) => !prev)}
                aria-expanded={isTextExpanded}
                aria-controls="extracted-text-content"
              >
                {isTextExpanded ? 'Collapse Text' : 'Expand Text'}
              </button>
            </div>
          )}
        </div>

        {result?.extracted_text ? (
          <div className="extracted-text-wrapper">
            <pre
              id="extracted-text-content"
              className={`extracted-text-box ${isTextExpanded ? 'expanded' : ''}`}
            >
              {result.extracted_text}
            </pre>
            {!isTextExpanded && (
              <div
                className="text-overlay-hint"
                onClick={() => setIsTextExpanded(true)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setIsTextExpanded(true);
                  }
                }}
                aria-label="Expand full extracted text"
              >
                Click to expand full extracted content &darr;
              </div>
            )}
          </div>
        ) : (
          <div className="section-empty-notice">
            {hasActiveJob
              ? 'Text extraction is currently in progress...'
              : 'No text content extracted for this document.'}
          </div>
        )}
      </div>
    </div>
  );
}
