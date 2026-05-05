'use client';

import { useState } from 'react';

interface ExtractedFields {
  bride_name?: string | null;
  groom_name?: string | null;
  marriage_date?: string | null;
  registration_number?: string | null;
  place_of_marriage?: string | null;
  officiating_authority?: string | null;
  document_language?: string | null;
  has_official_seal?: boolean | null;
  has_signature?: boolean | null;
  has_qr_or_barcode?: boolean | null;
  document_quality?: string | null;
  raw_text?: string | null;
  [key: string]: any;
}

interface ScoreContribution {
  field: string;
  label: string;
  value: any;
  scoreCategory: 'name_match' | 'authenticity' | 'forgery' | 'info';
  impact: 'high' | 'medium' | 'low';
  description: string;
}

const CATEGORY_STYLE: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  name_match:  { bg: 'bg-blue-50',   border: 'border-blue-300',  text: 'text-blue-800',  badge: 'bg-blue-100 text-blue-700' },
  authenticity:{ bg: 'bg-green-50',  border: 'border-green-300', text: 'text-green-800', badge: 'bg-green-100 text-green-700' },
  forgery:     { bg: 'bg-purple-50', border: 'border-purple-300',text: 'text-purple-800',badge: 'bg-purple-100 text-purple-700' },
  info:        { bg: 'bg-gray-50',   border: 'border-gray-300',  text: 'text-gray-700',  badge: 'bg-gray-100 text-gray-600' },
};

const CATEGORY_LABEL: Record<string, string> = {
  name_match:  'Name Match',
  authenticity:'Authenticity',
  forgery:     'Integrity',
  info:        'Info',
};

function buildContributions(fields: ExtractedFields): ScoreContribution[] {
  const items: ScoreContribution[] = [];

  if (fields.bride_name) items.push({
    field: 'bride_name', label: "Bride's Name", value: fields.bride_name,
    scoreCategory: 'name_match', impact: 'high',
    description: 'Matched against current name on record',
  });

  if (fields.groom_name) items.push({
    field: 'groom_name', label: "Groom's Name", value: fields.groom_name,
    scoreCategory: 'name_match', impact: 'high',
    description: 'Used to verify plausibility of new name (surname inheritance)',
  });

  if (fields.marriage_date) items.push({
    field: 'marriage_date', label: 'Marriage Date', value: fields.marriage_date,
    scoreCategory: 'authenticity', impact: 'medium',
    description: 'Confirms document is a valid marriage record',
  });

  if (fields.registration_number) items.push({
    field: 'registration_number', label: 'Registration No.', value: fields.registration_number,
    scoreCategory: 'authenticity', impact: 'high',
    description: 'Official certificate registration — boosts authenticity score',
  });

  if (fields.place_of_marriage) items.push({
    field: 'place_of_marriage', label: 'Place of Marriage', value: fields.place_of_marriage,
    scoreCategory: 'authenticity', impact: 'low',
    description: 'Additional context on document validity',
  });

  if (fields.officiating_authority) items.push({
    field: 'officiating_authority', label: 'Officiating Authority', value: fields.officiating_authority,
    scoreCategory: 'authenticity', impact: 'low',
    description: 'Presence of an authority increases authenticity',
  });

  if (fields.has_official_seal != null) items.push({
    field: 'has_official_seal', label: 'Official Seal / Stamp', value: fields.has_official_seal ? '✓ Present' : '✗ Not detected',
    scoreCategory: 'forgery', impact: 'high',
    description: fields.has_official_seal ? 'Government seal detected — strong authenticity signal' : 'No official seal detected — may reduce confidence',
  });

  if (fields.has_signature != null) items.push({
    field: 'has_signature', label: 'Signature', value: fields.has_signature ? '✓ Present' : '✗ Not detected',
    scoreCategory: 'forgery', impact: 'medium',
    description: fields.has_signature ? 'Signature present' : 'No signature detected',
  });

  if (fields.has_qr_or_barcode != null) items.push({
    field: 'has_qr_or_barcode', label: 'QR Code / Barcode', value: fields.has_qr_or_barcode ? '✓ Present' : '✗ Not detected',
    scoreCategory: 'forgery', impact: 'medium',
    description: fields.has_qr_or_barcode ? 'Machine-readable code found — strong authenticity signal' : 'No QR/barcode detected',
  });

  if (fields.document_language) items.push({
    field: 'document_language', label: 'Language', value: fields.document_language,
    scoreCategory: 'info', impact: 'low',
    description: 'Detected document language',
  });

  if (fields.document_quality) items.push({
    field: 'document_quality', label: 'Document Quality', value: fields.document_quality,
    scoreCategory: fields.document_quality === 'good' ? 'authenticity' : 'info', impact: 'low',
    description: `Image quality: ${fields.document_quality}`,
  });

  return items;
}

// Inline document panel — tries <img>, falls back to <object> (PDF), then <iframe>
function InlineDoc({ url }: { url: string }) {
  const [mode, setMode] = useState<'img' | 'object' | 'iframe'>('img');

  if (mode === 'img') {
    return (
      <img
        src={url}
        alt="Supporting document"
        className="w-full h-auto object-contain rounded-lg"
        style={{ maxHeight: 520 }}
        onError={() => setMode('object')}
      />
    );
  }

  if (mode === 'object') {
    return (
      <object
        data={url}
        type="application/pdf"
        className="w-full rounded-lg border border-gray-200"
        style={{ height: 520 }}
        onError={() => setMode('iframe')}
      >
        {/* Fallback if object tag unsupported */}
        <iframe
          src={url}
          className="w-full rounded-lg"
          style={{ height: 520 }}
          title="Supporting document"
          onError={() => setMode('iframe')}
        />
      </object>
    );
  }

  // Last-resort iframe
  return (
    <iframe
      src={url}
      className="w-full rounded-lg border border-gray-200"
      style={{ height: 520 }}
      title="Supporting document"
    />
  );
}

interface DocumentViewerProps {
  requestId: string;
  hasDocument: boolean;
  extractedFields: ExtractedFields | null;
  confidenceScores: {
    name_match: number;
    authenticity: number;
    forgery_check: string;
    overall: number;
    details?: any;
  } | null;
}

export default function DocumentViewer({
  requestId,
  hasDocument,
  extractedFields,
  confidenceScores,
}: DocumentViewerProps) {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const contributions = extractedFields ? buildContributions(extractedFields) : [];
  const grouped = contributions.reduce<Record<string, ScoreContribution[]>>((acc, c) => {
    (acc[c.scoreCategory] ??= []).push(c);
    return acc;
  }, {});

  const docUrl = hasDocument ? `/api/v1/checker/document/${requestId}` : null;

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Document Review</h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Document inline viewer */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-600">Uploaded Document</p>
            {docUrl && (
              <a
                href={docUrl}
                download={`document_${requestId}`}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-white bg-gray-700 hover:bg-gray-800 px-3 py-1.5 rounded-lg transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Download
              </a>
            )}
          </div>

          {docUrl ? (
            <div className="border border-gray-200 rounded-lg overflow-hidden bg-gray-50">
              <InlineDoc url={docUrl} />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-300 rounded-lg bg-gray-50 text-gray-400" style={{ minHeight: 200 }}>
              <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-sm">No document uploaded</span>
            </div>
          )}
        </div>

        {/* Right: Colour-coded field annotations */}
        <div>
          <p className="text-sm font-medium text-gray-600 mb-3">
            Extracted Fields &amp; Score Impact
          </p>

          {/* Category filter tabs */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            <button
              onClick={() => setActiveCategory(null)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                activeCategory === null ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              All
            </button>
            {Object.keys(grouped).map(cat => (
              <button
                key={cat}
                onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors border ${
                  activeCategory === cat
                    ? `${CATEGORY_STYLE[cat].badge} border-transparent`
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {CATEGORY_LABEL[cat]}
                {confidenceScores && cat === 'name_match' && (
                  <span className="ml-1 opacity-70">{Math.round(confidenceScores.name_match * 100)}%</span>
                )}
                {confidenceScores && cat === 'authenticity' && (
                  <span className="ml-1 opacity-70">{Math.round(confidenceScores.authenticity * 100)}%</span>
                )}
                {confidenceScores && cat === 'forgery' && (
                  <span className="ml-1 opacity-70">{confidenceScores.forgery_check}</span>
                )}
              </button>
            ))}
          </div>

          {/* Field cards */}
          <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
            {contributions.length === 0 ? (
              <p className="text-sm text-gray-400 italic">No fields extracted from document.</p>
            ) : (
              contributions
                .filter(c => activeCategory === null || c.scoreCategory === activeCategory)
                .map(c => {
                  const style = CATEGORY_STYLE[c.scoreCategory];
                  return (
                    <div key={c.field} className={`rounded-lg border p-3 ${style.bg} ${style.border}`}>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${style.badge}`}>
                              {CATEGORY_LABEL[c.scoreCategory]}
                            </span>
                            <span className={`text-xs ${style.text} opacity-60`}>{c.impact} impact</span>
                          </div>
                          <p className="text-xs text-gray-500 mt-0.5 font-medium">{c.label}</p>
                          <p className={`text-sm font-semibold ${style.text} mt-0.5`}>{String(c.value)}</p>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-1.5 leading-tight">{c.description}</p>
                    </div>
                  );
                })
            )}
          </div>

          {/* Score summary legend */}
          {confidenceScores && (
            <div className="mt-4 pt-3 border-t border-gray-100">
              <p className="text-xs font-medium text-gray-500 mb-2">Score Breakdown</p>
              <div className="space-y-1.5">
                {[
                  { label: 'Name Match', value: confidenceScores.name_match, cat: 'name_match' },
                  { label: 'Authenticity', value: confidenceScores.authenticity, cat: 'authenticity' },
                ].map(({ label, value, cat }) => (
                  <div key={cat} className="flex items-center gap-2">
                    <span className={`text-xs w-24 ${CATEGORY_STYLE[cat].text} font-medium`}>{label}</span>
                    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          value >= 0.9 ? 'bg-green-500' :
                          value >= 0.7 ? 'bg-yellow-500' :
                          value >= 0.5 ? 'bg-orange-500' : 'bg-red-500'
                        }`}
                        style={{ width: `${Math.round(value * 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-600 w-10 text-right font-mono">
                      {Math.round(value * 100)}%
                    </span>
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <span className={`text-xs w-24 ${CATEGORY_STYLE['forgery'].text} font-medium`}>Integrity</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                    confidenceScores.forgery_check === 'PASS' ? 'bg-green-100 text-green-700' :
                    confidenceScores.forgery_check === 'FAIL' ? 'bg-red-100 text-red-700' :
                    'bg-yellow-100 text-yellow-700'
                  }`}>
                    {confidenceScores.forgery_check}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
