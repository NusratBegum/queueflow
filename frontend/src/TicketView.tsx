import { useEffect, useRef, useState } from 'react';
import { api, ApiError, PublicTicket } from './api';
import { pad, waitText } from './format';
import { Logo } from './Staff';
import { usePoll } from './usePoll';

export default function TicketView({ token }: { token: string }) {
  const { data: t, error, refresh } = usePoll<PublicTicket>(() => api.ticket(token), 3000);
  const [problem, setProblem] = useState('');
  const lastStatus = useRef<string | null>(null);

  // Buzz the phone once when the customer is called.
  useEffect(() => {
    if (t?.status === 'called' && lastStatus.current === 'waiting') navigator.vibrate?.([200, 100, 200]);
    if (t) lastStatus.current = t.status;
  }, [t]);

  async function leave() {
    try {
      await api.leave(token);
      await refresh();
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : 'Could not reach the server');
    }
  }

  return (
    <main className="phone">
      <div className="brand"><Logo /> QueueFlow</div>
      {error && !t && <p className="error" role="alert">{error}</p>}
      {t && (
        <section className={`card ticket ticket-${t.status}`} aria-live="polite">
          <div className="muted">{t.queue_name}</div>
          <div className="muted small">Your number</div>
          <div className="big-num">{pad(t.number)}</div>
          {t.status === 'waiting' && (
            <>
              <p className="headline">
                {t.people_ahead === 0 ? "You're next" : `${t.people_ahead} ${t.people_ahead === 1 ? 'person' : 'people'} ahead of you`}
              </p>
              <p className="muted">Expected wait {waitText(t.estimated_wait_minutes)}. This page updates by itself.</p>
              <button onClick={leave}>Leave the queue</button>
            </>
          )}
          {t.status === 'called' && <p className="headline">It's your turn. Please go to {t.counter}.</p>}
          {t.status === 'served' && <p className="headline">All done. Thank you, {t.name}!</p>}
          {t.status === 'no_show' && <p className="headline">We called you but missed you. Please ask at the front desk.</p>}
          {t.status === 'cancelled' && (
            <>
              <p className="headline">You left the queue.</p>
              <a href={`#/q/${t.queue_slug}`}>Join again</a>
            </>
          )}
          {problem && <p className="error" role="alert">{problem}</p>}
        </section>
      )}
    </main>
  );
}
