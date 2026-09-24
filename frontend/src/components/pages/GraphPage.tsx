import { useCallback, useEffect, useRef, useState } from 'react';
import { ChevronRight } from 'lucide-react';
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type ForceX,
  type ForceY,
  type Simulation,
} from 'd3-force';
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
  fx?: number | null;
  fy?: number | null;
}

const DEFAULT_WIDTH = 1400;
const DEFAULT_HEIGHT = 800;

// The simulation world is larger than the viewport so the layout has room to
// breathe; the default view fits the whole world (a zoomed-out overview).
const WORLD_SCALE = 2;

// Label detail levels by zoom factor (world width / view width):
// 0 = platform + cluster labels, 1 = + accounts, 2 = + comments
const labelLevelForScale = (zoom: number) => {
  if (zoom >= 1.5) return 2;
  if (zoom >= 0.9) return 1;
  return 0;
};

const platformColors: Record<string, string> = {
  instagram: '#e1306c',
  youtube: '#ff0000',
  facebook: '#1877f2',
  twitter: '#1da1f2',
  tiktok: '#000000',
  reddit: '#ff4500',
  linkedin: '#0a66c2',
};

const nodeColor = (node: SimNode) => {
  if (node.type === 'platform') return platformColors[node.platform || ''] || '#6d6d78';
  if (node.type === 'cluster') return node.color || '#0087e9';
  if (node.type === 'comment') return '#6d6d78';
  return platformColors[node.platform || ''] || '#6d6d78';
};

const nodeRadius = (node: SimNode) => {
  switch (node.type) {
    case 'platform':
      return 22;
    case 'cluster':
      return 16;
    case 'comment':
      return 6;
    default:
      return 10;
  }
};

// Charge repulsion per node type; strongly negative for hub-like nodes so the
// platform/cluster backbone spreads out while comment nodes stay compact.
const chargeStrength = (node: SimNode) => {
  switch (node.type) {
    case 'platform':
      return -250;
    case 'cluster':
      return -100;
    case 'account':
      return -50;
    default:
      return -10;
  }
};

// Positioning pull toward the center; y is stronger than x because the graph
// container is wider than it is tall (the ratio is applied at setup time).
const X_PULL = 0.04;

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
      const filter =
        node.type === 'account'
          ? { account_id: node.id }
          : node.type === 'comment' && node.account_id
            ? { account_id: node.account_id }
            : { cluster_id: node.id };
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
                          <ChevronRight size={14} className="transition-all duration-300 group-hover:translate-x-0.5" aria-hidden />
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
  const [showComments, setShowComments] = useState(true);
  const [view, setView] = useState({ x: 0, y: 0, w: DEFAULT_WIDTH * WORLD_SCALE, h: DEFAULT_HEIGHT * WORLD_SCALE });
  const [labelLevel, setLabelLevel] = useState(1);
  const [svgEl, setSvgEl] = useState<SVGSVGElement | null>(null);
  const sizeRef = useRef({ width: DEFAULT_WIDTH, height: DEFAULT_HEIGHT });
  const viewRef = useRef({ x: 0, y: 0, w: DEFAULT_WIDTH * WORLD_SCALE, h: DEFAULT_HEIGHT * WORLD_SCALE });
  const panningRef = useRef<{ lastX: number; lastY: number } | null>(null);
  const simNodesRef = useRef<SimNode[]>([]);
  const simulationRef = useRef<Simulation<SimNode, undefined> | null>(null);
  const nodeElsRef = useRef(new Map<string, SVGGElement>());
  const linkElsRef = useRef<(SVGLineElement | null)[]>([]);
  const draggingRef = useRef<{ index: number; offsetX: number; offsetY: number; moved: boolean } | null>(null);
  const svgRefCallback = useCallback((el: SVGSVGElement | null) => setSvgEl(el), []);

  useEffect(() => {
    if (!isAuthenticated) return;
    clusterApi
      .graph({ include_comments: showComments })
      .then((r) => setGraph(r.data))
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load graph'));
  }, [isAuthenticated, showComments]);

  // Track the rendered SVG size so the graph fills the page
  useEffect(() => {
    if (!svgEl) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const next = {
        width: Math.round(entry.contentRect.width),
        height: Math.round(entry.contentRect.height),
      };
      if (next.width < 1 || next.height < 1) return;
      if (Math.abs(next.width - sizeRef.current.width) < 1 && Math.abs(next.height - sizeRef.current.height) < 1) return;
      // Keep the current zoom level and center when the container resizes
      // (zoom is tracked relative to the world, which scales with the container)
      const prevWorldW = sizeRef.current.width * WORLD_SCALE;
      const scale = viewRef.current.w / prevWorldW;
      const currentView = viewRef.current;
      const nextView = {
        w: next.width * WORLD_SCALE * scale,
        h: next.height * WORLD_SCALE * scale,
        x: currentView.x + currentView.w / 2 - (next.width * WORLD_SCALE * scale) / 2,
        y: currentView.y + currentView.h / 2 - (next.height * WORLD_SCALE * scale) / 2,
      };
      viewRef.current = nextView;
      setView(nextView);
      sizeRef.current = next;
      // Keep the positioning targets in sync with the new bounds and gently
      // reheat so the settled layout adapts, then cools down again.
      const simulation = simulationRef.current;
      const forceX_ = simulation?.force('x') as ForceX<SimNode> | undefined;
      const forceY_ = simulation?.force('y') as ForceY<SimNode> | undefined;
      if (simulation && forceX_ && forceY_) {
        forceX_.x(next.width / 2);
        forceY_.y(next.height / 2);
        forceY_.strength(X_PULL * (next.width / next.height));
        simulation.alpha(0.1).restart();
      }
    });
    observer.observe(svgEl);
    return () => observer.disconnect();
  }, [svgEl]);

  // Wheel zoom: scale the viewBox window toward the pointer. Attached natively
  // so preventDefault works (React wheel listeners are passive).
  useEffect(() => {
    if (!svgEl) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = svgEl.getBoundingClientRect();
      const current = viewRef.current;
      const px = current.x + ((e.clientX - rect.left) / rect.width) * current.w;
      const py = current.y + ((e.clientY - rect.top) / rect.height) * current.h;
      const worldW = sizeRef.current.width * WORLD_SCALE;
      const factor = Math.exp(e.deltaY * 0.0015);
      const nextW = Math.max(60, Math.min(worldW * 1.25, current.w * factor));
      const nextH = nextW * (current.h / current.w);
      const next = {
        x: px - (px - current.x) * (nextW / current.w),
        y: py - (py - current.y) * (nextH / current.h),
        w: nextW,
        h: nextH,
      };
      viewRef.current = next;
      setView(next);
      setLabelLevel(labelLevelForScale(worldW / nextW));
    };
    svgEl.addEventListener('wheel', onWheel, { passive: false });
    return () => svgEl.removeEventListener('wheel', onWheel);
  }, [svgEl]);

  // Initialize the force simulation on graph load. Positions are written
  // straight to the DOM in the tick handler, so React renders the structure
  // once and never re-renders during the animation. The simulation cools down
  // via alpha decay and stops by itself once the layout settles.
  useEffect(() => {
    if (!graph) return;
    const worldW = sizeRef.current.width * WORLD_SCALE;
    const worldH = sizeRef.current.height * WORLD_SCALE;
    const simNodes: SimNode[] = graph.nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(1, graph.nodes.length);
      const radius = Math.min(worldW, worldH) / 3;
      return {
        ...node,
        x: worldW / 2 + radius * Math.cos(angle),
        y: worldH / 2 + radius * Math.sin(angle),
        vx: 0,
        vy: 0,
      };
    });
    simNodesRef.current = simNodes;
    setNodes(simNodes);
    nodeElsRef.current.clear();
    linkElsRef.current = [];

    // d3-force replaces link.source/target with node object references, so
    // clone the links and keep the index pairs for the DOM updater.
    const simLinks = graph.links.map((link) => ({ ...link }));
    const endpoints = simLinks.map((link) => ({ source: link.source, target: link.target }));

    const updateDom = () => {
      const w = sizeRef.current.width * WORLD_SCALE;
      const h = sizeRef.current.height * WORLD_SCALE;
      const nodeEls = nodeElsRef.current;
      for (const node of simNodes) {
        node.x = Math.max(40, Math.min(w - 40, node.x));
        node.y = Math.max(40, Math.min(h - 40, node.y));
        nodeEls
          .get(node.id)
          ?.setAttribute('transform', `translate(${node.x} ${node.y})`);
      }
      const linkEls = linkElsRef.current;
      for (let i = 0; i < endpoints.length; i++) {
        const line = linkEls[i];
        const a = simNodes[endpoints[i].source];
        const b = simNodes[endpoints[i].target];
        if (!line || !a || !b) continue;
        line.setAttribute('x1', String(a.x));
        line.setAttribute('y1', String(a.y));
        line.setAttribute('x2', String(b.x));
        line.setAttribute('y2', String(b.y));
      }
    };

    const simulation = forceSimulation(simNodes)
      .velocityDecay(0.3)
      // Charge, link length and centering pull all scale with the world so the
      // layout fills it instead of clustering in the middle.
      .force(
        'charge',
        forceManyBody<SimNode>()
          .strength((d) => chargeStrength(d) * WORLD_SCALE)
          .distanceMax(800 * WORLD_SCALE)
      )
      .force('link', forceLink<SimNode, GraphLink>(simLinks).distance(100 * WORLD_SCALE).strength(0.05))
      .force('x', forceX<SimNode>(worldW / 2).strength(X_PULL * WORLD_SCALE))
      .force('y', forceY<SimNode>(worldH / 2).strength(X_PULL * WORLD_SCALE * (worldW / worldH)))
      .force('collide', forceCollide<SimNode>((d) => nodeRadius(d) + 4))
      .on('tick', updateDom);

    simulationRef.current = simulation;
    return () => {
      simulation.stop();
      simulationRef.current = null;
    };
  }, [graph]);

  const toSvgCoords = (e: React.MouseEvent) => {
    if (!svgEl) return { x: 0, y: 0 };
    const rect = svgEl.getBoundingClientRect();
    const current = viewRef.current;
    return {
      x: current.x + ((e.clientX - rect.left) / rect.width) * current.w,
      y: current.y + ((e.clientY - rect.top) / rect.height) * current.h,
    };
  };

  // Pan by dragging the background (nodes call stopPropagation in their own
  // mousedown handler, so this only fires for the svg/line background).
  const handleBackgroundMouseDown = (e: React.MouseEvent) => {
    panningRef.current = { lastX: e.clientX, lastY: e.clientY };
  };

  const handleMouseDown = (e: React.MouseEvent, index: number) => {
    e.stopPropagation();
    const point = toSvgCoords(e);
    const node = simNodesRef.current[index];
    if (!node) return;
    draggingRef.current = { index, offsetX: point.x - node.x, offsetY: point.y - node.y, moved: false };
    node.fx = node.x;
    node.fy = node.y;
    setSelected(node);
    simulationRef.current?.alphaTarget(0.3).restart();
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const drag = draggingRef.current;
    if (drag) {
      const node = simNodesRef.current[drag.index];
      if (!node) return;
      const point = toSvgCoords(e);
      const nextX = point.x - drag.offsetX;
      const nextY = point.y - drag.offsetY;
      if (Math.hypot(nextX - (node.fx ?? node.x), nextY - (node.fy ?? node.y)) > 4) drag.moved = true;
      node.fx = nextX;
      node.fy = nextY;
      return;
    }
    const pan = panningRef.current;
    if (!pan || !svgEl) return;
    const rect = svgEl.getBoundingClientRect();
    const current = viewRef.current;
    const next = {
      ...current,
      x: current.x - ((e.clientX - pan.lastX) / rect.width) * current.w,
      y: current.y - ((e.clientY - pan.lastY) / rect.height) * current.h,
    };
    pan.lastX = e.clientX;
    pan.lastY = e.clientY;
    viewRef.current = next;
    setView(next);
  };

  const handleMouseUp = () => {
    const drag = draggingRef.current;
    draggingRef.current = null;
    panningRef.current = null;
    if (drag) {
      const node = simNodesRef.current[drag.index];
      if (node) {
        node.fx = null;
        node.fy = null;
      }
      simulationRef.current?.alphaTarget(0);
    }
    // Platform nodes are structural; the details modal needs a cluster or account
    if (drag && !drag.moved && selected?.type !== 'platform') setDetailsOpen(true);
  };

  const resetView = () => {
    const next = {
      x: 0,
      y: 0,
      w: sizeRef.current.width * WORLD_SCALE,
      h: sizeRef.current.height * WORLD_SCALE,
    };
    viewRef.current = next;
    setView(next);
    setLabelLevel(labelLevelForScale(1));
  };

  if (authLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
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
  const commentCount = nodes.filter((n) => n.type === 'comment').length;
  const platforms = Array.from(
    new Set(nodes.filter((n) => n.type === 'platform').map((n) => n.platform || ''))
  ).filter(Boolean);

  return (
    <div className="flex flex-col flex-1 min-h-0 p-8">
      {/* Section header with legend on the right */}
      <div className="flex flex-wrap items-start justify-between gap-x-10 gap-y-4 mb-4">
        <div>
          <span className="eyebrow-badge">Network</span>
          <h1 className="mt-3 font-display text-4xl font-semibold text-mistral-ink leading-tight">Entity Graph</h1>
          <p className="mt-2 text-sm text-mistral-muted max-w-xl">
            Platforms, clusters, accounts and their comments. Click a node for details, drag to rearrange.
          </p>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 text-base text-mistral-ink ml-auto pt-2">
          <div className="flex items-center gap-3">
            <span className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">Platform</span>
            {platforms.map((p) => (
              <span key={p} className="flex items-center gap-1.5">
                <span
                  className="inline-block w-4 h-4 rounded-full"
                  style={{ backgroundColor: platformColors[p] || '#6d6d78' }}
                />
                {p}
              </span>
            ))}
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-5 h-5 rounded-full bg-mistral-blue" />
            Cluster ({clusterCount})
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-4 h-4 rounded-full bg-mistral-muted" />
            Account ({accountCount})
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-mistral-muted" />
            Comment ({commentCount})
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-8 h-0.5 bg-mistral-blue" />
            platform
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-8 border-t-2 border-dashed border-mistral-border-strong" />
            belongs to
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-block w-8 h-0.5 bg-mistral-red" />
            connection
          </div>
        </div>
      </div>

      {error && <div className="border border-mistral-red/60 bg-mistral-red-tint text-mistral-ink p-4 rounded-md mb-6">{error}</div>}

      {/* Toggle */}
      <div className="flex items-center justify-between mb-4">
        <label className="flex items-center gap-2 text-sm text-mistral-muted cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showComments}
            onChange={(e) => setShowComments(e.target.checked)}
            className="accent-mistral-red"
          />
          Show comments as nodes
        </label>
        <div className="flex items-center gap-3">
          {showComments && graph && (
            <span className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">
              {commentCount} comment nodes
            </span>
          )}
          <Button variant="outline" size="sm" onClick={resetView}>
            Reset view
          </Button>
        </div>
      </div>

      {/* Graph fills the remaining page height */}
      <div className="flex-1 min-h-0 bg-white rounded-md border border-mistral-border p-2">
        {!graph || nodes.length === 0 ? (
          <div className="flex items-center justify-center h-full text-mistral-muted">
            {error ? 'Failed to load graph' : 'No entities yet. Import comments to build clusters.'}
          </div>
        ) : (
          <svg
            ref={svgRefCallback}
            viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
            className="block w-full h-full select-none"
            onMouseDown={handleBackgroundMouseDown}
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
              const isPlatformLink = link.type === 'platform';
              return (
                <line
                  key={i}
                  ref={(el) => {
                    linkElsRef.current[i] = el;
                  }}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  stroke={
                    isConnection
                      ? '#f66c60'
                      : isPlatformLink
                        ? '#0087e9'
                        : 'rgb(var(--color-mistral-border-strong))'
                  }
                  strokeWidth={isConnection ? 2.5 : isPlatformLink ? 2 : 1.5}
                  strokeDasharray={isConnection || isPlatformLink ? undefined : '4 4'}
                />
              );
            })}
            {/* Nodes */}
            {nodes.map((node, i) => {
              // Declutter labels by zoom level: hubs always, accounts when
              // zoomed near the default fit, comments only when zoomed in.
              const showLabel =
                node.type === 'platform' ||
                node.type === 'cluster' ||
                (node.type === 'account' && labelLevel >= 1) ||
                (node.type === 'comment' && labelLevel >= 2);
              return (
              <g
                key={node.id}
                ref={(el) => {
                  if (el) nodeElsRef.current.set(node.id, el);
                  else nodeElsRef.current.delete(node.id);
                }}
                transform={`translate(${node.x} ${node.y})`}
                onMouseDown={(e) => handleMouseDown(e, i)}
                style={{ cursor: 'grab' }}
              >
                <circle
                  r={nodeRadius(node)}
                  fill={nodeColor(node)}
                  stroke={selected?.id === node.id ? '#f66c60' : 'rgb(var(--color-white))'}
                  strokeWidth={selected?.id === node.id ? 4 : 2}
                />
                {showLabel && (
                  <text
                    y={-nodeRadius(node) - 8}
                    textAnchor="middle"
                    className="fill-mistral-muted"
                    style={{
                      fontSize: 12,
                      fontWeight: node.type === 'platform' || node.type === 'cluster' ? 600 : 400,
                    }}
                  >
                    {node.name.length > 18 ? `${node.name.slice(0, 18)}...` : node.name}
                  </text>
                )}
              </g>
              );
            })}
          </svg>
        )}
      </div>

      {/* Node details modal */}
      {detailsOpen && selected && (
        <NodeDetailsModal
          key={selected.id}
          node={selected}
          onClose={() => setDetailsOpen(false)}
          onCommentMutated={() => {
            clusterApi
              .graph({ include_comments: showComments })
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
