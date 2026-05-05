'use client';

const STAGES = [
  { key: 'SUBMITTED', label: 'Submitted', icon: '📋' },
  { key: 'VALIDATING', label: 'Validating Customer', icon: '🔍' },
  { key: 'PROCESSING_DOCUMENTS', label: 'Reading Document', icon: '📄' },
  { key: 'SCORING', label: 'AI Scoring', icon: '🧠' },
  { key: 'COMPLETE', label: 'Human Review', icon: '✅' },
];

const COMPLETE_STATUSES = new Set([
  'AI_VERIFIED_PENDING_HUMAN',
  'AI_FLAGGED_PENDING_HUMAN',
  'APPROVED',
  'REJECTED',
  'ERROR',
]);

function getStageIndex(status: string): number {
  if (COMPLETE_STATUSES.has(status)) return STAGES.length; // all done
  const map: Record<string, number> = {
    SUBMITTED: 0,
    VALIDATING: 1,
    PROCESSING_DOCUMENTS: 2,
    SCORING: 3,
  };
  return map[status] ?? 0;
}

interface PipelineProgressProps {
  status: string;
}

export default function PipelineProgress({ status }: PipelineProgressProps) {
  const activeIdx = getStageIndex(status);
  const isProcessing = !COMPLETE_STATUSES.has(status);

  if (!isProcessing) return null; // Only show while pipeline is running

  return (
    <div className="card p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          AI Pipeline Progress
        </h3>
        <span className="flex items-center gap-2 text-sm text-blue-600 font-medium">
          <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Processing…
        </span>
      </div>

      <div className="flex items-center">
        {STAGES.map((stage, idx) => {
          const isDone = idx < activeIdx;
          const isActive = idx === activeIdx;
          const isPending = idx > activeIdx;

          return (
            <div key={stage.key} className="flex items-center flex-1 min-w-0">
              {/* Step circle */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-medium border-2 transition-all
                    ${isDone ? 'bg-green-500 border-green-500 text-white' : ''}
                    ${isActive ? 'bg-blue-500 border-blue-500 text-white shadow-lg shadow-blue-200' : ''}
                    ${isPending ? 'bg-gray-100 border-gray-300 text-gray-400' : ''}
                  `}
                >
                  {isDone ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : isActive ? (
                    <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>
                <span
                  className={`mt-1.5 text-xs text-center max-w-[80px] leading-tight
                    ${isDone ? 'text-green-600 font-medium' : ''}
                    ${isActive ? 'text-blue-600 font-semibold' : ''}
                    ${isPending ? 'text-gray-400' : ''}
                  `}
                >
                  {stage.label}
                </span>
              </div>

              {/* Connector line (not after last) */}
              {idx < STAGES.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 mb-5 transition-all
                  ${idx < activeIdx ? 'bg-green-400' : 'bg-gray-200'}
                `} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
