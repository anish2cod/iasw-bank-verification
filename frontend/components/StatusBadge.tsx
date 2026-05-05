'use client';

interface StatusBadgeProps {
  status: string;
}

const statusConfig: Record<string, { color: string; label: string }> = {
  SUBMITTED: { color: 'bg-gray-100 text-gray-800', label: 'Submitted' },
  VALIDATING: { color: 'bg-blue-100 text-blue-800', label: 'Validating' },
  PROCESSING_DOCUMENTS: { color: 'bg-blue-100 text-blue-800', label: 'Processing' },
  SCORING: { color: 'bg-blue-100 text-blue-800', label: 'Scoring' },
  AI_VERIFIED_PENDING_HUMAN: { color: 'bg-yellow-100 text-yellow-800', label: 'Pending Review' },
  AI_FLAGGED_PENDING_HUMAN: { color: 'bg-orange-100 text-orange-800', label: 'Flagged - Review' },
  APPROVED: { color: 'bg-green-100 text-green-800', label: 'Approved' },
  REJECTED: { color: 'bg-red-100 text-red-800', label: 'Rejected' },
  ERROR: { color: 'bg-red-100 text-red-800', label: 'Error' },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', label: status };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
      {/* Status indicator dot */}
      {(status === 'VALIDATING' || status === 'PROCESSING_DOCUMENTS' || status === 'SCORING') && (
        <span className="w-2 h-2 mr-1.5 bg-blue-500 rounded-full animate-pulse"></span>
      )}
      {status === 'AI_VERIFIED_PENDING_HUMAN' && (
        <span className="w-2 h-2 mr-1.5 bg-yellow-500 rounded-full"></span>
      )}
      {status === 'AI_FLAGGED_PENDING_HUMAN' && (
        <span className="w-2 h-2 mr-1.5 bg-orange-500 rounded-full"></span>
      )}
      {status === 'APPROVED' && (
        <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
      )}
      {status === 'REJECTED' && (
        <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
        </svg>
      )}
      {config.label}
    </span>
  );
}
