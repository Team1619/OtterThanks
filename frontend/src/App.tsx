import React, { useEffect, useState } from 'react';
import './App.css';
import { Header } from './components/Header';
import { KudosForm } from './components/KudosForm';
import { MentorDashboard } from './components/MentorDashboard';
import { Toast } from './components/Toast';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'form' | 'mentors'>(() => {
    return window.location.pathname.startsWith('/mentors') ? 'mentors' : 'form';
  });
  const [submitted, setSubmitted] = useState(false);
  const [toast, setToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info';
  } | null>(null);

  // Sync browser history
  useEffect(() => {
    const handlePopState = () => {
      setCurrentView(window.location.pathname.startsWith('/mentors') ? 'mentors' : 'form');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleViewChange = (view: 'form' | 'mentors') => {
    setCurrentView(view);
    const newPath = view === 'mentors' ? '/mentors' : '/';
    if (window.location.pathname !== newPath) {
      window.history.pushState({}, '', newPath);
    }
  };

  const handleSuccess = () => {
    setSubmitted(true);
    setToast({
      message: 'Kudos submitted successfully! It will appear in Slack soon.',
      type: 'success',
    });
  };

  const handleErrorToast = (msg: string) => {
    setToast({
      message: msg,
      type: 'error',
    });
  };

  const showToast = (message: string, type: 'success' | 'error' | 'info' = 'info') => {
    setToast({ message, type });
  };

  return (
    <div className="app-container">
      <Header currentView={currentView} onViewChange={handleViewChange} />

      <main className={`main-content ${currentView === 'mentors' ? 'wide' : ''}`}>
        {currentView === 'mentors' ? (
          <MentorDashboard
            onBackToForm={() => handleViewChange('form')}
            onToast={showToast}
          />
        ) : (
          <>
            <div className="hero-card">
              <h2 className="hero-title">Spread the Appreciation 🦦</h2>
              <p className="hero-subtitle">
                Say thank you to a hardworking teammate, an inspiring mentor, or celebrate the whole team!
              </p>
            </div>

            {submitted ? (
              <div className="form-card success-card">
                <div className="success-icon-badge">
                  <svg viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                  </svg>
                </div>
                <h3 className="success-title">Thank You!</h3>
                <p className="success-message">
                  Your message of appreciation has been delivered!
                </p>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setSubmitted(false)}
                >
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                    <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
                  </svg>
                  <span>Send Another Kudos</span>
                </button>
              </div>
            ) : (
              <KudosForm
                onSuccess={handleSuccess}
                onErrorToast={handleErrorToast}
              />
            )}
          </>
        )}
      </main>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}

      <footer className="app-footer">
        <p>Built with ❤️ for Up-A-Creek Robotics (FRC Team 1619)</p>
      </footer>
    </div>
  );
};

export default App;
