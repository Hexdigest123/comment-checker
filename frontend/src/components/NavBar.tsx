import { useState } from 'react';
import { AuthProvider, useAuth } from '../services/auth';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/comments', label: 'Comments' },
  { href: '/graph', label: 'Graph' },
  { href: '/assistant', label: 'AI Assistant' },
  { href: '/upload', label: 'Import' },
];

const NavContent = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex items-center">
            <a href="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              </div>
              <span className="text-xl font-bold text-gray-900">Comment Checker</span>
            </a>
          </div>

          <div className="hidden md:flex items-center space-x-6">
            {links.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-gray-600 hover:text-gray-900 transition-colors text-sm font-medium"
              >
                {link.label}
              </a>
            ))}
          </div>

          <div className="flex items-center">
            {isAuthenticated && user ? (
              <div className="relative">
                <button
                  onClick={() => setMenuOpen(!menuOpen)}
                  className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
                >
                  <span className="w-8 h-8 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center">
                    {(user.username?.[0] || '?').toUpperCase()}
                  </span>
                  <span className="hidden sm:inline">{user.username}</span>
                  <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1">
                    <button
                      onClick={async () => {
                        await logout();
                        window.location.href = '/login';
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-gray-50"
                    >
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <a href="/login" className="text-gray-600 hover:text-gray-900 transition-colors text-sm font-medium">
                Login
              </a>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

const NavBar = () => (
  <AuthProvider>
    <NavContent />
  </AuthProvider>
);

export default NavBar;
