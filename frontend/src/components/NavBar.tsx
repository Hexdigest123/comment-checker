import { useEffect, useState } from 'react';
import { AuthProvider, useAuth } from '../services/auth';

const links = [
  { href: '/', label: 'Dashboard' },
  { href: '/comments', label: 'Comments' },
  { href: '/graph', label: 'Graph' },
  { href: '/assistant', label: 'AI Assistant' },
  { href: '/upload', label: 'Import' },
];

const ThemeToggle = () => {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    setIsDark(document.documentElement.classList.contains('dark'));
  }, []);

  const toggle = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('theme', next ? 'dark' : 'light');
  };

  return (
    <button
      onClick={toggle}
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      className="h-12 px-3 flex items-center text-mistral-muted hover:bg-mistral-band hover:text-mistral-ink transition-colors duration-200 border-l border-mistral-border"
    >
      {isDark ? (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
        </svg>
      )}
    </button>
  );
};

const NavContent = () => {
  const { user, isAuthenticated, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="bg-mistral-surface border-b border-mistral-border sticky top-0 z-50">
      <div className="flex items-stretch justify-between h-12 px-4 sm:px-6">
        {/* Logo */}
        <a href="/" className="flex items-center gap-2 pr-4">
          <span className="w-6 h-6 rounded-sm bg-mistral-red flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-purewhite" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </span>
          <span className="font-display text-base font-semibold text-mistral-ink tracking-tight">
            Comment Checker
          </span>
        </a>

        {/* Desktop nav items — hairline-separated, display face */}
        <div className="hidden md:flex items-stretch border-l border-mistral-border">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="flex items-center px-4 font-display text-sm text-mistral-ink border-r border-mistral-border hover:bg-mistral-band transition-colors duration-200"
            >
              {link.label}
            </a>
          ))}
        </div>

        <div className="flex items-stretch ml-auto">
          <ThemeToggle />

          {isAuthenticated && user ? (
            <div className="relative flex items-stretch">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex items-center gap-2 px-3 font-display text-sm text-mistral-ink border-l border-mistral-border hover:bg-mistral-band transition-colors duration-200"
              >
                <span className="w-7 h-7 bg-mistral-yellow-tint border border-mistral-yellow/70 text-mistral-ink rounded-full flex items-center justify-center font-mono text-xs uppercase">
                  {(user.username?.[0] || '?').toUpperCase()}
                </span>
                <span className="hidden sm:inline">{user.username}</span>
                <svg className="w-3.5 h-3.5 text-mistral-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-12 w-48 bg-white rounded-md border border-mistral-border py-1">
                  <button
                    onClick={async () => {
                      await logout();
                      window.location.href = '/login';
                    }}
                    className="block w-full text-left px-4 py-2 font-display text-sm text-mistral-red-deep hover:bg-mistral-band transition-colors duration-200"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <a
              href="/login"
              className="hidden md:flex items-center px-4 font-display text-sm text-mistral-ink border-l border-mistral-border hover:bg-mistral-band transition-colors duration-200"
            >
              Login
            </a>
          )}

          {/* Mobile menu button */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle navigation menu"
            className="md:hidden flex items-center px-3 text-mistral-ink border-l border-mistral-border hover:bg-mistral-band transition-colors duration-200"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
              {mobileOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="md:hidden border-t border-mistral-border bg-mistral-surface">
          {links.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="block px-4 py-3 font-display text-sm text-mistral-ink border-b border-mistral-border hover:bg-mistral-band transition-colors duration-200"
              onClick={() => setMobileOpen(false)}
            >
              {link.label}
            </a>
          ))}
          {!isAuthenticated && (
            <a
              href="/login"
              className="block px-4 py-3 font-display text-sm text-mistral-red-deep border-b border-mistral-border hover:bg-mistral-band transition-colors duration-200"
              onClick={() => setMobileOpen(false)}
            >
              Login
            </a>
          )}
        </div>
      )}
    </nav>
  );
};

const NavBar = () => (
  <AuthProvider>
    <NavContent />
  </AuthProvider>
);

export default NavBar;
