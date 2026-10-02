import React, { useEffect, useState } from 'react';

interface KudosItem {
  id: number;
  recipient_type: string;
  recipient_name: string | null;
  message: string;
  sender_name: string;
  slack_status: string;
  slack_sent_at: string | null;
  created_at: string;
}

interface MentorStats {
  total: number;
  pending_count: number;
  sent_count: number;
  failed_count: number;
  items: KudosItem[];
}

interface UserProfile {
  authenticated: boolean;
  email?: string;
  name?: string;
  picture?: string;
  role?: string;
}

interface AuthConfig {
  configured: boolean;
  allowed_group?: string | null;
  dev_mode: boolean;
}

interface MentorDashboardProps {
  onBackToForm: () => void;
  onToast: (msg: string, type?: 'success' | 'error' | 'info') => void;
}

export const MentorDashboard: React.FC<MentorDashboardProps> = ({
  onBackToForm,
  onToast,
}) => {
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [loginError, setLoginError] = useState<string | null>(null);

  // Kudos Dashboard State
  const [kudosData, setKudosData] = useState<MentorStats>({
    total: 0,
    pending_count: 0,
    sent_count: 0,
    failed_count: 0,
    items: [],
  });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [fetchingKudos, setFetchingKudos] = useState(false);
  const [releasingId, setReleasingId] = useState<number | null>(null);

  // Read URL query errors (e.g. from Google OAuth callback)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const err = params.get('error');
    if (err) {
      setLoginError(decodeURIComponent(err));
      // Clean up URL without reload
      window.history.replaceState({}, '', '/mentors');
    }
  }, []);

  // Fetch Auth Config and Current User
  const checkAuth = async () => {
    try {
      const [configRes, meRes] = await Promise.all([
        fetch('/api/auth/config'),
        fetch('/api/auth/me'),
      ]);
      if (configRes.ok) {
        setAuthConfig(await configRes.json());
      }
      if (meRes.ok) {
        const userData: UserProfile = await meRes.json();
        setUser(userData);
        if (userData.authenticated) {
          fetchKudos();
        }
      }
    } catch (e) {
      console.error('Failed to load auth state', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkAuth();
  }, []);

  // Fetch Kudos List for Mentors
  const fetchKudos = async (status = statusFilter, search = searchQuery) => {
    setFetchingKudos(true);
    try {
      const params = new URLSearchParams();
      if (status && status !== 'all') {
        params.set('status', status);
      }
      if (search && search.trim()) {
        params.set('search', search.trim());
      }
      const res = await fetch(`/api/mentor/kudos?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setKudosData(data);
      } else if (res.status === 401) {
        setUser({ authenticated: false });
      }
    } catch (err) {
      onToast('Error loading kudos entries.', 'error');
    } finally {
      setFetchingKudos(false);
    }
  };

  const handleFilterChange = (newStatus: string) => {
    setStatusFilter(newStatus);
    fetchKudos(newStatus, searchQuery);
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setSearchQuery(val);
    fetchKudos(statusFilter, val);
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser({ authenticated: false });
      onToast('Logged out successfully.', 'info');
    } catch {
      onToast('Error logging out.', 'error');
    }
  };

  const handleDevLogin = async () => {
    try {
      const res = await fetch('/api/auth/dev-login', { method: 'POST' });
      if (res.ok) {
        onToast('Signed in with Dev Mentor Account!', 'success');
        checkAuth();
      } else {
        const err = await res.json();
        onToast(err.detail || 'Dev login failed', 'error');
      }
    } catch {
      onToast('Dev login request failed', 'error');
    }
  };

  const handleReleaseToSlack = async (item: KudosItem) => {
    setReleasingId(item.id);
    try {
      const res = await fetch(`/api/mentor/kudos/${item.id}/release`, {
        method: 'POST',
      });
      if (res.ok) {
        onToast(`Kudos #${item.id} successfully released to Slack!`, 'success');
        fetchKudos();
      } else {
        const errorData = await res.json().catch(() => ({}));
        onToast(errorData.detail || 'Failed to release kudos to Slack.', 'error');
      }
    } catch {
      onToast('Network error releasing kudos to Slack.', 'error');
    } finally {
      setReleasingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm(`Are you sure you want to delete kudos #${id}?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/mentor/kudos/${id}`, { method: 'DELETE' });
      if (res.ok) {
        onToast(`Kudos #${id} deleted.`, 'info');
        fetchKudos();
      } else {
        onToast('Failed to delete kudos.', 'error');
      }
    } catch {
      onToast('Network error deleting kudos.', 'error');
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem' }}>
        <div className="spinner" style={{ margin: '0 auto 1rem', borderColor: 'var(--md-sys-color-primary)' }} />
        <p style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Loading Mentor Portal...</p>
      </div>
    );
  }

  // View 1: Not Logged In
  if (!user || !user.authenticated) {
    return (
      <div className="form-card mentor-login-card">
        <div className="mentor-portal-icon">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="currentColor">
            <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" />
          </svg>
        </div>

        <h2 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>
          Mentor Portal
        </h2>
        <p style={{ color: 'var(--md-sys-color-on-surface-variant)', fontSize: '0.95rem', marginBottom: '1.5rem' }}>
          Sign in with your Up-A-Creek Robotics Google Workspace account to review and manage submitted kudos.
        </p>

        {loginError && (
          <div className="alert-banner" role="alert">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z" />
            </svg>
            <span>{loginError}</span>
          </div>
        )}

        <div className="group-notice">
          <strong>Authorized Google Group:</strong>{' '}
          <code>{authConfig?.allowed_group || 'Configured via ALLOWED_GOOGLE_GROUP in .env'}</code>
        </div>

        <a href="/api/auth/login" className="google-btn">
          <svg className="google-icon-svg" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.8-2.4 3.66v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.15z"
            />
            <path
              fill="#34A853"
              d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.24v3.15C3.26 21.36 7.33 24 12 24z"
            />
            <path
              fill="#FBBC05"
              d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.24C.45 8.16 0 9.96 0 12s.45 3.84 1.24 5.42l4.04-3.15z"
            />
            <path
              fill="#EA4335"
              d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.24 6.58l4.04 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
            />
          </svg>
          <span>Sign in with Google Workspace</span>
        </a>

        {/* Development Quick-Login for local testing without OAuth secrets */}
        {authConfig?.dev_mode && (
          <div className="dev-login-box">
            <p style={{ fontSize: '0.8rem', color: 'var(--md-sys-color-outline)', marginBottom: '0.75rem' }}>
              🔧 Development Mode Active (Google OAuth not configured or DEV_MODE=true)
            </p>
            <button
              type="button"
              className="dev-login-btn"
              onClick={handleDevLogin}
            >
              <span>Quick Login as Mock Mentor</span>
            </button>
          </div>
        )}

        <div style={{ marginTop: '1.5rem' }}>
          <button
            type="button"
            className="btn-secondary"
            onClick={onBackToForm}
            style={{ fontSize: '0.85rem', padding: '0.5rem 1rem' }}
          >
            ← Back to Kudos Form
          </button>
        </div>
      </div>
    );
  }

  // View 2: Authenticated Mentor Dashboard
  return (
    <div>
      {/* Dashboard Top Row */}
      <div className="dashboard-top-bar">
        <div className="dashboard-title-group">
          <h2>Mentor Kudos Dashboard</h2>
          <p>
            Signed in as <strong>{user.name}</strong> ({user.email})
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button
            type="button"
            className="nav-btn"
            onClick={onBackToForm}
            title="Go to student submission page"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
            </svg>
            <span>Kudos Form</span>
          </button>

          <button
            type="button"
            className="nav-btn"
            onClick={handleLogout}
            title="Sign out of Mentor Portal"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z" />
            </svg>
            <span>Sign Out</span>
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-number">{kudosData.total}</div>
          <div className="stat-label">Total Submissions</div>
        </div>

        <div className="stat-card stat-pending">
          <div className="stat-number">{kudosData.pending_count}</div>
          <div className="stat-label">Pending for Slack</div>
        </div>

        <div className="stat-card stat-sent">
          <div className="stat-number">{kudosData.sent_count}</div>
          <div className="stat-label">Delivered to Slack</div>
        </div>
      </div>

      {/* Controls & Filters */}
      <div className="dashboard-controls">
        <div className="search-box">
          <svg className="search-icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z" />
          </svg>
          <input
            type="text"
            className="search-input"
            placeholder="Search recipient, sender, or message..."
            value={searchQuery}
            onChange={handleSearchChange}
          />
        </div>

        <div className="filter-chips">
          <button
            type="button"
            className={`chip-filter ${statusFilter === 'all' ? 'active' : ''}`}
            onClick={() => handleFilterChange('all')}
          >
            All ({kudosData.total})
          </button>
          <button
            type="button"
            className={`chip-filter ${statusFilter === 'pending' ? 'active' : ''}`}
            onClick={() => handleFilterChange('pending')}
          >
            Pending ({kudosData.pending_count})
          </button>
          <button
            type="button"
            className={`chip-filter ${statusFilter === 'sent' ? 'active' : ''}`}
            onClick={() => handleFilterChange('sent')}
          >
            Sent ({kudosData.sent_count})
          </button>
        </div>
      </div>

      {/* Kudos List */}
      {fetchingKudos ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem', borderColor: 'var(--md-sys-color-primary)' }} />
          <p style={{ color: 'var(--md-sys-color-on-surface-variant)' }}>Updating kudos...</p>
        </div>
      ) : kudosData.items.length === 0 ? (
        <div className="form-card empty-state">
          <svg className="empty-state-icon" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V5h14v14z" />
          </svg>
          <p style={{ fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.25rem' }}>
            No kudos found
          </p>
          <p style={{ fontSize: '0.875rem' }}>
            {searchQuery || statusFilter !== 'all'
              ? 'Try adjusting your search or filters.'
              : 'Submissions will appear here once students or mentors share kudos!'}
          </p>
        </div>
      ) : (
        <div className="kudos-list">
          {kudosData.items.map((item) => (
            <div key={item.id} className="kudos-item-card">
              <div className="kudos-card-header">
                <span className={`kudos-recipient-badge ${item.recipient_type}`}>
                  {item.recipient_type === 'team' ? (
                    <>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                        <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
                      </svg>
                      <span>The Whole Team</span>
                    </>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                      </svg>
                      <span>To: {item.recipient_name}</span>
                    </>
                  )}
                </span>

                <span className="kudos-meta">
                  Submitted {formatDate(item.created_at)}
                </span>
              </div>

              <div className="kudos-card-message">{item.message}</div>

              <div className="kudos-card-footer">
                <div className="kudos-sender">
                  Signed by: <strong>{item.sender_name}</strong>
                </div>

                <div className="kudos-card-actions">
                  <span
                    className={`status-badge ${item.slack_status}`}
                    title={
                      item.slack_sent_at
                        ? `Posted to Slack at ${formatDate(item.slack_sent_at)}`
                        : 'Waiting for Slack microservice'
                    }
                  >
                    ● {item.slack_status}
                  </span>

                  <button
                    type="button"
                    className={`action-btn-release ${item.slack_status === 'sent' ? 'is-sent' : ''}`}
                    onClick={() => handleReleaseToSlack(item)}
                    disabled={releasingId === item.id}
                    title="Release to Slack"
                    aria-label="Release to Slack"
                  >
                    {releasingId === item.id ? (
                      <span className="spinner-small" aria-hidden="true" />
                    ) : item.slack_status === 'sent' ? (
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M19 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.11 0 2-.9 2-2V5c0-1.1-.89-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                        <path d="M19 5v14H5V5h14m0-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z" />
                      </svg>
                    )}
                    <span>{item.slack_status === 'sent' ? 'Released to Slack' : 'Release to Slack'}</span>
                  </button>

                  <button
                    type="button"
                    className="action-icon-btn btn-delete"
                    onClick={() => handleDelete(item.id)}
                    title="Delete Kudos"
                  >
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                      <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
