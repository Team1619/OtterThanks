import React, { useState } from 'react';

interface KudosFormProps {
  onSuccess: () => void;
  onErrorToast: (msg: string) => void;
}

export const KudosForm: React.FC<KudosFormProps> = ({
  onSuccess,
  onErrorToast,
}) => {
  const [recipientType, setRecipientType] = useState<'team' | 'individual'>('individual');
  const [recipientName, setRecipientName] = useState('');
  const [message, setMessage] = useState('');
  const [senderName, setSenderName] = useState('');
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (recipientType === 'individual' && !recipientName.trim()) {
      newErrors.recipientName = 'Please enter who this kudos is for.';
    }

    if (!message.trim()) {
      newErrors.message = 'Please write your thank you message.';
    } else if (message.trim().length < 2) {
      newErrors.message = 'Message must be at least 2 characters.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleToggleAnonymous = () => {
    setIsAnonymous((prev) => !prev);
    if (!isAnonymous) {
      setSenderName('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) {
      return;
    }

    setSubmitting(true);
    setErrors({});

    try {
      const payload = {
        recipient_type: recipientType,
        recipient_name: recipientType === 'individual' ? recipientName.trim() : null,
        message: message.trim(),
        sender_name: isAnonymous || !senderName.trim() ? 'Anonymous' : senderName.trim(),
      };

      const response = await fetch('/api/kudos', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to submit kudos. Please try again.');
      }

      // Reset form
      setRecipientName('');
      setMessage('');
      setSenderName('');
      setIsAnonymous(false);
      setErrors({});

      onSuccess();
    } catch (err: any) {
      onErrorToast(err.message || 'Network error occurred.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="form-card" onSubmit={handleSubmit} noValidate>
      {/* 1. Recipient Selection */}
      <div className="form-group">
        <label className="group-label">Who are you thanking?</label>
        <div className="segmented-buttons" role="group" aria-label="Recipient selection">
          <button
            type="button"
            className={`segmented-btn ${recipientType === 'individual' ? 'active' : ''}`}
            onClick={() => {
              setRecipientType('individual');
              setErrors((prev) => ({ ...prev, recipientName: '' }));
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
            </svg>
            <span>A Person</span>
          </button>

          <button
            type="button"
            className={`segmented-btn ${recipientType === 'team' ? 'active' : ''}`}
            onClick={() => {
              setRecipientType('team');
              setErrors((prev) => ({ ...prev, recipientName: '' }));
            }}
          >
            <svg viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
            </svg>
            <span>The Whole Team</span>
          </button>
        </div>
      </div>

      {/* Recipient Name Field (conditional on individual) */}
      {recipientType === 'individual' && (
        <div className="form-group">
          <label htmlFor="recipientName" className="group-label">
            Recipient Name <span style={{ color: 'var(--md-sys-color-error)' }}>*</span>
          </label>
          <div className="text-field-container">
            <input
              id="recipientName"
              type="text"
              className={`text-field-input ${errors.recipientName ? 'has-error' : ''}`}
              placeholder="e.g. Mentor Bob, Emily (Build Lead), Drive Team..."
              value={recipientName}
              onChange={(e) => {
                setRecipientName(e.target.value);
                if (errors.recipientName) {
                  setErrors((prev) => ({ ...prev, recipientName: '' }));
                }
              }}
              disabled={submitting}
              autoFocus
            />
          </div>
          {errors.recipientName && (
            <div className="field-meta-row">
              <span className="field-error-text">{errors.recipientName}</span>
            </div>
          )}
        </div>
      )}

      {/* 2. Message Field */}
      <div className="form-group">
        <label htmlFor="message" className="group-label">
          Message <span style={{ color: 'var(--md-sys-color-error)' }}>*</span>
        </label>
        <div className="text-field-container">
          <textarea
            id="message"
            className={`text-field-input text-field-textarea ${errors.message ? 'has-error' : ''}`}
            placeholder="Write your note of appreciation here... What did they do that made an impact?"
            value={message}
            onChange={(e) => {
              setMessage(e.target.value);
              if (errors.message) {
                setErrors((prev) => ({ ...prev, message: '' }));
              }
            }}
            maxLength={2500}
            disabled={submitting}
          />
        </div>
        <div className="field-meta-row">
          {errors.message ? (
            <span className="field-error-text">{errors.message}</span>
          ) : (
            <span className="field-helper">Keep it supportive, specific, and enthusiastic!</span>
          )}
          <span className="char-counter">{message.length} / 2500</span>
        </div>
      </div>

      {/* 3. Signature Field */}
      <div className="form-group">
        <label htmlFor="senderName" className="group-label">
          Signed By
        </label>
        <div className="signature-row">
          <div className="signature-input-wrap">
            <input
              id="senderName"
              type="text"
              className="text-field-input"
              placeholder={isAnonymous ? 'Posting as Anonymous' : 'Your name or nickname...'}
              value={isAnonymous ? '' : senderName}
              onChange={(e) => setSenderName(e.target.value)}
              disabled={isAnonymous || submitting}
            />
          </div>
          <button
            type="button"
            className={`anon-chip ${isAnonymous ? 'active' : ''}`}
            onClick={handleToggleAnonymous}
            disabled={submitting}
            title="Send anonymously without your name"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
            </svg>
            <span>{isAnonymous ? 'Anonymous' : 'Stay Anonymous'}</span>
          </button>
        </div>
        <div className="field-meta-row">
          <span className="field-helper">
            {isAnonymous ? 'Your name will not be shown.' : 'Enter your name or click "Stay Anonymous".'}
          </span>
        </div>
      </div>

      {/* 4. Submit Button */}
      <div className="submit-btn-row">
        <button
          type="submit"
          className="btn-primary"
          disabled={submitting}
        >
          {submitting ? (
            <>
              <span className="spinner" aria-hidden="true" />
              <span>Submitting Kudos...</span>
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
              <span>Send Kudos</span>
            </>
          )}
        </button>
      </div>
    </form>
  );
};
