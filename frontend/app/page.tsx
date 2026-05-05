'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import axios from 'axios';
import StatusBadge from '@/components/StatusBadge';

interface Stats {
  total: number;
  pending_review: number;
  approved: number;
  rejected: number;
  processing: number;
  errors: number;
  ai_recommendations: {
    approve: number;
    reject: number;
    manual_review: number;
  };
}

interface Request {
  request_id: string;
  customer_id: string;
  old_name: string;
  new_name: string;
  status: string;
  ai_recommendation: string | null;
  created_at: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [recentRequests, setRecentRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, requestsRes] = await Promise.all([
        axios.get('/api/v1/checker/stats'),
        axios.get('/api/v1/status/all?limit=10'),
      ]);
      setStats(statsRes.data);
      setRecentRequests(requestsRes.data.requests);
      setError(null);
    } catch (err) {
      setError('Failed to fetch data. Is the backend running?');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <h2 className="text-lg font-semibold text-red-800 mb-2">Connection Error</h2>
          <p className="text-red-600 mb-4">{error}</p>
          <p className="text-sm text-gray-600">
            Make sure the backend is running: <code className="bg-gray-100 px-2 py-1 rounded">uvicorn backend.main:app --reload</code>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-2 text-gray-600">Overview of name change requests and AI verification status</p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="card p-6">
            <div className="text-sm font-medium text-gray-500">Total Requests</div>
            <div className="mt-2 text-3xl font-bold text-gray-900">{stats.total}</div>
          </div>

          <div className="card p-6 border-l-4 border-l-yellow-400">
            <div className="text-sm font-medium text-gray-500">Pending Review</div>
            <div className="mt-2 text-3xl font-bold text-yellow-600">{stats.pending_review}</div>
            <Link href="/checker" className="text-sm text-primary-600 hover:underline mt-2 inline-block">
              Review now →
            </Link>
          </div>

          <div className="card p-6 border-l-4 border-l-green-400">
            <div className="text-sm font-medium text-gray-500">Approved</div>
            <div className="mt-2 text-3xl font-bold text-green-600">{stats.approved}</div>
          </div>

          <div className="card p-6 border-l-4 border-l-red-400">
            <div className="text-sm font-medium text-gray-500">Rejected</div>
            <div className="mt-2 text-3xl font-bold text-red-600">{stats.rejected}</div>
          </div>
        </div>
      )}

      {/* AI Recommendations Summary */}
      {stats && (
        <div className="card p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Recommendations</h2>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-2xl font-bold text-green-600">{stats.ai_recommendations.approve}</div>
              <div className="text-sm text-green-700">Recommend Approve</div>
            </div>
            <div className="text-center p-4 bg-yellow-50 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">{stats.ai_recommendations.manual_review}</div>
              <div className="text-sm text-yellow-700">Manual Review</div>
            </div>
            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-2xl font-bold text-red-600">{stats.ai_recommendations.reject}</div>
              <div className="text-sm text-red-700">Recommend Reject</div>
            </div>
          </div>
        </div>
      )}

      {/* Recent Requests */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900">Recent Requests</h2>
          <Link href="/intake" className="btn-primary text-sm">
            + New Request
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Request ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Customer</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name Change</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">AI Rec.</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Created</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {recentRequests.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    No requests yet. <Link href="/intake" className="text-primary-600 hover:underline">Submit your first request</Link>
                  </td>
                </tr>
              ) : (
                recentRequests.map((request) => (
                  <tr key={request.request_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Link href={`/checker?id=${request.request_id}`} className="text-primary-600 hover:underline font-mono text-sm">
                        {request.request_id}
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {request.customer_id}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <span className="text-gray-500">{request.old_name}</span>
                      <span className="mx-2">→</span>
                      <span className="text-gray-900 font-medium">{request.new_name}</span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {request.ai_recommendation && (
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                          request.ai_recommendation === 'APPROVE' ? 'bg-green-100 text-green-800' :
                          request.ai_recommendation === 'REJECT' ? 'bg-red-100 text-red-800' :
                          'bg-yellow-100 text-yellow-800'
                        }`}>
                          {request.ai_recommendation}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <StatusBadge status={request.status} />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(request.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link href="/intake" className="card p-6 hover:shadow-lg transition-shadow group">
          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-600">Submit New Request</h3>
          <p className="mt-2 text-gray-600">Create a new name change request with document upload</p>
        </Link>
        <Link href="/checker" className="card p-6 hover:shadow-lg transition-shadow group">
          <h3 className="text-lg font-semibold text-gray-900 group-hover:text-primary-600">Checker Dashboard</h3>
          <p className="mt-2 text-gray-600">Review pending requests and approve/reject</p>
        </Link>
      </div>
    </div>
  );
}
