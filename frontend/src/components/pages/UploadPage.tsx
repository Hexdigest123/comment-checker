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
        <div className="animate-spin h-12 w-12 border-4 border-mistral-ink border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="p-8">
        <div className="border border-mistral-border-strong bg-mistral-band text-mistral-ink p-4 rounded-md font-mono text-sm">
          Please login to upload files
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        {/* Section header */}
        <div className="mb-8">
          <span className="eyebrow-badge">Ingestion</span>
          <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">
            Ingest <span className="marker-highlight">Comments</span>
          </h1>
          <p className="mt-2 text-sm text-mistral-muted">
            Upload a CSV or pull comments straight from a social media post.
          </p>
        </div>

        {/* Tabs — hairline underline style */}
        <div className="flex border-b border-mistral-border mb-6">
          <button
            className={`px-4 py-2 font-display text-sm font-medium border-b-2 transition-colors duration-200 ${tab === 'csv' ? 'border-mistral-red text-mistral-ink' : 'border-transparent text-mistral-muted hover:text-mistral-ink'}`}
            onClick={() => setTab('csv')}
          >
            CSV Upload
          </button>
          <button
            className={`px-4 py-2 font-display text-sm font-medium border-b-2 transition-colors duration-200 ${tab === 'url' ? 'border-mistral-red text-mistral-ink' : 'border-transparent text-mistral-muted hover:text-mistral-ink'}`}
            onClick={() => setTab('url')}
          >
            Import from Social Media URL
          </button>
        </div>

        {tab === 'csv' ? (
          <div className="bg-white rounded-md border border-mistral-border p-6">
            {error && <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-3 rounded-md mb-6">{error}</div>}
            {success && <div className="border border-mistral-green/50 bg-mistral-green-tint text-mistral-ink p-3 rounded-md mb-6">{success}</div>}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block font-mono text-xs uppercase tracking-widest text-mistral-muted mb-2">CSV File</label>
                <Input type="file" accept=".csv" onChange={handleFileChange} ref={fileInputRef} required />
                <p className="mt-1 text-sm text-mistral-muted">
                  CSV file with comment text, optionally author, URL and platform columns
                </p>
              </div>

              <div className="bg-mistral-surface border border-mistral-border p-4 rounded-md">
                <h3 className="font-display font-medium text-mistral-ink mb-2">CSV Format</h3>
                <p className="text-sm text-mistral-muted mb-2">Your CSV should have the following columns:</p>
                <ul className="list-disc list-inside text-sm text-mistral-muted space-y-1">
                  <li><strong className="text-mistral-ink">text</strong> or <strong className="text-mistral-ink">comment</strong> - The comment text (required)</li>
                  <li><strong className="text-mistral-ink">source_url</strong> or <strong className="text-mistral-ink">url</strong> - The source URL (optional)</li>
                  <li><strong className="text-mistral-ink">user</strong> or <strong className="text-mistral-ink">author</strong> - The user who wrote the comment (optional)</li>
                  <li><strong className="text-mistral-ink">platform</strong> - Social media platform (optional)</li>
                  <li><strong className="text-mistral-ink">context</strong> - Context the comments react to (optional)</li>
                </ul>
              </div>

              {results && (
                <div className="border border-mistral-blue/40 bg-mistral-blue-tint p-4 rounded-md">
                  <h3 className="font-display font-medium text-mistral-ink mb-2">Upload Results</h3>
                  <p className="text-sm text-mistral-muted">
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
          <div className="bg-white rounded-md border border-mistral-border p-6">
            {importError && <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-3 rounded-md mb-6">{importError}</div>}
            {importMessage && <div className="border border-mistral-green/50 bg-mistral-green-tint text-mistral-ink p-3 rounded-md mb-6">{importMessage}</div>}

            {importStatus && !importStatus.configured && (
              <div className="border border-mistral-yellow/70 bg-mistral-yellow-tint rounded-md p-4 mb-6">
                <p className="text-sm text-mistral-ink font-medium mb-1">
                  ExportComments API key not configured
                </p>
                <p className="text-sm text-mistral-muted">
                  Set <code className="bg-mistral-inset px-1 rounded-sm font-mono text-xs">EXPORTCOMMENTS_API_KEY</code> in the
                  backend <code className="bg-mistral-inset px-1 rounded-sm font-mono text-xs">.env</code> to enable direct URL import
                  (requires an ExportComments Premium/Business plan).
                </p>
              </div>
            )}

            <form onSubmit={handleImport} className="space-y-6">
              <div>
                <label className="block font-mono text-xs uppercase tracking-widest text-mistral-muted mb-2">Social media post / video URL</label>
                <Input
                  type="url"
                  placeholder="https://www.instagram.com/p/..."
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                />
                <p className="mt-1 text-sm text-mistral-muted">
                  Supported via ExportComments: {importStatus?.platforms?.slice(0, 6).join(', ') || 'instagram, youtube, facebook, tiktok, twitter, reddit'}...
                </p>
              </div>

              <div>
                <label className="block font-mono text-xs uppercase tracking-widest text-mistral-muted mb-2">
                  Context (recommended for classification)
                </label>
                <Input
                  type="text"
                  placeholder="e.g. Comments reacting to a news video about..."
                  value={importContext}
                  onChange={(e) => setImportContext(e.target.value)}
                />
              </div>

              <label className="flex items-center gap-2 text-sm text-mistral-muted">
                <input
                  type="checkbox"
                  checked={includeReplies}
                  onChange={(e) => setIncludeReplies(e.target.checked)}
                  className="rounded accent-mistral-red"
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

            <p className="mt-4 text-xs text-mistral-muted">
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
