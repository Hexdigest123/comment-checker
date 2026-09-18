"use client";

import { useState, useEffect } from 'react';
import axios from 'axios';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title } from 'chart.js';
import { Pie, Bar } from 'react-chartjs-2';

// Register ChartJS components
ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement, Title);

// Define types
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

// Status colors
const statusColors: Record<string, string> = {
  pending: '#fbbf24',
  waiting: '#6b7280',
  processing: '#3b82f6',
  completed: '#10b981',
  failed: '#ef4444',
};

// Category colors
const categoryColors: Record<string, string> = {
  none: '#9ca3af',
  incitement_to_crime: '#ef4444',
  approval_of_arbitrary_action: '#f97316',
  incitement_to_hatred: '#ea580c',
  insult: '#eab308',
  threat: '#dc2626',
  glorification_of_nazism: '#7c2d12',
  religious_defamation: '#7c3aed',
  other: '#6b7280',
};

// Date range options
const dateRangeOptions = [
  { value: '1m', label: 'Last 1 Month' },
  { value: '6m', label: 'Last 6 Months' },
  { value: '1y', label: 'Last 1 Year' },
  { value: 'all', label: 'All Time' },
];

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
      
      const response = await axios.get(`/api/v1/dashboard/stats`, {
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
    return statusColors[status] || '#6b7280';
  };

  // Get category color
  const getCategoryColor = (category: string): string => {
    return categoryColors[category] || '#6b7280';
  };

  // Loading state
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8">
          <div className="animate-pulse flex space-x-4">
            <div className="flex-1 space-y-6 py-1">
              <div className="h-2 bg-gray-200 rounded"></div>
              <div className="space-y-3">
                <div className="grid grid-cols-4 gap-4">
                  <div className="h-2 bg-gray-200 rounded col-span-1"></div>
                  <div className="h-2 bg-gray-200 rounded col-span-1"></div>
                  <div className="h-2 bg-gray-200 rounded col-span-1"></div>
                  <div className="h-2 bg-gray-200 rounded col-span-1"></div>
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
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">{error}</h3>
          </div>
        </div>
      </div>
    );
  }

  // No data
  if (!stats) {
    return (
      <div className="text-center py-12">
        <svg className="w-16 h-16 mx-auto mb-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-900">No Data Available</h3>
        <p className="text-gray-500 mt-1">Start by uploading comments to classify</p>
      </div>
    );
  }

  // Main dashboard
  return (
    <div className="space-y-6">
      {/* Date range selector */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Date Range</h2>
            <p className="text-sm text-gray-500">Select the time period for statistics</p>
          </div>
          <div className="flex items-center space-x-2">
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="block w-48 px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            >
              {dateRangeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 text-sm font-medium text-primary-600 bg-primary-50 rounded-lg hover:bg-primary-100 transition-colors"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
        {/* Total Comments */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Total Comments</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{formatNumber(stats.summary.total_comments)}</p>
            </div>
          </div>
        </div>

        {/* Total Classifications */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-green-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Classifications</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{formatNumber(stats.summary.total_classifications)}</p>
            </div>
          </div>
        </div>

        {/* Flagged */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-red-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Flagged</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{formatNumber(stats.summary.total_flagged)}</p>
            </div>
          </div>
        </div>

        {/* Flagged Percentage */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-yellow-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-yellow-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Flag Rate</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{formatPercentage(stats.summary.flagged_percentage)}</p>
            </div>
          </div>
        </div>

        {/* Average Harmful */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-purple-50 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-500">Avg Harmful</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{stats.summary.average_harmful.toFixed(3)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Status Distribution Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Status Distribution</h2>
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
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Category Distribution</h2>
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
              <div className="flex items-center justify-center h-full text-gray-500">
                No category data available
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Processing Status</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-3xl font-bold text-blue-600">{formatNumber(stats.summary.in_processing)}</p>
            <p className="text-sm text-gray-500 mt-1">In Processing</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-3xl font-bold text-gray-600">{formatNumber(stats.summary.waiting)}</p>
            <p className="text-sm text-gray-500 mt-1">Waiting</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-3xl font-bold text-green-600">{formatNumber(stats.summary.processed)}</p>
            <p className="text-sm text-gray-500 mt-1">Processed</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-3xl font-bold text-yellow-600">{formatNumber(stats.summary.pending)}</p>
            <p className="text-sm text-gray-500 mt-1">Pending</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <p className="text-3xl font-bold text-red-600">{formatNumber(stats.summary.failed)}</p>
            <p className="text-sm text-gray-500 mt-1">Failed</p>
          </div>
        </div>
      </div>

      {/* Backend Distribution */}
      {Object.keys(stats.backend_distribution).length > 0 && (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Backend Usage</h2>
          <div className="flex flex-wrap gap-4">
            {Object.entries(stats.backend_distribution).map(([backend, count]) => (
              <div key={backend} className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-600">{backend}</span>
                <div className="w-48 bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: `${(count / stats.summary.total_classifications) * 100}%` }}
                  />
                </div>
                <span className="text-sm text-gray-500">{formatNumber(count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DashboardClient;
