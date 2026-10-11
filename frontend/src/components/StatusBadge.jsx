import React from 'react';

/**
 * StatusBadge component for processing and validation states
 *
 * @param {'processing' | 'validation'} type
 * @param {string} status
 */
export default function StatusBadge({ type = 'processing', status }) {
  if (!status) {
    return <span className="status-badge-empty">—</span>;
  }

  const normalized = String(status).toUpperCase();

  if (type === 'validation') {
    switch (normalized) {
      case 'PASS':
        return (
          <span className="badge badge-pass">
            <span className="badge-dot badge-dot-pass" />
            PASS
          </span>
        );
      case 'FAIL':
        return (
          <span className="badge badge-fail">
            <span className="badge-dot badge-dot-fail" />
            FAIL
          </span>
        );
      case 'REVIEW':
        return (
          <span className="badge badge-review">
            <span className="badge-dot badge-dot-review" />
            REVIEW
          </span>
        );
      default:
        return <span className="badge badge-neutral">{status}</span>;
    }
  }

  // Processing status
  switch (normalized) {
    case 'COMPLETED':
      return (
        <span className="badge badge-completed">
          <span className="badge-dot badge-dot-completed" />
          Completed
        </span>
      );
    case 'PROCESSING':
      return (
        <span className="badge badge-processing">
          <span className="badge-dot badge-dot-processing pulse" />
          Processing
        </span>
      );
    case 'QUEUED':
      return (
        <span className="badge badge-queued">
          <span className="badge-dot badge-dot-queued pulse" />
          Queued
        </span>
      );
    case 'FAILED':
      return (
        <span className="badge badge-failed">
          <span className="badge-dot badge-dot-failed" />
          Failed
        </span>
      );
    case 'UPLOADED':
      return (
        <span className="badge badge-uploaded">
          <span className="badge-dot badge-dot-uploaded" />
          Uploaded
        </span>
      );
    default:
      return <span className="badge badge-neutral">{status}</span>;
  }
}
