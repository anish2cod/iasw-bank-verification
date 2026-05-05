'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import IntakeForm from '@/components/IntakeForm';

interface SubmitResponse {
  request_id: string;
  status: string;
}

export default function IntakePage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (formData: FormData) => {
    setSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post('/api/v1/intake/submit', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit request');
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">New Name Change Request</h1>
        <p className="mt-2 text-gray-600">
          Submit a legal name change request with supporting documentation
        </p>
      </div>

      {/* Success Message */}
      {result && (
        <div className="mb-6 bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-center">
            <svg className="w-6 h-6 text-green-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <div>
              <h3 className="text-lg font-semibold text-green-800">Request Submitted Successfully</h3>
              <p className="text-green-700 mt-1">
                Request ID: <span className="font-mono font-bold">{result.request_id}</span>
              </p>
              <p className="text-sm text-green-600 mt-2">
                AI verification is in progress. The request will be queued for human review.
              </p>
            </div>
          </div>
          <div className="mt-4 flex space-x-4">
            <button
              onClick={() => router.push(`/checker?id=${result.request_id}`)}
              className="btn-primary"
            >
              View Status
            </button>
            <button
              onClick={() => {
                setResult(null);
                setError(null);
              }}
              className="btn-secondary"
            >
              Submit Another
            </button>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <svg className="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="text-sm font-medium text-red-800">Submission Failed</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Form */}
      {!result && (
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Request Details</h2>
          </div>
          <div className="p-6">
            <IntakeForm onSubmit={handleSubmit} submitting={submitting} />
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-blue-800 mb-2">How it works</h3>
        <ol className="text-sm text-blue-700 space-y-2">
          <li>1. Fill in the customer details and upload supporting document</li>
          <li>2. AI automatically verifies the document and extracts relevant fields</li>
          <li>3. Confidence scores are calculated based on name matching</li>
          <li>4. Request is queued for human review (Checker Dashboard)</li>
          <li>5. Upon approval, customer record is updated in core banking</li>
        </ol>
      </div>

      {/* Test Data */}
      <div className="mt-6 bg-gray-50 border border-gray-200 rounded-lg p-6">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Test Data (Mock Customers)</h3>
        <div className="text-sm text-gray-600 space-y-1 font-mono">
          <p>C001: Priya Sharma - Active</p>
          <p>C002: Rahul Kumar - Active</p>
          <p>C003: Anita Desai - Active</p>
          <p>C004: Vikram Singh - Dormant</p>
        </div>
      </div>
    </div>
  );
}
