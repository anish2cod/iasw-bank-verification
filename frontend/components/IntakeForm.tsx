'use client';

import { useState, useRef, DragEvent } from 'react';

interface IntakeFormProps {
  onSubmit: (formData: FormData) => Promise<void>;
  submitting: boolean;
}

export default function IntakeForm({ onSubmit, submitting }: IntakeFormProps) {
  const [customerId, setCustomerId] = useState('');
  const [oldName, setOldName] = useState('');
  const [newName, setNewName] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const formData = new FormData();
    formData.append('customer_id', customerId);
    formData.append('old_name', oldName);
    formData.append('new_name', newName);
    formData.append('request_type', 'LEGAL_NAME_CHANGE');

    if (file) {
      formData.append('document', file);
    }

    await onSubmit(formData);
  };

  const fillTestData = () => {
    setCustomerId('C001');
    setOldName('Priya Sharma');
    setNewName('Priya Mehta');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Test Data Button */}
      <div className="flex justify-end">
        <button
          type="button"
          onClick={fillTestData}
          className="text-sm text-primary-600 hover:text-primary-700"
        >
          Fill Test Data
        </button>
      </div>

      {/* Customer ID */}
      <div>
        <label htmlFor="customer_id" className="label">
          Customer ID <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="customer_id"
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          className="input"
          placeholder="e.g., C001"
          required
        />
        <p className="mt-1 text-sm text-gray-500">Enter the customer's ID from the core banking system</p>
      </div>

      {/* Old Name */}
      <div>
        <label htmlFor="old_name" className="label">
          Current Legal Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="old_name"
          value={oldName}
          onChange={(e) => setOldName(e.target.value)}
          className="input"
          placeholder="e.g., Priya Sharma"
          required
        />
        <p className="mt-1 text-sm text-gray-500">Name as it appears in current records</p>
      </div>

      {/* New Name */}
      <div>
        <label htmlFor="new_name" className="label">
          New Legal Name <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          id="new_name"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          className="input"
          placeholder="e.g., Priya Mehta"
          required
        />
        <p className="mt-1 text-sm text-gray-500">Name to change to</p>
      </div>

      {/* Document Upload */}
      <div>
        <label className="label">Supporting Document</label>
        <div
          className={`relative border-2 border-dashed rounded-lg p-6 transition-colors ${
            dragActive
              ? 'border-primary-500 bg-primary-50'
              : file
              ? 'border-green-500 bg-green-50'
              : 'border-gray-300 hover:border-gray-400'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileChange}
            accept=".pdf,.png,.jpg,.jpeg,.tiff"
            className="hidden"
          />

          {file ? (
            <div className="text-center">
              <svg className="w-12 h-12 text-green-500 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm font-medium text-gray-900">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">{(file.size / 1024).toFixed(1)} KB</p>
              <button
                type="button"
                onClick={() => setFile(null)}
                className="mt-2 text-sm text-red-600 hover:text-red-700"
              >
                Remove
              </button>
            </div>
          ) : (
            <div className="text-center">
              <svg className="w-12 h-12 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="text-sm text-gray-600">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-primary-600 hover:text-primary-700 font-medium"
                >
                  Click to upload
                </button>
                {' '}or drag and drop
              </p>
              <p className="text-xs text-gray-500 mt-1">PDF, PNG, JPG up to 10MB</p>
            </div>
          )}
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Upload marriage certificate, court order, or other legal document
        </p>
      </div>

      {/* Submit Button */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={submitting || !customerId || !oldName || !newName}
          className="w-full btn-primary py-3 text-lg"
        >
          {submitting ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Submitting...
            </span>
          ) : (
            'Submit Request'
          )}
        </button>
      </div>
    </form>
  );
}
