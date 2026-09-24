import { useCallback, useState } from 'react';
import { DataTable, StatusBadge, PlatformBadge, BackendBadge, CategoryBadge, SeverityBadge } from '../tables/DataTable';
import { Button } from '../ui/Button';
import { AuthProvider, useAuth } from '../../services/auth';
import { commentApi, classificationApi } from '../../services/api';
import { usePaginatedResource } from '../../hooks/usePaginatedResource';
import { formatDate, truncate } from '../../lib/format';
import type { Classification, Comment, CommentSearchResult, PageResponse } from '../../types';

type PageView = 'comments' | 'classifications';

const fetchComments = (params: Record<string, string | number>) =>
  commentApi.list(params).then((r) => r.data as PageResponse<Comment>);

const fetchClassifications = (params: Record<string, string | number>) =>
  classificationApi.list(params).then((r) => r.data as PageResponse<Classification>);

const segmentClass = (active: boolean) =>
  `px-4 py-1.5 font-display text-sm rounded-sm transition-colors duration-200 ${
    active ? 'bg-mistral-ink text-mistral-surface' : 'text-mistral-muted hover:text-mistral-ink'
  }`;

const CommentsPageContent = ({ initialView = 'comments' }: { initialView?: PageView }) => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [view, setView] = useState<PageView>(initialView);
  const commentsResource = usePaginatedResource<Comment>(fetchComments, {
    enabled: isAuthenticated,
    pollIntervalMs: 5000,
  });
  const classificationsResource = usePaginatedResource<Classification>(fetchClassifications, {
    enabled: isAuthenticated,
  });

  // Semantic search mode
  const [semanticMode, setSemanticMode] = useState(false);
  const [semanticQuery, setSemanticQuery] = useState('');
  const [semanticResults, setSemanticResults] = useState<CommentSearchResult[] | null>(null);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState('');

  const runSemanticSearch = useCallback(async () => {
    if (!semanticQuery.trim()) return;
    setSemanticLoading(true);
    setSemanticError('');
    try {
      const response = await commentApi.semanticSearch(semanticQuery, 25);
      setSemanticResults(response.data);
    } catch (err) {
      setSemanticError(err instanceof Error ? err.message : 'Semantic search failed');
      setSemanticResults(null);
    } finally {
      setSemanticLoading(false);
    }
  }, [semanticQuery]);

  const handleClassify = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await commentApi.classify(id);
    } finally {
      commentsResource.refetch();
    }
  };

  const commentColumns = [
    {
      key: 'text',
      header: 'Comment',
      sortable: true,
      className: 'max-w-md',
      render: (item: Comment) => (
        <a href={`/comments/${item.id}`} className="text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200" title={item.text}>
          {truncate(item.text, 90)}
        </a>
      ),
    },
    {
      key: 'original_author',
      header: 'Author',
      sortable: false,
      render: (item: Comment) =>
        item.original_author_url ? (
          <a
            href={item.original_author_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-mistral-blue hover:text-mistral-red-deep transition-colors duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {item.original_author || 'unknown'}
          </a>
        ) : (
          item.original_author || '-'
        ),
    },
    {
      key: 'source_platform',
      header: 'Platform',
      sortable: false,
      render: (item: Comment) => <PlatformBadge platform={item.source_platform} />,
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (item: Comment) => <StatusBadge status={item.status} />,
    },
    {
      key: 'created_at',
      header: 'Created',
      sortable: true,
      render: (item: Comment) => (
        <span className="font-mono text-xs text-mistral-muted">{formatDate(item.created_at)}</span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (item: Comment) => (
        <div className="flex gap-2">
          <a
            href={`/comments/${item.id}`}
            className="group inline-flex items-center gap-1 text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            View
            <span className="transition-all duration-300 group-hover:translate-x-0.5">→</span>
          </a>
          {item.status === 'pending' && (
            <Button size="sm" variant="ink" onClick={(e) => handleClassify(e, item.id)}>
              Classify
            </Button>
          )}
          {(item.status === 'completed' || item.status === 'failed') && (
            <Button size="sm" variant="hairline" onClick={(e) => handleClassify(e, item.id)}>
              Reclassify
            </Button>
          )}
        </div>
      ),
    },
  ];

  const classificationColumns = [
    {
      key: 'comment_id',
      header: 'Comment',
      sortable: true,
      render: (item: Classification) => (
        <a href={`/comments/${item.comment_id}`} className="font-mono text-sm text-mistral-blue hover:text-mistral-red-deep transition-colors duration-200">
          #{item.comment_id}
        </a>
      ),
    },
    {
      key: 'backend',
      header: 'Backend',
      sortable: true,
      render: (item: Classification) => <BackendBadge backend={item.backend} />,
    },
    {
      key: 'category',
      header: 'Category',
      sortable: true,
      render: (item: Classification) => <CategoryBadge category={item.category} />,
    },
    {
      key: 'severity',
      header: 'Severity',
      sortable: true,
      render: (item: Classification) => <SeverityBadge severity={item.severity || ''} />,
    },
    {
      key: 'confidence',
      header: 'Confidence',
      sortable: true,
      render: (item: Classification) => (
        <span className="font-mono text-sm">{(item.confidence * 100).toFixed(1)}%</span>
      ),
    },
    {
      key: 'harmful_score',
      header: 'Harmful Score',
      sortable: true,
      render: (item: Classification) => (
        <span className="font-mono text-sm">{item.harmful_score.toFixed(2)}</span>
      ),
    },
    {
      key: 'created_at',
      header: 'Classified At',
      sortable: true,
      render: (item: Classification) => (
        <span className="font-mono text-xs text-mistral-muted">{formatDate(item.created_at)}</span>
      ),
    },
  ];

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
          Please login to view comments
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Section header */}
      <div className="mb-8 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <span className="eyebrow-badge">Moderation queue</span>
          <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">Comments</h1>
          <p className="mt-2 text-sm text-mistral-muted max-w-xl">
            Uploaded comments are <span className="marker-highlight">classified automatically</span> by the
            background worker, with every verdict kept for review.
          </p>
        </div>
        <a
          href="/upload"
          className="group inline-flex items-center gap-2 font-display text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-300 mt-2"
        >
          Upload / Import
          <span className="arrow inline-block transition-all duration-300 group-hover:translate-x-1 group-hover:delay-75">→</span>
        </a>
      </div>

      {/* View switch: comments + classifications share one tab */}
      <div className="mb-6 flex items-center justify-between gap-4 flex-wrap">
        <div className="inline-flex gap-1 p-1 rounded-md border border-mistral-border-strong bg-white">
          <button className={segmentClass(view === 'comments')} onClick={() => setView('comments')}>
            Comments
            <span className="ml-2 font-mono text-[11px] opacity-70">{commentsResource.total}</span>
          </button>
          <button className={segmentClass(view === 'classifications')} onClick={() => setView('classifications')}>
            Classifications
            <span className="ml-2 font-mono text-[11px] opacity-70">{classificationsResource.total}</span>
          </button>
        </div>
      </div>

      {view === 'comments' ? (
        <>
          {/* Search mode switch */}
          <div className="mb-4 flex items-center gap-4 flex-wrap">
            <div className="inline-flex gap-1 p-1 rounded-md border border-mistral-border bg-white">
              <button
                className={`${segmentClass(!semanticMode)} font-mono text-xs uppercase tracking-wide px-3`}
                onClick={() => {
                  setSemanticMode(false);
                  setSemanticResults(null);
                }}
              >
                Keyword
              </button>
              <button
                className={`${segmentClass(semanticMode)} font-mono text-xs uppercase tracking-wide px-3`}
                onClick={() => setSemanticMode(true)}
              >
                Semantic
              </button>
            </div>
            {semanticMode && (
              <span className="font-mono text-xs text-mistral-muted">
                Finds comments by meaning using embeddings (no keyword match needed)
              </span>
            )}
          </div>

          {commentsResource.error && (
            <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">
              {commentsResource.error}
            </div>
          )}

          {!semanticMode ? (
            <DataTable
              resource={commentsResource}
              columns={commentColumns}
              searchPlaceholder="Search comments..."
              showFilters
              filterOptions={[
                {
                  key: 'status',
                  label: 'Statuses',
                  options: [
                    { value: 'pending', label: 'Pending' },
                    { value: 'waiting', label: 'Waiting' },
                    { value: 'processing', label: 'Processing' },
                    { value: 'completed', label: 'Completed' },
                    { value: 'failed', label: 'Failed' },
                  ],
                },
              ]}
              emptyMessage="No comments found. Upload a CSV to get started."
              onRowClick={(item) => {
                window.location.href = `/comments/${item.id}`;
              }}
            />
          ) : (
            <div className="bg-white rounded-lg border border-mistral-border overflow-hidden">
              <div className="p-4 border-b border-mistral-border flex gap-4">
                <input
                  type="text"
                  placeholder="e.g. people insulting the shop owner"
                  value={semanticQuery}
                  onChange={(e) => setSemanticQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && runSemanticSearch()}
                  className="flex-1 px-4 py-2 text-sm bg-white border border-mistral-border-strong rounded-md placeholder:text-mistral-muted/70 text-mistral-ink focus:outline-none focus:border-mistral-ink transition-colors duration-200"
                />
                <Button variant="ink" onClick={runSemanticSearch} isLoading={semanticLoading}>
                  Search
                </Button>
              </div>

              {semanticError && <div className="p-4 text-sm text-mistral-red-deep">{semanticError}</div>}

              {semanticResults && (
                <div className="divide-y divide-mistral-border">
                  {semanticResults.length === 0 && (
                    <div className="p-8 text-center text-sm text-mistral-muted">
                      No semantically similar comments found
                    </div>
                  )}
                  {semanticResults.map((result) => (
                    <div key={result.id} className="p-4 flex items-start gap-4 hover:bg-mistral-surface transition-colors duration-200">
                      <div className="flex-1 min-w-0">
                        <a href={`/comments/${result.id}`} className="text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200 block">
                          {result.text}
                        </a>
                        <div className="mt-1 flex items-center gap-3 text-xs text-mistral-muted">
                          <span className="font-mono">{result.original_author || 'unknown'}</span>
                          <PlatformBadge platform={result.source_platform} />
                          <StatusBadge status={result.status} />
                          <span className="font-mono">{formatDate(result.created_at)}</span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-mono text-sm text-mistral-ink">
                          {(result.similarity * 100).toFixed(1)}%
                        </div>
                        <div className="font-mono text-[11px] uppercase tracking-wide text-mistral-muted">similar</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {!semanticResults && !semanticError && !semanticLoading && (
                <div className="p-8 text-center text-sm text-mistral-muted">
                  Enter a query to find comments by meaning
                </div>
              )}
            </div>
          )}
        </>
      ) : (
        <>
          {classificationsResource.error && (
            <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">
              {classificationsResource.error}
            </div>
          )}
          <DataTable
            resource={classificationsResource}
            columns={classificationColumns}
            searchPlaceholder="Search classifications..."
            showFilters
            filterOptions={[
              {
                key: 'backend',
                label: 'Backends',
                options: [
                  { value: 'mistral', label: 'Mistral' },
                  { value: 'typesafe', label: 'TypeSafe' },
                  { value: 'combined', label: 'Combined' },
                ],
              },
              {
                key: 'category',
                label: 'Categories',
                options: [
                  { value: 'hate', label: 'Hate' },
                  { value: 'harassment', label: 'Harassment' },
                  { value: 'violence', label: 'Violence' },
                  { value: 'self_harm', label: 'Self Harm' },
                  { value: 'sexual', label: 'Sexual' },
                  { value: 'spam', label: 'Spam' },
                  { value: 'illegal', label: 'Illegal' },
                  { value: 'safe', label: 'Safe' },
                ],
              },
            ]}
            emptyMessage="No classifications yet. They appear once the worker processes comments."
          />
        </>
      )}
    </div>
  );
};

const CommentsPage = ({ initialView }: { initialView?: PageView }) => (
  <AuthProvider>
    <CommentsPageContent initialView={initialView} />
  </AuthProvider>
);

export default CommentsPage;
