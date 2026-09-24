import { useEffect, useRef, useState } from 'react';
import { AuthProvider, useAuth } from '../../services/auth';
import { clusterApi } from '../../services/api';
import type { GraphData, GraphNode, GraphLink } from '../../types';

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const WIDTH = 900;
const HEIGHT = 560;

const nodeColor = (node: SimNode) => {
  if (node.type === 'cluster') return node.color || '#3b82f6';
  const platformColors: Record<string, string> = {
    instagram: '#e1306c',
    youtube: '#ff0000',
    facebook: '#1877f2',
    twitter: '#1da1f2',
    tiktok: '#000000',
    reddit: '#ff4500',
    linkedin: '#0a66c2',
  };
  return platformColors[node.platform || ''] || '#64748b';
};

const GraphContent = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<SimNode | null>(null);
  const [nodes, setNodes] = useState<SimNode[]>([]);
  const svgRef = useRef<SVGSVGElement>(null);
  const stateRef = useRef<{ nodes: SimNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const draggingRef = useRef<{ index: number; offsetX: number; offsetY: number } | null>(null);

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
          const force = 3000 / (dist * dist);
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
      const linkDistance = 110;
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
    draggingRef.current = { index, offsetX: point.x - node.x, offsetY: point.y - node.y };
    setSelected(node);
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const drag = draggingRef.current;
    if (!drag) return;
    const point = toSvgCoords(e);
    const node = stateRef.current.nodes[drag.index];
    node.x = point.x - drag.offsetX;
    node.y = point.y - drag.offsetY;
    node.vx = 0;
    node.vy = 0;
  };

  const handleMouseUp = () => {
    draggingRef.current = null;
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
          Please login to view the graph
        </div>
      </div>
    );
  }

  const accountCount = nodes.filter((n) => n.type === 'account').length;
  const clusterCount = nodes.filter((n) => n.type === 'cluster').length;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-800">Entity Graph</h1>
        <p className="text-sm text-gray-500 mt-1">
          Clusters and their accounts with relations. Drag nodes to rearrange.
        </p>
      </div>

      {error && <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          {!graph || nodes.length === 0 ? (
            <div className="flex items-center justify-center h-96 text-gray-500">
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
                    stroke={isConnection ? '#ef4444' : '#cbd5e1'}
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
                    r={node.type === 'cluster' ? 14 : 8}
                    fill={nodeColor(node)}
                    stroke={selected?.id === node.id ? '#1d4ed8' : '#ffffff'}
                    strokeWidth={selected?.id === node.id ? 4 : 2}
                  />
                  <text
                    x={node.x}
                    y={node.y - (node.type === 'cluster' ? 20 : 14)}
                    textAnchor="middle"
                    className="fill-gray-700"
                    style={{ fontSize: 11, fontWeight: node.type === 'cluster' ? 600 : 400 }}
                  >
                    {node.name.length > 18 ? `${node.name.slice(0, 18)}...` : node.name}
                  </text>
                </g>
              ))}
            </svg>
          )}
        </div>

        {/* Legend + selected node details */}
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Legend</h2>
            <div className="space-y-2 text-sm text-gray-600">
              <div className="flex items-center gap-2">
                <span className="inline-block w-4 h-4 rounded-full bg-blue-500" />
                Cluster ({clusterCount})
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-3 h-3 rounded-full bg-slate-500" />
                Account ({accountCount})
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-6 h-0.5 bg-slate-300" style={{ borderTop: '2px dashed #cbd5e1' }} />
                belongs to
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-6 h-0.5 bg-red-500" />
                connection
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-sm font-semibold text-gray-900 mb-3">Details</h2>
            {selected ? (
              <dl className="space-y-2 text-sm">
                <div><dt className="text-gray-500">Name</dt><dd className="text-gray-900 font-medium">{selected.name}</dd></div>
                <div><dt className="text-gray-500">Type</dt><dd className="text-gray-900">{selected.type}</dd></div>
                {selected.platform && (
                  <div><dt className="text-gray-500">Platform</dt><dd className="text-gray-900">{selected.platform}</dd></div>
                )}
                {selected.cluster_type && (
                  <div><dt className="text-gray-500">Cluster type</dt><dd className="text-gray-900">{selected.cluster_type}</dd></div>
                )}
                <div><dt className="text-gray-500">Comments</dt><dd className="text-gray-900">{selected.comment_count ?? '-'}</dd></div>
                {selected.toxicity_score !== undefined && selected.toxicity_score !== null && (
                  <div>
                    <dt className="text-gray-500">Toxicity</dt>
                    <dd className="text-gray-900">{(selected.toxicity_score * 100).toFixed(1)}%</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="text-sm text-gray-500">Click a node to see its details.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const GraphPage = () => (
  <AuthProvider>
    <GraphContent />
  </AuthProvider>
);

export default GraphPage;
