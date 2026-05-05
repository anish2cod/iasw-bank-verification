'use client';

interface ConfidenceScores {
  name_match: number;
  authenticity: number;
  forgery_check: string;
  overall: number;
}

interface ConfidenceCardProps {
  scores: ConfidenceScores;
}

function ProgressBar({ value, color }: { value: number; color: string }) {
  const percentage = Math.round(value * 100);

  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm font-medium text-gray-700 w-12 text-right">{percentage}%</span>
    </div>
  );
}

function getScoreColor(score: number): string {
  if (score >= 0.9) return 'bg-green-500';
  if (score >= 0.7) return 'bg-yellow-500';
  if (score >= 0.5) return 'bg-orange-500';
  return 'bg-red-500';
}

export default function ConfidenceCard({ scores }: ConfidenceCardProps) {
  const overallPercentage = Math.round(scores.overall * 100);

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Confidence Scores</h3>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Overall Score */}
        <div className="md:col-span-2 flex items-center justify-center p-4 bg-gray-50 rounded-lg">
          <div className="text-center">
            <div className={`text-5xl font-bold ${
              scores.overall >= 0.9 ? 'text-green-600' :
              scores.overall >= 0.7 ? 'text-yellow-600' :
              scores.overall >= 0.5 ? 'text-orange-600' :
              'text-red-600'
            }`}>
              {overallPercentage}%
            </div>
            <div className="text-sm text-gray-500 mt-1">Overall Confidence</div>
          </div>
        </div>

        {/* Individual Scores */}
        <div className="space-y-4">
          <div>
            <div className="flex justify-between mb-1">
              <span className="text-sm font-medium text-gray-600">Name Match</span>
            </div>
            <ProgressBar value={scores.name_match} color={getScoreColor(scores.name_match)} />
          </div>

          <div>
            <div className="flex justify-between mb-1">
              <span className="text-sm font-medium text-gray-600">Document Authenticity</span>
            </div>
            <ProgressBar value={scores.authenticity} color={getScoreColor(scores.authenticity)} />
          </div>
        </div>

        {/* Forgery Check */}
        <div className="flex items-center justify-center">
          <div className={`text-center p-4 rounded-lg ${
            scores.forgery_check === 'PASS' ? 'bg-green-50' :
            scores.forgery_check === 'FAIL' ? 'bg-red-50' :
            'bg-yellow-50'
          }`}>
            <div className="flex items-center justify-center mb-2">
              {scores.forgery_check === 'PASS' ? (
                <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              ) : scores.forgery_check === 'FAIL' ? (
                <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              ) : (
                <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </div>
            <div className={`text-sm font-semibold ${
              scores.forgery_check === 'PASS' ? 'text-green-700' :
              scores.forgery_check === 'FAIL' ? 'text-red-700' :
              'text-yellow-700'
            }`}>
              Forgery Check: {scores.forgery_check}
            </div>
          </div>
        </div>
      </div>

      {/* Score Legend */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <div className="flex justify-center space-x-6 text-xs">
          <div className="flex items-center">
            <div className="w-3 h-3 bg-green-500 rounded-full mr-1"></div>
            <span className="text-gray-500">90%+ High</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-yellow-500 rounded-full mr-1"></div>
            <span className="text-gray-500">70-90% Medium</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-orange-500 rounded-full mr-1"></div>
            <span className="text-gray-500">50-70% Low</span>
          </div>
          <div className="flex items-center">
            <div className="w-3 h-3 bg-red-500 rounded-full mr-1"></div>
            <span className="text-gray-500">&lt;50% Critical</span>
          </div>
        </div>
      </div>
    </div>
  );
}
