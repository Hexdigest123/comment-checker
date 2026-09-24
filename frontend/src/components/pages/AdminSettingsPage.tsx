import { useState } from 'react';
import { AuthProvider, useAuth } from '../../services/auth';
import { adminApi } from '../../services/api';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import type { ApiError } from '../../types';

type AdminAction = 'delete-all' | 'reclassify-all' | 'wipe-graph' | null;

const AdminSettingsContent = () => {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const [confirmAction, setConfirmAction] = useState<AdminAction>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isReclassifying, setIsReclassifying] = useState(false);
  const [isWipingGraph, setIsWipingGraph] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const closeConfirm = () => {
    setConfirmAction(null);
  };

  const handleDeleteAll = async () => {
    setIsDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await adminApi.deleteAllComments();
      setSuccess(`Deleted ${response.data.deleted_comments} comments.`);
      setConfirmAction(null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.detail || 'Failed to delete comments');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReclassifyAll = async () => {
    setIsReclassifying(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await adminApi.reclassifyAllComments();
      setSuccess(
        `Queued ${response.data.queued_comments} comments for reclassification. They are being processed in the background.`
      );
      setConfirmAction(null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.detail || 'Failed to queue reclassification');
    } finally {
      setIsReclassifying(false);
    }
  };

  const handleWipeGraph = async () => {
    setIsWipingGraph(true);
    setError(null);
    setSuccess(null);
    try {
      const response = await adminApi.wipeGraph();
      const { deleted_clusters, deleted_accounts, deleted_connections } = response.data;
      setSuccess(
        `Wiped the graph: ${deleted_clusters} clusters, ${deleted_accounts} accounts, ${deleted_connections} connections deleted. Comments were kept but detached from their authors.`
      );
      setConfirmAction(null);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.detail || 'Failed to wipe graph');
    } finally {
      setIsWipingGraph(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin h-12 w-12 border-4 border-mistral-ink border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!isAuthenticated || !user?.is_admin) {
    return (
      <div className="p-8">
        <div className="border border-mistral-border-strong bg-mistral-band text-mistral-ink p-4 rounded-md font-mono text-sm">
          Admin access required
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        {/* Section header */}
        <div className="mb-8">
          <span className="eyebrow-badge">Administration</span>
          <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">
            Admin Settings
          </h1>
          <p className="mt-2 text-sm text-mistral-muted">
            Bulk operations across every comment in the system. These actions cannot be undone.
          </p>
        </div>

        <div className="bg-white rounded-md border border-mistral-border p-6 space-y-6">
          {error && <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-3 rounded-md">{error}</div>}
          {success && <div className="border border-mistral-green/50 bg-mistral-green-tint text-mistral-ink p-3 rounded-md">{success}</div>}

          {/* Delete all comments */}
          <div className="flex items-start justify-between gap-4 border border-mistral-border rounded-md p-4">
            <div>
              <h3 className="font-display font-medium text-mistral-ink">Delete all comments</h3>
              <p className="mt-1 text-sm text-mistral-muted">
                Permanently removes every comment and its classifications.
              </p>
            </div>
            <Button variant="danger" onClick={() => setConfirmAction('delete-all')} className="shrink-0">
              Delete all comments
            </Button>
          </div>

          {/* Reclassify all comments */}
          <div className="flex items-start justify-between gap-4 border border-mistral-border rounded-md p-4">
            <div>
              <h3 className="font-display font-medium text-mistral-ink">Reclassify all comments</h3>
              <p className="mt-1 text-sm text-mistral-muted">
                Clears existing classifications and re-runs the classifier on every comment.
              </p>
            </div>
            <Button variant="primary" onClick={() => setConfirmAction('reclassify-all')} className="shrink-0">
              Reclassify all comments
            </Button>
          </div>

          {/* Wipe graph */}
          <div className="flex items-start justify-between gap-4 border border-mistral-border rounded-md p-4">
            <div>
              <h3 className="font-display font-medium text-mistral-ink">Wipe graph</h3>
              <p className="mt-1 text-sm text-mistral-muted">
                Permanently removes every account cluster, external account, and cluster connection.
                Comments are kept but detached from their authors.
              </p>
            </div>
            <Button variant="danger" onClick={() => setConfirmAction('wipe-graph')} className="shrink-0">
              Wipe graph
            </Button>
          </div>
        </div>
      </div>

      {/* Confirmation modals */}
      <Modal isOpen={confirmAction === 'delete-all'} onClose={closeConfirm} title="Delete all comments" size="md">
        <p className="text-sm text-mistral-ink">
          This will permanently delete <strong>every comment</strong> and its classifications. This action cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={closeConfirm}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleDeleteAll} isLoading={isDeleting}>
            Delete everything
          </Button>
        </div>
      </Modal>

      <Modal isOpen={confirmAction === 'reclassify-all'} onClose={closeConfirm} title="Reclassify all comments" size="md">
        <p className="text-sm text-mistral-ink">
          Existing classifications will be removed and every comment will be queued for re-classification. This cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={closeConfirm}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleReclassifyAll} isLoading={isReclassifying}>
            Reclassify everything
          </Button>
        </div>
      </Modal>

      <Modal isOpen={confirmAction === 'wipe-graph'} onClose={closeConfirm} title="Wipe graph" size="md">
        <p className="text-sm text-mistral-ink">
          This will permanently delete <strong>every account cluster, external account, and cluster
          connection</strong>. Comments are kept but detached from their authors. This action cannot be undone.
        </p>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="secondary" onClick={closeConfirm}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleWipeGraph} isLoading={isWipingGraph}>
            Wipe the graph
          </Button>
        </div>
      </Modal>
    </div>
  );
};

const AdminSettingsPage = () => (
  <AuthProvider>
    <AdminSettingsContent />
  </AuthProvider>
);

export default AdminSettingsPage;
