import React from 'react';

interface HeaderProps {
  currentView: 'form' | 'mentors';
  onViewChange: (view: 'form' | 'mentors') => void;
}

export const Header: React.FC<HeaderProps> = ({ currentView, onViewChange }) => {
  return (
    <header className="top-app-bar">
      <div className="top-app-bar-content">
        <div
          className="brand-section"
          onClick={() => onViewChange('form')}
          title="Return to Kudos submission"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') onViewChange('form');
          }}
        >
          <img 
            src="/logo.png" 
            alt="Up-A-Creek Robotics Otter Logo" 
            className="brand-logo"
          />
          <div className="brand-text">
            <h1>OtterThanks</h1>
            <span>Up-A-Creek Robotics</span>
          </div>
        </div>

        <div className="nav-actions">
          <div className="team-badge" title="FIRST Robotics Competition Team 1619">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
            </svg>
            <span>FRC 1619</span>
          </div>

          <button
            type="button"
            className={`nav-btn ${currentView === 'mentors' ? 'active' : ''}`}
            onClick={() => onViewChange(currentView === 'mentors' ? 'form' : 'mentors')}
            title="Mentors: Sign in and view database kudos"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" />
            </svg>
            <span>{currentView === 'mentors' ? 'Kudos Form' : 'Mentor Portal'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
