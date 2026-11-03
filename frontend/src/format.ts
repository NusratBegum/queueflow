const time = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Bangkok' });

export const clock = (iso: string | null) => (iso ? time.format(new Date(iso)) : '');

export function minutesSince(iso: string, now = Date.now()) {
  return Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
}

export const waitText = (minutes: number) =>
  minutes <= 1 ? 'about a minute' : minutes < 60 ? `about ${minutes} min` : `about ${Math.round(minutes / 6) / 10} h`;

export const pad = (n: number) => String(n).padStart(3, '0');
