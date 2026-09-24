import { DataTable, StatusBadge, PlatformBadge } from '../tables/DataTable';
import { AuthProvider, useAuth } from '../../services/auth';
import { commentApi } from '../../services/api';
import { usePaginatedResource } from '../../hooks/usePaginatedResource';
import { formatDate, truncate } from '../../lib/format';
import type { Comment, PageResponse } from '../../types';

const fetchComments = (params: Record<string, string | number>) =>
  commentApi.list(params).then((r) => r.data as PageResponse<Comment>);

const CommentsPageContent = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const commentsResource = usePaginatedResource<Comment>(fetchComments, {
    enabled: isAuthenticated,
    pollIntervalMs: 5000,
  });

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
        <a
          href={`/comments/${item.id}`}
          className="group inline-flex items-center gap-1 text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200"
          onClick={(e) => e.stopPropagation()}
        >
          View
          <span className="transition-all duration-300 group-hover:translate-x-0.5">→</span>
        </a>
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

      {commentsResource.error && (
        <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">
          {commentsResource.error}
        </div>
      )}

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
    </div>
  );
};

const CommentsPage = () => (
  <AuthProvider>
    <CommentsPageContent />
  </AuthProvider>
);

export default CommentsPage;
