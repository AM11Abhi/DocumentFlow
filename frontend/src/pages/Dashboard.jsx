import React, { useState, useEffect, useRef } from 'react';
import UploadZone from '../components/UploadZone';
import DocumentTable from '../components/DocumentTable';
import { api } from '../api/client';

const PAGE_SIZE = 20;
const POLL_INTERVAL_MS = 2500;

export default function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const isMountedRef = useRef(true);
  const isPollingRef = useRef(false);
  const consecutivePollFailuresRef = useRef(0);
  const activeOffsetRef = useRef(offset);
  const isLoadingRef = useRef(loading);

  // Synchronize refs outside of render body
  useEffect(() => {
    activeOffsetRef.current = offset;
    isLoadingRef.current = loading;
  }, [offset, loading]);

  // Load documents on mount, offset change, or explicit refresh
  useEffect(() => {
    isMountedRef.current = true;
    let cancelled = false;

    api.listDocuments(PAGE_SIZE, offset)
      .then((data) => {
        if (!cancelled && isMountedRef.current) {
          consecutivePollFailuresRef.current = 0;

          // Guard pagination boundary: if items were deleted and current offset >= total
          if (offset > 0 && offset >= data.total) {
            const lastValidOffset =
              data.total > 0
                ? Math.floor((data.total - 1) / PAGE_SIZE) * PAGE_SIZE
                : 0;
            setOffset(lastValidOffset);
            return;
          }

          setDocuments(data.items || []);
          setTotal(data.total || 0);
          setError(null);
          setLoading(false);
          setIsRefreshing(false);
        }
      })
      .catch((err) => {
        if (!cancelled && isMountedRef.current) {
          setError(err.message || 'Failed to retrieve document listing.');
          setLoading(false);
          setIsRefreshing(false);
          // Preserve existing documents instead of wiping with empty array
        }
      });

    return () => {
      cancelled = true;
      isMountedRef.current = false;
    };
  }, [offset, refreshTrigger]);

  // Determine if any documents currently in view are actively processing or queued
  const hasActiveJobs = documents.some((doc) => {
    const docStatus = doc.status;
    const jobStatus = doc.processing_job?.status;
    return (
      docStatus === 'UPLOADED' ||
      docStatus === 'PROCESSING' ||
      jobStatus === 'QUEUED' ||
      jobStatus === 'PROCESSING'
    );
  });

  // Background polling for active processing jobs
  useEffect(() => {
    if (!hasActiveJobs) {
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

      api.listDocuments(PAGE_SIZE, offset)
        .then((data) => {
          consecutivePollFailuresRef.current = 0;
          // Guard against stale response overwriting a changed page or foreground refresh
          if (
            isMountedRef.current &&
            activeOffsetRef.current === offset &&
            !isLoadingRef.current
          ) {
            setDocuments(data.items || []);
            setTotal(data.total || 0);
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
  }, [hasActiveJobs, offset]);

  const handleUploadSuccess = () => {
    setError(null);
    setLoading(true);
    if (offset !== 0) {
      setOffset(0);
    } else {
      setRefreshTrigger((prev) => prev + 1);
    }
  };

  const handleManualRefresh = () => {
    setIsRefreshing(true);
    setLoading(true);
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleRetry = () => {
    setError(null);
    setLoading(true);
    setRefreshTrigger((prev) => prev + 1);
  };

  const handlePageChange = (newOffset) => {
    const clampedOffset = Math.max(0, newOffset);
    setLoading(true);
    setOffset(clampedOffset);
  };

  return (
    <div className="dashboard">
      <div className="page-header">
        <div>
          <h1 className="page-title">Documents</h1>
          <p className="page-description">
            Upload and monitor document ingestion, processing pipeline, and policy validation.
          </p>
        </div>

        <div className="header-actions">
          {hasActiveJobs && (
            <span className="live-status-pill" title="Polling for processing updates">
              <span className="badge-dot badge-dot-processing pulse" />
              Active processing
            </span>
          )}
          <button
            type="button"
            className="btn-secondary refresh-btn"
            onClick={handleManualRefresh}
            disabled={loading || isRefreshing}
            aria-label="Refresh document list"
          >
            <svg
              className={`btn-icon ${isRefreshing ? 'spin' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="23 4 23 10 17 10" />
              <polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      <UploadZone onUploadSuccess={handleUploadSuccess} />

      <div className="dashboard-content-area">
        <div className="section-header">
          <h2 className="section-title">
            All Documents
            {total > 0 && <span className="section-count">({total})</span>}
          </h2>
        </div>

        {/* Display non-destructive alert if refresh fails while retaining existing documents */}
        {error && documents.length > 0 && (
          <div className="alert alert-error" role="alert" aria-live="polite">
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
                <strong>Failed to refresh documents: </strong>{error}
              </span>
              <button
                type="button"
                className="alert-retry-btn"
                onClick={handleRetry}
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

        <DocumentTable
          documents={documents}
          total={total}
          limit={PAGE_SIZE}
          offset={offset}
          loading={loading}
          error={error}
          onRetry={handleRetry}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  );
}
