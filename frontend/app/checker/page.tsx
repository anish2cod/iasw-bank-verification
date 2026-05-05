'use client';

import { Suspense, useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import axios from 'axios';
import StatusBadge from '@/components/StatusBadge';
import ConfidenceCard from '@/components/ConfidenceCard';
import CheckerReview from '@/components/CheckerReview';
import PipelineProgress from '@/components/PipelineProgress';
import DocumentViewer from '@/components/DocumentViewer';

interface ValidationErrors {
  errors: string[];
  warnings: string[];
  customer_exists: boolean | null;
  name_matches: boolean | null;
  account_active: boolean | null;
}

interface Request {
  request_id: string;
  customer_id: string;
  old_name: string;
  new_name: string;
  request_type: string;
  status: string;
  ai_summary: string | null;
  ai_recommendation: string | null;
  confidence_scores: {
    name_match: number;
    authenticity: number;
    forgery_check: string;
    overall: number;
    details?: any;
  } | null;
  extracted_fields: Record<string, any> | null;
  validation_errors: ValidationErrors | null;
  document_path: string | null;
  checker_id: string | null;
  checker_notes: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

interface RequestList {
  requests: Request[];
  total: number;
  pending_review: number;
}

const PROCESSING_STATUSES = new Set([
  'SUBMITTED', 'VALIDATING', 'PROCESSING_DOCUMENTS', 'SCORING',
]);

function ValidationErrorBanner({ validation }: { validation: ValidationErrors }) {
  const hasErrors = validation.errors && validation.errors.length > 0;
  const hasWarnings = validation.warnings && validation.warnings.length > 0;

  if (!hasErrors && !hasWarnings) return null;

  return (
    <div className={`rounded-lg border p-4 mb-4 ${hasErrors ? 'bg-red-50 border-red-300' : 'bg-yellow-50 border-yellow-300'}`}>
      <div className="flex items-start gap-3">
        {hasErrors ? (
          <svg className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        ) : (
          <svg className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        )}
        <div className="flex-1">
          <p className={`text-sm font-semibold ${hasErrors ? 'text-red-800' : 'text-yellow-800'}`}>
            {hasErrors ? 'Validation Failed — Review Required' : 'Validation Warnings'}
          </p>

          {/* Validation checks */}
          <div className="mt-2 grid grid-cols-3 gap-2">
            {[
              { label: 'Customer Exists', value: validation.customer_exists },
              { label: 'Name Matches', value: validation.name_matches },
              { label: 'Account Active', value: validation.account_active },
            ].map(({ label, value }) => (
              <div key={label} className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded ${
                value === true ? 'bg-green-100 text-green-700' :
                value === false ? 'bg-red-100 text-red-700' :
                'bg-gray-100 text-gray-500'
              }`}>
                {value === true ? '✓' : value === false ? '✗' : '?'} {label}
              </div>
            ))}
          </div>

          {hasErrors && (
            <ul className="mt-2 space-y-1">
              {validation.errors.map((e, i) => (
                <li key={i} className="text-sm text-red-700">• {e}</li>
              ))}
            </ul>
          )}
          {hasWarnings && (
            <ul className="mt-1 space-y-1">
              {validation.warnings.map((w, i) => (
                <li key={i} className="text-sm text-yellow-700">• {w}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckerDashboard() {
  const searchParams = useSearchParams();
  const requestIdParam = searchParams.get('id');

  const [requests, setRequests] = useState<Request[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<Request | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    fetchRequests();
    const interval = setInterval(fetchRequests, 3000); // faster polling for pipeline progress
    return () => clearInterval(interval);
  }, []);

  // Keep selected request in sync with poll results
  useEffect(() => {
    if (requestIdParam && requests.length > 0) {
      const found = requests.find(r => r.request_id === requestIdParam);
      if (found) {
        setSelectedRequest(found);
      } else {
        fetchRequestDetails(requestIdParam);
      }
    }
  }, [requestIdParam, requests]);

  // If a request is selected and still processing, refresh it individually
  useEffect(() => {
    if (!selectedRequest || !PROCESSING_STATUSES.has(selectedRequest.status)) return;
    const t = setInterval(() => fetchRequestDetails(selectedRequest.request_id), 2000);
    return () => clearInterval(t);
  }, [selectedRequest?.request_id, selectedRequest?.status]);

  const fetchRequests = async () => {
    try {
      const response = await axios.get<RequestList>('/api/v1/checker/pending');
      setRequests(response.data.requests);
      setPendingCount(response.data.pending_review);
      setError(null);

      // Sync selected if it's in the list
      if (selectedRequest) {
        const updated = response.data.requests.find(r => r.request_id === selectedRequest.request_id);
        if (updated) setSelectedRequest(updated);
      }
    } catch (err) {
      setError('Failed to fetch requests');
    } finally {
      setLoading(false);
    }
  };

  const fetchRequestDetails = async (requestId: string) => {
    try {
      const response = await axios.get<Request>(`/api/v1/checker/request/${requestId}`);
      setSelectedRequest(response.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleAction = async (action: 'APPROVE' | 'REJECT', notes: string) => {
    if (!selectedRequest) return;
    try {
      await axios.post(`/api/v1/checker/request/${selectedRequest.request_id}/action`, {
        action,
        checker_id: 'CHECKER001',
        notes,
      });
      await fetchRequests();
      await fetchRequestDetails(selectedRequest.request_id);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Action failed');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
      </div>
    );
  }

  const isProcessing = selectedRequest && PROCESSING_STATUSES.has(selectedRequest.status);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Checker Dashboard</h1>
          <p className="mt-2 text-gray-600">Review AI-verified requests and approve or reject</p>
        </div>
        <div className="bg-yellow-100 text-yellow-800 px-4 py-2 rounded-lg font-semibold">
          {pendingCount} Pending Review
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">{error}</div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ---- Request list ---- */}
        <div className="lg:col-span-1">
          <div className="card">
            <div className="px-4 py-3 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Pending Requests</h2>
            </div>
            <div className="divide-y divide-gray-200 max-h-[600px] overflow-y-auto">
              {requests.length === 0 ? (
                <div className="p-6 text-center text-gray-500">No pending requests</div>
              ) : (
                requests.map((request) => (
                  <button
                    key={request.request_id}
                    onClick={() => setSelectedRequest(request)}
                    className={`w-full p-4 text-left hover:bg-gray-50 transition-colors ${
                      selectedRequest?.request_id === request.request_id
                        ? 'bg-primary-50 border-l-4 border-primary-600'
                        : ''
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="min-w-0">
                        <div className="font-mono text-sm text-primary-600">{request.request_id}</div>
                        <div className="font-medium text-gray-900 mt-1">{request.customer_id}</div>
                        <div className="text-sm text-gray-500 mt-1 truncate">
                          {request.old_name} → {request.new_name}
                        </div>
                        {/* Validation error indicator */}
                        {request.validation_errors?.errors?.length ? (
                          <div className="mt-1 text-xs text-red-600 font-medium">⚠ Validation failed</div>
                        ) : null}
                      </div>
                      <div className="text-right flex-shrink-0 ml-2">
                        {request.ai_recommendation && (
                          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                            request.ai_recommendation === 'APPROVE' ? 'bg-green-100 text-green-800' :
                            request.ai_recommendation === 'REJECT' ? 'bg-red-100 text-red-800' :
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {request.ai_recommendation}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* ---- Request detail ---- */}
        <div className="lg:col-span-2">
          {selectedRequest ? (
            <div className="space-y-6">
              {/* Pipeline progress (shown while processing) */}
              {isProcessing && <PipelineProgress status={selectedRequest.status} />}

              {/* Request info */}
              <div className="card p-6">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h2 className="text-xl font-bold text-gray-900">{selectedRequest.request_id}</h2>
                    <p className="text-gray-500">Customer: {selectedRequest.customer_id}</p>
                  </div>
                  <StatusBadge status={selectedRequest.status} />
                </div>

                <div className="grid grid-cols-2 gap-4 mt-4">
                  <div>
                    <div className="text-sm text-gray-500">Current Name</div>
                    <div className="font-medium text-gray-900">{selectedRequest.old_name}</div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-500">Requested Name</div>
                    <div className="font-medium text-gray-900">{selectedRequest.new_name}</div>
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-gray-200">
                  <div className="text-sm text-gray-500">
                    Created: {new Date(selectedRequest.created_at).toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Validation errors — prominent banner */}
              {selectedRequest.validation_errors && (
                <ValidationErrorBanner validation={selectedRequest.validation_errors} />
              )}

              {/* Confidence scores */}
              {selectedRequest.confidence_scores && (
                <ConfidenceCard scores={selectedRequest.confidence_scores} />
              )}

              {/* AI summary */}
              {selectedRequest.ai_summary && (
                <div className="card p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">AI Verification Summary</h3>
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-gray-700 whitespace-pre-wrap">{selectedRequest.ai_summary}</p>
                  </div>
                  {selectedRequest.confidence_scores?.details?.name_details && (
                    <details className="mt-3">
                      <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-700">
                        Name matching details
                      </summary>
                      <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-3 space-y-1">
                        {Object.entries(selectedRequest.confidence_scores.details.name_details)
                          .filter(([k]) => !['request_old_name','request_new_name'].includes(k))
                          .map(([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <span className="font-medium text-gray-500 w-40 flex-shrink-0">{k.replace(/_/g,' ')}:</span>
                              <span>{String(v)}</span>
                            </div>
                          ))}
                      </div>
                    </details>
                  )}
                </div>
              )}

              {/* Document viewer with color-coded score annotations */}
              <DocumentViewer
                requestId={selectedRequest.request_id}
                hasDocument={!!selectedRequest.document_path}
                extractedFields={selectedRequest.extracted_fields}
                confidenceScores={selectedRequest.confidence_scores}
              />

              {/* Action buttons */}
              {(selectedRequest.status === 'AI_VERIFIED_PENDING_HUMAN' ||
                selectedRequest.status === 'AI_FLAGGED_PENDING_HUMAN') && (
                <CheckerReview request={selectedRequest} onAction={handleAction} />
              )}

              {/* Completed */}
              {(selectedRequest.status === 'APPROVED' || selectedRequest.status === 'REJECTED') && (
                <div className={`card p-6 ${
                  selectedRequest.status === 'APPROVED'
                    ? 'bg-green-50 border-green-200'
                    : 'bg-red-50 border-red-200'
                }`}>
                  <h3 className={`text-lg font-semibold ${
                    selectedRequest.status === 'APPROVED' ? 'text-green-800' : 'text-red-800'
                  }`}>
                    {selectedRequest.status === 'APPROVED' ? 'Request Approved' : 'Request Rejected'}
                  </h3>
                  {selectedRequest.checker_id && (
                    <p className="text-sm mt-2">By: {selectedRequest.checker_id}</p>
                  )}
                  {selectedRequest.checker_notes && (
                    <p className="text-sm mt-1">Notes: {selectedRequest.checker_notes}</p>
                  )}
                  {selectedRequest.completed_at && (
                    <p className="text-sm mt-1">
                      Completed: {new Date(selectedRequest.completed_at).toLocaleString()}
                    </p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="card p-12 text-center">
              <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <h3 className="text-lg font-medium text-gray-900">Select a Request</h3>
              <p className="text-gray-500 mt-2">
                Choose a request from the list to view details and take action
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CheckerPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600" />
      </div>
    }>
      <CheckerDashboard />
    </Suspense>
  );
}
