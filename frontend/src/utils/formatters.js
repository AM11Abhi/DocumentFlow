/**
 * Format bytes into human-readable file size string
 * @param {number} bytes
 * @returns {string}
 */
export function formatFileSize(bytes) {
  if (bytes == null || isNaN(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format ISO datetime string into concise readable date
 * @param {string} dateStr
 * @returns {string}
 */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    }).format(date);
  } catch {
    return dateStr;
  }
}

/**
 * Format internal enum document types into user-friendly display labels
 * @param {string} type
 * @returns {string}
 */
export function formatDocumentType(type) {
  if (!type) return '—';
  const map = {
    MARKSHEET: 'Marksheet',
    INCOME_CERTIFICATE: 'Income Certificate',
    IDENTITY_DOCUMENT: 'Identity Document',
    RESUME: 'Resume',
  };
  if (map[type]) return map[type];
  return type
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Format camelCase or snake_case object keys into clean display labels
 * @param {string} key
 * @returns {string}
 */
export function formatKeyName(key) {
  if (!key) return '';
  const acronyms = {
    gpa: 'GPA',
    cgpa: 'CGPA',
    id: 'ID',
    dob: 'Date of Birth',
  };
  if (acronyms[key.toLowerCase()]) return acronyms[key.toLowerCase()];
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

