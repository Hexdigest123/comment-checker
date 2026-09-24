"use client";

import { useState, useEffect } from 'react';
import api from '../services/api';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';
import { Pie, Bar } from 'react-chartjs-2';

// Register ChartJS components
ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

// Neutral defaults that read well on both cream and steel surfaces
ChartJS.defaults.color = '#6d6d78';
ChartJS.defaults.borderColor = 'rgba(109, 109, 120, 0.15)';

interface DashboardSummary {
  total_comments: number;
  total_classifications: number;
  total_flagged: number;
  total_not_flagged: number;
  flagged_percentage: number;
  average_harmful: number;
  in_processing: number;
  waiting: number;
  processed: number;
  pending: number;
  failed: number;
}

interface StatusDistribution {
  status: string;
  count: number;
  percentage: number;
}

interface CategoryDistribution {
  category: string;
  category_label: string;
  count: number;
  percentage: number;
}

interface DashboardStats {
  summary: DashboardSummary;
  status_distribution: StatusDistribution[];
  category_distribution: CategoryDistribution[];
  backend_distribution: Record<string, number>;
  date_range: string;
}

// Status colors — Mistral joy accents
const statusColors: Record<string, string> = {
  pending: '#fec835',
  waiting: '#6d6d78',
  processing: '#0087e9',
  completed: '#45bf87',
  failed: '#f66c60',
};

// Category colors — Mistral joy accents
const categoryColors: Record<string, string> = {
  safe: '#45bf87',
  hate: '#e51300',
  harassment: '#ff6523',
  violence: '#f66c60',
  self_harm: '#ff95de',
  sexual: '#ffc2eb',
  spam: '#6d6d78',
  illegal: '#0087e9',
  financial: '#f7b900',
  health: '#00c8b4',
  legal: '#0057d2',
  pii: '#ff9f1c',
  jailbreaking: '#8f4bd8',
};

// Date range options
const dateRangeOptions = [
  { value: '1m', label: 'Last 1 Month' },
  { value: '6m', label: 'Last 6 Months' },
  { value: '1y', label: 'Last 1 Year' },
  { value: 'all', label: 'All Time' },
];

interface SummaryCardProps {
  label: string;
  value: string;
  icon: React.ReactNode;
  chipClass: string;
}

const SummaryCard = ({ label, value, icon, chipClass }: SummaryCardProps) => (
  <div className="bg-white rounded-md border border-mistral-border p-6 transition-colors duration-300 hover:border-mistral-border-strong">
    <div className="flex items-center">
      <div className="flex-shrink-0">
        <div className={`w-10 h-10 rounded-md border flex items-center justify-center ${chipClass}`}>
          {icon}
        </div>
      </div>
      <div className="ml-4">
        <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted">{label}</p>
        <p className="font-display text-2xl font-semibold text-mistral-ink mt-1">{value}</p>
      </div>
    </div>
  </div>
);

// DashboardClient component
const DashboardClient = () => {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState('1y');

  // Fetch dashboard stats
  const fetchStats = async (range: string) => {
    try {
      setLoading(true);
      setError(null);

      const response = await api.get('/dashboard/stats', {
        params: { date_range: range },
      });

      setStats(response.data);
    } catch (err) {
      console.error('Failed to fetch dashboard stats:', err);
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchStats(dateRange);
  }, []);

  // Fetch when date range changes
  useEffect(() => {
    fetchStats(dateRange);
  }, [dateRange]);

  // Refresh function
  const handleRefresh = () => {
    fetchStats(dateRange);
  };

  // Format number with commas
  const formatNumber = (num: number): string => {
    return new Intl.NumberFormat().format(num);
  };

  // Format percentage
  const formatPercentage = (num: number): string => {
    return `${num.toFixed(1)}%`;
  };

  // Get status badge color
  const getStatusColor = (status: string): string => {
    return statusColors[status] || '#6d6d78';
  };

  // Get category color
  const getCategoryColor = (category: string): string => {
    return categoryColors[category] || '#6d6d78';
  };

  // Loading state
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-md border border-mistral-border p-8">
          <div className="animate-pulse flex space-x-4">
            <div className="flex-1 space-y-6 py-1">
              <div className="h-2 bg-mistral-inset rounded"></div>
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-4">
                  <div className="h-2 bg-mistral-inset rounded col-span-1"></div>
                  <div className="h-2 bg-mistral-inset rounded col-span-1"></div>
                  <div className="h-2 bg-mistral-inset rounded col-span-1"></div>
                  <div className="h-2 bg-mistral-inset rounded col-span-1"></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="border border-mistral-red/60 bg-mistral-red-tint rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-mistral-red-deep" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-mistral-ink">{error}</h3>
          </div>
        </div>
      </div>
    );
  }

  // No data
  if (!stats) {
    return (
      <div className="text-center py-12">
        <svg className="w-16 h-16 mx-auto mb-4 text-mistral-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="font-display text-lg font-medium text-mistral-ink">No Data Available</h3>
        <p className="text-mistral-muted mt-1">Start by uploading comments to classify</p>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="space-y-6">
      {/* Date range selector */}
      <div className="bg-white rounded-md border border-mistral-border p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <span className="eyebrow">Statistics</span>
            <h2 className="font-display text-lg font-semibold text-mistral-ink mt-1">Date Range</h2>
            <p className="text-sm text-mistral-muted">Select the time period for statistics</p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="block w-48 px-3 py-2 font-mono text-xs uppercase tracking-wide border border-mistral-border-strong rounded-md bg-white text-mistral-ink focus:outline-none focus:border-mistral-ink transition-colors duration-200"
            >
              {dateRangeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 font-display text-sm font-medium text-mistral-ink border border-mistral-border-strong rounded-md hover:border-mistral-ink transition-colors duration-200"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        <SummaryCard
          label="Total Comments"
          value={formatNumber(stats.summary.total_comments)}
          chipClass="bg-mistral-blue-tint border-mistral-blue/40"
          icon={
            <svg className="w-5 h-5 text-mistral-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          }
        />
        <SummaryCard
          label="Classifications"
          value={formatNumber(stats.summary.total_classifications)}
          chipClass="bg-mistral-green-tint border-mistral-green/50"
          icon={
            <svg className="w-5 h-5 text-mistral-green" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <SummaryCard
          label="Flagged"
          value={formatNumber(stats.summary.total_flagged)}
          chipClass="bg-mistral-red-tint border-mistral-red/60"
          icon={
            <svg className="w-5 h-5 text-mistral-red" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <SummaryCard
          label="Flag Rate"
          value={formatPercentage(stats.summary.flagged_percentage)}
          chipClass="bg-mistral-yellow-tint border-mistral-yellow/70"
          icon={
            <svg className="w-5 h-5 text-mistral-orange" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
            </svg>
          }
        />
        <SummaryCard
          label="Avg Harmful"
          value={stats.summary.average_harmful.toFixed(3)}
          chipClass="bg-mistral-pink-tint border-mistral-pink/60"
          icon={
            <svg className="w-5 h-5 text-mistral-pink" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
        />
      </div>

      {/* Status Distribution Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-md border border-mistral-border p-6">
          <h2 className="font-display text-lg font-semibold text-mistral-ink mb-4">Status Distribution</h2>
          <div className="chart-container">
            <Bar
              data={{
                labels: stats.status_distribution.map((s) => s.status),
                datasets: [
                  {
                    label: 'Count',
                    data: stats.status_distribution.map((s) => s.count),
                    backgroundColor: stats.status_distribution.map((s) => getStatusColor(s.status)),
                    borderRadius: 4,
                  },
                ],
              }}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    display: false,
                  },
                  tooltip: {
                    callbacks: {
                      label: (context) => {
                        const item = stats.status_distribution[context.dataIndex];
                        return `${item.status}: ${item.count} (${item.percentage}%)`;
                      },
                    },
                  },
                },
                scales: {
                  y: {
                    beginAtZero: true,
                    ticks: {
                      stepSize: 1,
                    },
                  },
                },
              }}
            />
          </div>
        </div>

        {/* Category Distribution Chart */}
        <div className="bg-white rounded-md border border-mistral-border p-6">
          <h2 className="font-display text-lg font-semibold text-mistral-ink mb-4">Category Distribution</h2>
          <div className="chart-container">
            {stats.category_distribution.length > 0 ? (
              <Pie
                data={{
                  labels: stats.category_distribution.map((c) => c.category_label),
                  datasets: [
                    {
                      data: stats.category_distribution.map((c) => c.count),
                      backgroundColor: stats.category_distribution.map((c) => getCategoryColor(c.category)),
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'right',
                    },
                    tooltip: {
                      callbacks: {
                        label: (context) => {
                          const item = stats.category_distribution[context.dataIndex];
                          return `${item.category_label}: ${item.count} (${item.percentage}%)`;
                        },
                      },
                    },
                  },
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-mistral-muted">
                No category data available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detailed Stats — spec-sheet rows with hairline dividers */}
      <div className="bg-white rounded-md border border-mistral-border p-6">
        <h2 className="font-display text-lg font-semibold text-mistral-ink mb-4">Processing Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-4 bg-mistral-surface border border-mistral-border rounded-md">
            <p className="font-display text-3xl font-semibold text-mistral-blue">{formatNumber(stats.summary.in_processing)}</p>
            <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mt-1">In Processing</p>
          </div>
          <div className="text-center p-4 bg-mistral-surface border border-mistral-border rounded-md">
            <p className="font-display text-3xl font-semibold text-mistral-muted">{formatNumber(stats.summary.waiting)}</p>
            <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mt-1">Waiting</p>
          </div>
          <div className="text-center p-4 bg-mistral-surface border border-mistral-border rounded-md">
            <p className="font-display text-3xl font-semibold text-mistral-green">{formatNumber(stats.summary.processed)}</p>
            <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mt-1">Processed</p>
          </div>
          <div className="text-center p-4 bg-mistral-surface border border-mistral-border rounded-md">
            <p className="font-display text-3xl font-semibold text-mistral-orange">{formatNumber(stats.summary.pending)}</p>
            <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mt-1">Pending</p>
          </div>
          <div className="text-center p-4 bg-mistral-surface border border-mistral-border rounded-md">
            <p className="font-display text-3xl font-semibold text-mistral-red">{formatNumber(stats.summary.failed)}</p>
            <p className="font-mono text-[11px] uppercase tracking-widest text-mistral-muted mt-1">Failed</p>
          </div>
        </div>
      </div>

    </div>
  );
};

export default DashboardClient;
