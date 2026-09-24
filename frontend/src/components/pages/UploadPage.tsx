import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { AuthProvider, useAuth } from '../../services/auth';
import { commentApi, importApi } from '../../services/api';
import type { CSVUploadResponse, ImportStatus } from '../../types';

type Tab = 'csv' | 'url';

const UploadPageContent = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [tab, setTab] = useState<Tab>('csv');

  // CSV upload state
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [results, setResults] = useState<CSVUploadResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // URL import state
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [importUrl, setImportUrl] = useState('');
  const [importContext, setImportContext] = useState('');
  const [includeReplies, setIncludeReplies] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importMessage, setImportMessage] = useState('');
  const [importError, setImportError] = useState('');

  useEffect(() => {
    if (!isAuthenticated) return;
    importApi
      .status()
      .then((r) => setImportStatus(r.data))
      .catch(() => setImportStatus({ configured: false, platforms: [] }));
  }, [isAuthenticated]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
      setSuccess('');
      setResults(null);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a file');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      const response = await commentApi.uploadCSV(file);
      const data = response.data as CSVUploadResponse;
      setResults(data);
      setSuccess(
        `${data.valid_rows} comments uploaded (${data.invalid_rows} invalid rows skipped). ` +
          'They are queued and will be classified automatically.'
      );
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload CSV');
    } finally {
      setIsLoading(false);
    }
  };

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importUrl.trim()) {
      setImportError('Please enter a social media URL');
      return;
    }

    setImportLoading(true);
    setImportError('');
    setImportMessage('');

    try {
      const response = await importApi.fromUrl({
        url: importUrl,
        context: importContext || undefined,
        include_replies: includeReplies,
      });
      setImportMessage(response.data?.message || 'Export started.');
      setImportUrl('');
    } catch (err) {
      setImportError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setImportLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-12 w-12 border-4 border-blue-500 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="p-8">
        <div className="bg-yellow-50 text-yellow-600 p-4 rounded-lg">
          Please login to upload files
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Ingest Comments</h1>

        {/* Tabs */}
        <div className="flex border-b border-gray-200 mb-6">
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'csv' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab('csv')}
          >
            CSV Upload
          </button>
          <button
            className={`px-4 py-2 text-sm font-medium border-b-2 ${tab === 'url' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            onClick={() => setTab('url')}
          >
            Import from Social Media URL
          </button>
        </div>

        {tab === 'csv' ? (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-6">{error}</div>}
            {success && <div className="bg-green-50 text-green-600 p-3 rounded-lg mb-6">{success}</div>}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">CSV File</label>
                <Input type="file" accept=".csv" onChange={handleFileChange} ref={fileInputRef} required />
                <p className="mt-1 text-sm text-gray-500">
                  CSV file with comment text, optionally author, URL and platform columns
                </p>
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-700 mb-2">CSV Format</h3>
                <p className="text-sm text-gray-600 mb-2">Your CSV should have the following columns:</p>
                <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                  <li><strong>text</strong> or <strong>comment</strong> - The comment text (required)</li>
                  <li><strong>source_url</strong> or <strong>url</strong> - The source URL (optional)</li>
                  <li><strong>user</strong> or <strong>author</strong> - The user who wrote the comment (optional)</li>
                  <li><strong>platform</strong> - Social media platform (optional)</li>
                  <li><strong>context</strong> - Context the comments react to (optional)</li>
                </ul>
              </div>

              {results && (
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h3 className="font-medium text-blue-800 mb-2">Upload Results</h3>
                  <p className="text-sm text-blue-700">
                    Batch {results.batch_id}: {results.valid_rows} of {results.total_rows} rows
                    created valid comments. Classification is running in the background -
                    check the Comments page.
                  </p>
                </div>
              )}

              <Button type="submit" variant="primary" isLoading={isLoading} fullWidth size="lg">
                Upload CSV
              </Button>
            </form>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            {importError && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-6">{importError}</div>}
            {importMessage && <div className="bg-green-50 text-green-600 p-3 rounded-lg mb-6">{importMessage}</div>}

            {importStatus && !importStatus.configured && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
                <p className="text-sm text-yellow-800 font-medium mb-1">
                  ExportComments API key not configured
                </p>
                <p className="text-sm text-yellow-700">
                  Set <code className="bg-yellow-100 px-1 rounded">EXPORTCOMMENTS_API_KEY</code> in the
                  backend <code className="bg-yellow-100 px-1 rounded">.env</code> to enable direct URL import
                  (requires an ExportComments Premium/Business plan).
                </p>
              </div>
            )}

            <form onSubmit={handleImport} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Social media post / video URL</label>
                <Input
                  type="url"
                  placeholder="https://www.instagram.com/p/..."
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                />
                <p className="mt-1 text-sm text-gray-500">
                  Supported via ExportComments: {importStatus?.platforms?.slice(0, 6).join(', ') || 'instagram, youtube, facebook, tiktok, twitter, reddit'}...
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Context (recommended for classification)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Comments reacting to a news video about..."
                  value={importContext}
                  onChange={(e) => setImportContext(e.target.value)}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={includeReplies}
                  onChange={(e) => setIncludeReplies(e.target.checked)}
                  className="rounded"
                />
                Include reply threads
              </label>

              <Button
                type="submit"
                variant="primary"
                isLoading={importLoading}
                fullWidth
                size="lg"
              >
                Start Import
              </Button>
            </form>

            <p className="mt-4 text-xs text-gray-400">
              The export runs in the background. Imported comments appear in the Comments
              table and are classified automatically by the worker.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

const UploadPage = () => (
  <AuthProvider>
    <UploadPageContent />
  </AuthProvider>
);

export default UploadPage;
