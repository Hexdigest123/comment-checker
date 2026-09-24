import { useState, useEffect } from 'react';
import { Button } from '../ui/Button';
import { StatusBadge, BackendBadge, CategoryBadge, SeverityBadge } from '../tables/DataTable';
import { AuthProvider, useAuth } from '../../services/auth';
import { commentApi, classificationApi } from '../../services/api';
import type { Comment, Classification } from '../../types';

interface CommentDetailPageProps {
  params: { id: string };
}

const CommentDetailPageContent = ({ params }: CommentDetailPageProps) => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [comment, setComment] = useState<Comment | null>(null);
  const [classifications, setClassifications] = useState<Classification[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      if (!isAuthenticated) return;

      setIsLoading(true);
      setError('');

      try {
        const [commentRes, classificationsRes] = await Promise.all([
          commentApi.get(params.id),
          classificationApi.list({ comment_id: params.id } as unknown as { page?: number; page_size?: number; comment_id?: string; backend?: string; category?: string }),
        ]);
        setComment(commentRes.data as Comment);
        setClassifications(classificationsRes.data.items as Classification[]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch comment details');
      } finally {
        setIsLoading(false);
      }
    };

    if (!authLoading) {
      fetchData();
    }
  }, [params.id, isAuthenticated, authLoading]);

  const handleClassify = async () => {
    if (!comment) return;

    try {
      await commentApi.classify(comment.id);
      // Refresh data
      const [commentRes, classificationsRes] = await Promise.all([
        commentApi.get(params.id),
        classificationApi.list({ comment_id: params.id } as unknown as { page?: number; page_size?: number; comment_id?: string; backend?: string; category?: string }),
      ]);
      setComment(commentRes.data as Comment);
      setClassifications(classificationsRes.data.items as Classification[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to classify comment');
    }
  };

  const handleReclassify = async () => {
    if (!comment) return;

    try {
      await commentApi.reclassify(comment.id);
      // Refresh data
      const [commentRes, classificationsRes] = await Promise.all([
        commentApi.get(params.id),
        classificationApi.list({ comment_id: params.id } as unknown as { page?: number; page_size?: number; comment_id?: string; backend?: string; category?: string }),
      ]);
      setComment(commentRes.data as Comment);
      setClassifications(classificationsRes.data.items as Classification[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reclassify comment');
    }
  };

  const handleDelete = async () => {
    if (!comment || isDeleting) return;

    setIsDeleting(true);
    try {
      await commentApi.delete(comment.id);
      window.location.href = '/comments';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete comment');
      setIsDeleting(false);
    }
  };

  if (authLoading || isLoading) {
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
          Please login to view comment details
        </div>
      </div>
    );
  }

  if (!comment) {
    return (
      <div className="p-8">
        <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md">
          Comment not found
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto">
        {/* Section header */}
        <div className="flex justify-between items-start mb-8 gap-4 flex-wrap">
          <div>
            <span className="eyebrow-badge">Record</span>
            <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">Comment Details</h1>
          </div>
          <a
            href="/comments"
            className="group inline-flex items-center gap-2 font-display text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-300 mt-2"
          >
            <span className="inline-block transition-all duration-300 group-hover:-translate-x-1">←</span>
            Back to Comments
          </a>
        </div>

        {error && (
          <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">
            {error}
          </div>
        )}

        <div className="bg-white rounded-md border border-mistral-border p-6 mb-8">
          <h2 className="font-display text-xl font-semibold text-mistral-ink mb-4">Comment Information</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block font-mono text-[11px] uppercase tracking-widest text-mistral-muted mb-1">Text</label>
              <p className="text-mistral-ink">{comment.text}</p>
            </div>
            <div>
              <label className="block font-mono text-[11px] uppercase tracking-widest text-mistral-muted mb-1">Status</label>
              <StatusBadge status={comment.status} />
            </div>
            <div>
              <label className="block font-mono text-[11px] uppercase tracking-widest text-mistral-muted mb-1">Source URL</label>
              {comment.source_url ? (
                <a href={comment.source_url} target="_blank" rel="noopener noreferrer" className="text-mistral-blue hover:text-mistral-red-deep transition-colors duration-200">
                  {comment.source_url}
                </a>
              ) : (
                <p className="text-mistral-muted">None</p>
              )}
            </div>
            <div>
              <label className="block font-mono text-[11px] uppercase tracking-widest text-mistral-muted mb-1">Created At</label>
              <p className="text-mistral-ink">{new Date(comment.created_at).toLocaleString()}</p>
            </div>
          </div>

          <div className="mt-6 flex gap-4">
            {comment.status === 'pending' && (
              <Button variant="primary" onClick={handleClassify}>
                Classify
              </Button>
            )}
            {(comment.status === 'completed' || comment.status === 'failed') && (
              <Button variant="outline" onClick={handleReclassify}>
                Reclassify
              </Button>
            )}
            <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
              Delete
            </Button>
          </div>
        </div>

        <div className="bg-white rounded-md border border-mistral-border p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="font-display text-xl font-semibold text-mistral-ink">Classifications</h2>
            <span className="font-mono text-xs uppercase tracking-widest text-mistral-muted">{classifications.length} total</span>
          </div>

          {classifications.length === 0 ? (
            <p className="text-mistral-muted text-center py-8">
              No classifications for this comment yet
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-mistral-band">
                  <tr>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Backend</th>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Category</th>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Severity</th>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Confidence</th>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Harmful Score</th>
                    <th className="px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border">Classified At</th>
                  </tr>
                </thead>
                <tbody className="bg-white">
                  {classifications.map((classification) => (
                    <tr key={classification.id} className="border-b border-mistral-border last:border-b-0 hover:bg-mistral-surface transition-colors duration-200">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <BackendBadge backend={classification.backend} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <CategoryBadge category={classification.category} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <SeverityBadge severity={classification.severity || ''} />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-mistral-ink">
                        {((classification.confidence || 0) * 100).toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-mistral-ink">
                        {(classification.harmful_score || 0).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap font-mono text-xs text-mistral-muted">
                        {new Date(classification.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const CommentDetailPage = ({ params }: CommentDetailPageProps) => (
  <AuthProvider>
    <CommentDetailPageContent params={params} />
  </AuthProvider>
);

export default CommentDetailPage;
