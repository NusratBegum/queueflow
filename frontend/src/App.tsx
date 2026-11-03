import { useEffect, useState } from 'react';
import Staff from './Staff';
import Join from './Join';
import TicketView from './TicketView';
import Display from './Display';

function useHash() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return hash;
}

export default function App() {
  const [, kind, id] = useHash().replace(/^#\/?/, '/').split('/');
  if (kind === 'q' && id) return <Join slug={decodeURIComponent(id)} />;
  if (kind === 't' && id) return <TicketView token={decodeURIComponent(id)} />;
  if (kind === 'display' && id) return <Display slug={decodeURIComponent(id)} />;
  return <Staff />;
}
