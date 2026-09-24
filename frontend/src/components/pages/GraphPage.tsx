import { useEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from '../../services/auth';
import { clusterApi, commentApi } from '../../services/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { StatusBadge, CategoryBadge, SeverityBadge } from '../tables/DataTable';
import { formatDate } from '../../lib/format';
import type { Classification, Comment, GraphData, GraphNode, GraphLink, PageResponse } from '../../types';

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const WIDTH = 1400;
const HEIGHT = 800;

const nodeColor = (node: SimNode) => {
  if (node.type === 'cluster') return node.color || '#0087e9';
  const platformColors: Record<string, string> = {
    instagram: '#e1306c',
    youtube: '#ff0000',
    facebook: '#1877f2',
    twitter: '#1da1f2',
    tiktok: '#000000',
    reddit: '#ff4500',
    linkedin: '#0a66c2',
  };
  return platformColors[node.platform || ''] || '#6d6d78';
};

const latestClassification = (comment: Comment): Classification | null => {
  if (!comment.classifications || comment.classifications.length === 0) return null;
  return [...comment.classifications].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )[0];
};

interface NodeDetailsModalProps {
  node: SimNode;
  onClose: () => void;
  onCommentMutated: () => void;
}

const NodeDetailsModal = ({ node, onClose, onCommentMutated }: NodeDetailsModalProps) => {
  const [comments, setComments] = useState<Comment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [savingId, setSavingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchComments = async () => {
    setIsLoading(true);
    setError('');
    try {
      const filter = node.type === 'account' ? { account_id: node.id } : { cluster_id: node.id };
      const res = await commentApi.list({ ...filter, page_size: 20 });
      setComments((res.data as PageResponse<Comment>).items);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load comments');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchComments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id]);

  const handleSave = async (id: string) => {
    if (!editText.trim()) return;
    setSavingId(id);
    setError('');
    try {
      await commentApi.update(id, { text: editText.trim() });
      setEditingId(null);
      setEditText('');
      await fetchComments();
      onCommentMutated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update comment');
    } finally {
      setSavingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this comment? This cannot be undone.')) return;
    setDeletingId(id);
    setError('');
    try {
      await commentApi.delete(id);
      await fetchComments();
      onCommentMutated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete comment');
    } finally {
      setDeletingId(null);
    }
  };

  const infoRows: [string, string][] = [
    ['Type', node.type],
    ...(node.platform ? ([['Platform', node.platform]] as [string, string][]) : []),
    ...(node.cluster_type ? ([['Cluster type', node.cluster_type]] as [string, string][]) : []),
    ['Comments', String(node.comment_count ?? '-')],
  ];
  if (node.toxicity_score !== undefined && node.toxicity_score !== null) {
    infoRows.push(['Toxicity', `${(node.toxicity_score * 100).toFixed(1)}%`]);
  }

  return (
    <Modal isOpen onClose={onClose} title={node.name} size="2xl">
      {/* Key info */}
      <dl className="grid grid-cols-2 gap-4 text-sm">
        {infoRows.map(([label, value]) => (
          <div key={label}>
            <dt className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">{label}</dt>
            <dd className="text-mistral-ink font-medium">{value}</dd>
          </div>
        ))}
      </dl>

      {error && (
        <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-3 rounded-md mt-4 text-sm">
          {error}
        </div>
      )}

      {/* Comments with classification */}
      <div className="mt-6">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">Comments</h3>
          <span className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">
            {comments.length} shown
          </span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin h-8 w-8 border-4 border-mistral-ink border-t-transparent rounded-full"></div>
          </div>
        ) : comments.length === 0 ? (
          <p className="text-mistral-muted text-sm py-4">No comments linked to this {node.type}.</p>
        ) : (
          <ul className="space-y-3">
            {comments.map((comment) => {
              const classification = latestClassification(comment);
              const isEditing = editingId === comment.id;
              return (
                <li key={comment.id} className="border border-mistral-border rounded-md p-4">
                  {isEditing ? (
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      rows={3}
                      className="w-full border border-mistral-border-strong rounded-md p-2 text-sm text-mistral-ink focus:outline-none focus:ring-2 focus:ring-mistral-red"
                    />
                  ) : (
                    <p className="text-sm text-mistral-ink whitespace-pre-wrap">{comment.text}</p>
                  )}

                  <div className="flex flex-wrap items-center gap-2 mt-3">
                    <StatusBadge status={comment.status} />
                    {classification ? (
                      <>
                        <CategoryBadge category={classification.category} />
                        {classification.severity && <SeverityBadge severity={classification.severity} />}
                        <span className="font-mono text-[11px] text-mistral-muted">
                          {((classification.confidence || 0) * 100).toFixed(0)}% confidence
                        </span>
                      </>
                    ) : (
                      <span className="font-mono text-[11px] uppercase tracking-wide text-mistral-muted">
                        Not classified
                      </span>
                    )}
                    <span className="font-mono text-[11px] text-mistral-muted ml-auto">
                      {formatDate(comment.created_at)}
                    </span>
                  </div>

                  <div className="flex gap-2 mt-3">
                    {isEditing ? (
                      <>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleSave(comment.id)}
                          isLoading={savingId === comment.id}
                          disabled={!editText.trim() || editText.trim() === comment.text}
                        >
                          Save
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingId(null);
                            setEditText('');
                          }}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingId(comment.id);
                            setEditText(comment.text);
                          }}
                        >
                          Edit
                        </Button>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDelete(comment.id)}
                          isLoading={deletingId === comment.id}
                        >
                          Delete
                        </Button>
                        <a
                          href={`/comments/${comment.id}`}
                          className="group inline-flex items-center gap-1 text-sm text-mistral-ink hover:text-mistral-red-deep transition-colors duration-200 self-center ml-1"
                        >
                          View
                          <span className="transition-all duration-300 group-hover:translate-x-0.5">→</span>
                        </a>
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Modal>
  );
};

const GraphContent = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<SimNode | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const svgRef = useRef<SVGSVGElement>(null);
  const stateRef = useRef<{ nodes: SimNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const draggingRef = useRef<{ index: number; offsetX: number; offsetY: number; moved: boolean } | null>(null);

  useEffect(() => {
    if (!isAuthenticated) return;
    clusterApi
      .graph()
      .then((r) => setGraph(r.data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load graph'));
  }, [isAuthenticated]);

  // Initialize simulation nodes on graph load
  useEffect(() => {
    if (!graph) return;
    const simNodes: SimNode[] = graph.nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, graph.nodes.length);
      const radius = Math.min(WIDTH, HEIGHT) / 3;
      return {
        ...node,
        x: WIDTH / 2 + radius * Math.cos(angle),
        y: HEIGHT / 2 + radius * Math.sin(angle),
        vx: 0,
        vy: 0,
      };
    });
    stateRef.current = { nodes: simNodes, links: graph.links };
    setNodes(simNodes);

    let raf = 0;
    const step = () => {
      const { nodes: current, links } = stateRef.current;

      // Repulsion between all nodes
      for (let i = 0; i < current.length; i++) {
        for (let j = i + 1; j < current.length; j++) {
          const a = current[i];
          const b = current[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let dist = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = 6000 / (dist * dist);
          dx /= dist;
          dy /= dist;
          a.vx -= dx * force;
          a.vy -= dy * force;
          b.vx += dx * force;
          b.vy += dy * force;
        }
      }

      // Springs along links
      const linkStrength = 0.02;
      const linkDistance = 140;
      for (const link of links) {
        const a = current[link.source];
        const b = current[link.target];
        if (!a || !b) continue;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - linkDistance) * linkStrength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (draggingRef.current?.index !== link.source) {
          a.vx += fx;
          a.vy += fy;
        }
        if (draggingRef.current?.index !== link.target) {
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      // Centering + damping + integration
      for (const node of current) {
        node.vx += (WIDTH / 2 - node.x) * 0.002;
        node.vy += (HEIGHT / 2 - node.y) * 0.002;
        node.vx *= 0.85;
        node.vy *= 0.85;
        if (draggingRef.current?.index !== current.indexOf(node)) {
          node.x += node.vx;
          node.y += node.vy;
        }
        node.x = Math.max(40, Math.min(WIDTH - 40, node.x));
        node.y = Math.max(40, Math.min(HEIGHT - 40, node.y));
      }

      setNodes([...current]);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [graph]);

  const toSvgCoords = (e: React.MouseEvent) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    return {
      x: ((e.clientX - rect.left) / rect.width) * WIDTH,
      y: ((e.clientY - rect.top) / rect.height) * HEIGHT,
    };
  };

  const handleMouseDown = (e: React.MouseEvent, index: number) => {
    const point = toSvgCoords(e);
    const node = stateRef.current.nodes[index];
    draggingRef.current = { index, offsetX: point.x - node.x, offsetY: point.y - node.y, moved: false };
    setSelected(node);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const drag = draggingRef.current;
    if (!drag) return;
    const point = toSvgCoords(e);
    const node = stateRef.current.nodes[drag.index];
    const nextX = point.x - drag.offsetX;
    const nextY = point.y - drag.offsetY;
    if (Math.hypot(nextX - node.x, nextY - node.y) > 4) drag.moved = true;
    node.x = nextX;
    node.y = nextY;
    node.vx = 0;
    node.vy = 0;
  };

  const handleMouseUp = () => {
    const drag = draggingRef.current;
    draggingRef.current = null;
    if (drag && !drag.moved) setDetailsOpen(true);
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
          Please login to view the graph
        </div>
      </div>
    );
  }

  const accountCount = nodes.filter((n) => n.type === 'account').length;
  const clusterCount = nodes.filter((n) => n.type === 'cluster').length;

  return (
    <div className="p-8">
      {/* Section header */}
      <div className="mb-8">
        <span className="eyebrow-badge">Network</span>
        <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">Entity Graph</h1>
        <p className="mt-2 text-sm text-mistral-muted max-w-xl">
          Clusters and their accounts with relations. Click a node for details, drag to rearrange.
        </p>
      </div>

      {error && <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">{error}</div>}

      <div className="bg-white rounded-md border border-mistral-border p-4">
        {!graph || nodes.length === 0 ? (
          <div className="flex items-center justify-center h-96 text-mistral-muted">
            {error ? 'Failed to load graph' : 'No entities yet. Import comments to build clusters.'}
          </div>
        ) : (
          <svg
            ref={svgRef}
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="w-full h-auto select-none"
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            {/* Links */}
            {graph.links.map((link, i) => {
              const a = nodes[link.source];
              const b = nodes[link.target];
              if (!a || !b) return null;
              const isConnection = link.type === 'connection';
              return (
                <line
                  key={i}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={isConnection ? '#f66c60' : 'rgb(var(--color-mistral-border-strong))'}
                  strokeWidth={isConnection ? 2.5 : 1.5}
                  strokeDasharray={isConnection ? undefined : '4 4'}
                />
              );
            })}
            {/* Nodes */}
            {nodes.map((node, i) => (
              <g
                key={node.id}
                onMouseDown={(e) => handleMouseDown(e, i)}
                style={{ cursor: 'grab' }}
              >
                <circle
                  cx={node.x}
                  cy={node.y}
                  r={node.type === 'cluster' ? 16 : 10}
                  fill={nodeColor(node)}
                  stroke={selected?.id === node.id ? '#f66c60' : 'rgb(var(--color-white))'}
                  strokeWidth={selected?.id === node.id ? 4 : 2}
                />
                <text
                  x={node.x}
                  y={node.y - (node.type === 'cluster' ? 24 : 16)}
                  textAnchor="middle"
                  className="fill-mistral-muted"
                  style={{ fontSize: 12, fontWeight: node.type === 'cluster' ? 600 : 400 }}
                >
                  {node.name.length > 18 ? `${node.name.slice(0, 18)}...` : node.name}
                </text>
              </g>
            ))}
          </svg>
        )}
      </div>

      {/* Legend */}
      <div className="bg-white rounded-md border border-mistral-border p-6 mt-6">
        <h2 className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mb-3">Legend</h2>
        <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-mistral-muted">
          <div className="flex items-center gap-2">
            <span className="inline-block w-4 h-4 rounded-full bg-mistral-blue" />
            Cluster ({clusterCount})
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-mistral-muted" />
            Account ({accountCount})
          </div>
          <div className="flex items-center gap-2">
            <span
              className="inline-block w-6 h-0.5"
              style={{ borderTop: '2px dashed rgb(var(--color-mistral-border-strong))' }}
            />
            belongs to
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-block w-6 h-0.5 bg-mistral-red" />
            connection
          </div>
        </div>
      </div>

      {/* Node details modal */}
      {detailsOpen && selected && (
        <NodeDetailsModal
          key={selected.id}
          node={selected}
          onClose={() => setDetailsOpen(false)}
          onCommentMutated={() => {
            clusterApi
              .graph()
              .then((r) => setGraph(r.data))
              .catch(() => {});
          }}
        />
      )}
    </div>
  );
};

const GraphPage = () => (
  <AuthProvider>
    <GraphContent />
  </AuthProvider>
);

export default GraphPage;
