import React, { useState, useRef } from 'react';
import { api } from '../api/client';
import { formatFileSize } from '../utils/formatters';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png'];
const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'image/jpeg',
  'image/png',
];

export default function UploadZone({ onUploadSuccess }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [errorMessage, setErrorMessage] = useState(null);
  const [failedFile, setFailedFile] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const fileInputRef = useRef(null);

  const validateFile = (file) => {
    if (!file) {
      return 'No file selected.';
    }

    if (file.size === 0) {
      return 'The selected file is empty (0 bytes). Please select a valid document.';
    }

    const extension = file.name.split('.').pop()?.toLowerCase();
    const isValidType =
      ALLOWED_MIME_TYPES.includes(file.type) ||
      ALLOWED_EXTENSIONS.includes(extension);

    if (!isValidType) {
      return 'Invalid file type. Only PDF, JPG, JPEG, and PNG files are accepted.';
    }

    if (file.size > MAX_FILE_SIZE) {
      return `File exceeds maximum allowed size of 10 MB (current size: ${formatFileSize(file.size)}). Please choose a smaller file.`;
    }

    return null;
  };

  const handleFile = async (file) => {
    setErrorMessage(null);
    setSuccessMessage(null);

    const validationError = validateFile(file);
    if (validationError) {
      setErrorMessage(validationError);
      setFailedFile(null);
      return;
    }

    setIsUploading(true);
    setUploadProgress(`Uploading ${file.name}...`);

    try {
      const result = await api.uploadDocument(file);
      setSuccessMessage(`Successfully uploaded "${file.name}". Job queued for processing.`);
      setFailedFile(null);
      if (onUploadSuccess) {
        onUploadSuccess(result);
      }
    } catch (err) {
      setErrorMessage(err.message || 'Failed to upload document. Please check connection and try again.');
      setFailedFile(file);
    } finally {
      setIsUploading(false);
      setUploadProgress('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) {
      setIsDragging(true);
    }
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (isUploading) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      handleFile(droppedFile);
    }
  };

  const onFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const selectedFile = e.target.files[0];
      handleFile(selectedFile);
    }
  };

  const triggerFileSelect = () => {
    if (!isUploading && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="upload-section">
      <div
        className={`upload-dropzone ${isDragging ? 'dragging' : ''} ${isUploading ? 'uploading' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={triggerFileSelect}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            triggerFileSelect();
          }
        }}
        aria-label="Upload document dropzone: press Enter or Space to browse files, or drag and drop files here"
        aria-busy={isUploading}
      >
        <input
          ref={fileInputRef}
          type="file"
          id="file-upload-input"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          onChange={onFileInputChange}
          style={{ display: 'none' }}
          disabled={isUploading}
          aria-label="Choose document file to upload"
        />

        <div className="upload-content">
          <div className="upload-icon-wrapper" aria-hidden="true">
            {isUploading ? (
              <span className="spinner" />
            ) : (
              <svg
                className="upload-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            )}
          </div>

          <div className="upload-text-group">
            {isUploading ? (
              <div className="upload-title">{uploadProgress}</div>
            ) : (
              <>
                <div className="upload-title">
                  <span className="upload-highlight">Choose a file</span> or drag it here
                </div>
                <div className="upload-hint">
                  Supports PDF, JPEG, or PNG &bull; Up to 10 MB
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="alert alert-error" role="alert" aria-live="assertive">
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
            <span className="alert-message">{errorMessage}</span>
            {failedFile && (
              <button
                type="button"
                className="alert-retry-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  handleFile(failedFile);
                }}
                aria-label={`Retry uploading ${failedFile.name}`}
              >
                Retry upload
              </button>
            )}
          </div>
          <button
            type="button"
            className="alert-dismiss"
            onClick={(e) => {
              e.stopPropagation();
              setErrorMessage(null);
              setFailedFile(null);
            }}
            aria-label="Dismiss error notification"
          >
            &times;
          </button>
        </div>
      )}

      {successMessage && (
        <div className="alert alert-success" role="status" aria-live="polite">
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
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          <span className="alert-message">{successMessage}</span>
          <button
            type="button"
            className="alert-dismiss"
            onClick={(e) => {
              e.stopPropagation();
              setSuccessMessage(null);
            }}
            aria-label="Dismiss success notice"
          >
            &times;
          </button>
        </div>
      )}
    </div>
  );
}
