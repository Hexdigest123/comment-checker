import { useEffect } from 'react';
import { ChevronUp, ChevronDown, ChevronRight, ArrowRight } from 'lucide-react';
import { DataTable, StatusBadge, PlatformBadge, CategoryBadge, SeverityBadge } from '../tables/DataTable';
import { AuthProvider, useAuth } from '../../services/auth';
import { commentApi } from '../../services/api';
import { usePaginatedResource } from '../../hooks/usePaginatedResource';
import { formatDate, truncate } from '../../lib/format';
import type { Comment, PageResponse } from '../../types';

const fetchComments = (params: Record<string, string | number>) =>
  commentApi.list(params).then((r) => r.data as PageResponse<Comment>);

const latestClassification = (item: Comment) =>
  item.classifications && item.classifications.length > 0
    ? [...item.classifications].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )[0]
    : null;

const CommentsPageContent = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const commentsResource = usePaginatedResource<Comment>(fetchComments, {
    enabled: isAuthenticated,
    pollIntervalMs: 5000,
  });

  // Mention links point here with ?account_id=<id>
  const accountIdFilter = new URLSearchParams(window.location.search).get('account_id');
  useEffect(() => {
    if (accountIdFilter) {
      commentsResource.setFilter('account_id', accountIdFilter);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountIdFilter]);

  // Voting is best-effort: apply the vote, then refetch to show the new score.
  // A score below 0 classifies the comment as a false flag (row is greyed out).
  const handleVote = async (id: string, action: 'upvote' | 'downvote') => {
    try {
      await commentApi[action](id);
    } catch {
      // score may still have changed server-side; refetch either way
    }
    commentsResource.refetch();
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
      key: 'category',
      header: 'Category',
      sortable: false,
      render: (item: Comment) => {
        const latest = latestClassification(item);
        return latest ? (
          <CategoryBadge category={latest.category} />
        ) : (
          <span className="text-mistral-muted/60">-</span>
        );
      },
    },
    {
      key: 'severity',
      header: 'Severity',
      sortable: false,
      render: (item: Comment) => {
        const latest = latestClassification(item);
        return latest && latest.severity ? (
          <SeverityBadge severity={latest.severity} />
        ) : (
          <span className="text-mistral-muted/60">-</span>
        );
      },
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
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <button
              type="button"
              title="Upvote"
              className="px-1.5 py-0.5 font-mono text-xs border border-mistral-border-strong rounded-md text-mistral-ink hover:border-mistral-ink transition-colors duration-200"
              onClick={(e) => {
                e.stopPropagation();
                handleVote(item.id, 'upvote');
              }}
            >
              <ChevronUp size={14} aria-hidden />
            </button>
            <span
              className={`font-mono text-xs min-w-6 text-center ${
                item.vote_score < 0 ? 'text-mistral-red-deep' : 'text-mistral-muted'
              }`}
              title={item.vote_score < 0 ? 'False flag: downvotes outnumber upvotes' : 'Vote score'}
            >
              {item.vote_score}
            </span>
            <button
              type="button"
              title="Downvote"
              className="px-1.5 py-0.5 font-mono text-xs border border-mistral-border-strong rounded-md text-mistral-ink hover:border-mistral-ink transition-colors duration-200"
              onClick={(e) => {
                e.stopPropagation();
                handleVote(item.id, 'downvote');
              }}
            >
              <ChevronDown size={14} aria-hidden />
            </button>
          </div>
          <a
            href={`/comments/${item.id}`}
            className="group inline-flex items-center gap-1 text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            View
            <ChevronRight size={14} className="transition-all duration-300 group-hover:translate-x-0.5" aria-hidden />
          </a>
        </div>
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
            Uploaded comments are classified automatically by the
            background worker, with every verdict kept for review.
          </p>
        </div>
        <a
          href="/upload"
          className="group inline-flex items-center gap-2 font-display text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-300 mt-2"
        >
          Upload / Import
          <span className="arrow inline-block transition-all duration-300 group-hover:translate-x-1 group-hover:delay-75">
            <ArrowRight size={14} aria-hidden />
          </span>
        </a>
      </div>

      {commentsResource.error && (
        <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">
          {commentsResource.error}
        </div>
      )}

      {commentsResource.filters.account_id && (
        <div className="mb-6 flex items-center gap-3 border border-mistral-border-strong bg-mistral-band text-mistral-ink px-4 py-2 rounded-md font-mono text-sm">
          <span>
            Showing comments from referenced account
            <span className="text-mistral-muted"> {commentsResource.filters.account_id}</span>
          </span>
          <a href="/comments" className="ml-auto text-mistral-blue hover:text-mistral-red-deep transition-colors duration-200">
            Clear
          </a>
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
          {
            key: 'category',
            label: 'Categories',
            options: [
              { value: 'hate', label: 'Hate' },
              { value: 'harassment', label: 'Harassment' },
              { value: 'violence', label: 'Violence' },
              { value: 'self_harm', label: 'Self harm' },
              { value: 'sexual', label: 'Sexual' },
              { value: 'spam', label: 'Spam' },
              { value: 'illegal', label: 'Illegal' },
              { value: 'financial', label: 'Financial' },
              { value: 'health', label: 'Health' },
              { value: 'legal', label: 'Legal' },
              { value: 'pii', label: 'PII' },
              { value: 'jailbreaking', label: 'Jailbreaking' },
              { value: 'safe', label: 'Safe' },
            ],
          },
          {
            key: 'severity',
            label: 'Severities',
            options: [
              { value: 'low', label: 'Low' },
              { value: 'medium', label: 'Medium' },
              { value: 'high', label: 'High' },
              { value: 'critical', label: 'Critical' },
            ],
          },
        ]}
        emptyMessage="No comments found. Upload a CSV to get started."
        rowClassName={(item) => (item.vote_score < 0 ? 'opacity-50' : '')}
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
