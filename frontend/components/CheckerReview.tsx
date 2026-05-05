'use client';

import { useState } from 'react';

interface Request {
  request_id: string;
  ai_recommendation: string | null;
}

interface CheckerReviewProps {
  request: Request;
  onAction: (action: 'APPROVE' | 'REJECT', notes: string) => Promise<void>;
}

export default function CheckerReview({ request, onAction }: CheckerReviewProps) {
  const [notes, setNotes] = useState('');
  const [processing, setProcessing] = useState(false);
  const [confirmAction, setConfirmAction] = useState<'APPROVE' | 'REJECT' | null>(null);

  const handleAction = async (action: 'APPROVE' | 'REJECT') => {
    if (confirmAction !== action) {
      setConfirmAction(action);
      return;
    }

    setProcessing(true);
    try {
      await onAction(action, notes);
    } finally {
      setProcessing(false);
      setConfirmAction(null);
    }
  };

  const cancelConfirm = () => {
    setConfirmAction(null);
  };

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Checker Action</h3>

      {/* AI Recommendation */}
      {request.ai_recommendation && (
        <div className={`mb-4 p-4 rounded-lg ${
          request.ai_recommendation === 'APPROVE' ? 'bg-green-50 border border-green-200' :
          request.ai_recommendation === 'REJECT' ? 'bg-red-50 border border-red-200' :
          'bg-yellow-50 border border-yellow-200'
        }`}>
          <div className="flex items-center">
            {request.ai_recommendation === 'APPROVE' ? (
              <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : request.ai_recommendation === 'REJECT' ? (
              <svg className="w-5 h-5 text-red-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg className="w-5 h-5 text-yellow-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            )}
            <span className={`font-medium ${
              request.ai_recommendation === 'APPROVE' ? 'text-green-800' :
              request.ai_recommendation === 'REJECT' ? 'text-red-800' :
              'text-yellow-800'
            }`}>
              AI Recommendation: {request.ai_recommendation.replace('_', ' ')}
            </span>
          </div>
        </div>
      )}

      {/* Notes */}
      <div className="mb-4">
        <label htmlFor="notes" className="label">
          Checker Notes (Optional)
        </label>
        <textarea
          id="notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          className="input min-h-[100px]"
          placeholder="Add any notes about your decision..."
        />
      </div>

      {/* Confirmation Message */}
      {confirmAction && (
        <div className={`mb-4 p-4 rounded-lg ${
          confirmAction === 'APPROVE' ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
        }`}>
          <p className={`font-medium ${
            confirmAction === 'APPROVE' ? 'text-green-800' : 'text-red-800'
          }`}>
            {confirmAction === 'APPROVE'
              ? 'Click APPROVE again to confirm. This will update the customer record in core banking.'
              : 'Click REJECT again to confirm. The request will be marked as rejected.'}
          </p>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex space-x-4">
        <button
          onClick={() => handleAction('APPROVE')}
          disabled={processing}
          className={`flex-1 py-3 px-6 rounded-lg font-medium transition-colors ${
            confirmAction === 'APPROVE'
              ? 'bg-green-700 text-white hover:bg-green-800'
              : 'bg-green-600 text-white hover:bg-green-700'
          } disabled:opacity-50`}
        >
          {processing && confirmAction === 'APPROVE' ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Processing...
            </span>
          ) : confirmAction === 'APPROVE' ? (
            'Confirm APPROVE'
          ) : (
            <span className="flex items-center justify-center">
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              APPROVE
            </span>
          )}
        </button>

        <button
          onClick={() => handleAction('REJECT')}
          disabled={processing}
          className={`flex-1 py-3 px-6 rounded-lg font-medium transition-colors ${
            confirmAction === 'REJECT'
              ? 'bg-red-700 text-white hover:bg-red-800'
              : 'bg-red-600 text-white hover:bg-red-700'
          } disabled:opacity-50`}
        >
          {processing && confirmAction === 'REJECT' ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Processing...
            </span>
          ) : confirmAction === 'REJECT' ? (
            'Confirm REJECT'
          ) : (
            <span className="flex items-center justify-center">
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              REJECT
            </span>
          )}
        </button>

        {confirmAction && (
          <button
            onClick={cancelConfirm}
            className="px-4 py-3 rounded-lg font-medium text-gray-600 hover:bg-gray-100 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Warning */}
      <p className="mt-4 text-xs text-gray-500 text-center">
        Actions are final and will be recorded in the audit trail.
      </p>
    </div>
  );
}
