// Small stroke icons, drawn here so the editor needs no network and no icon library. Decorative: aria-hidden.
const PATHS = {
  play: 'M7 5l11 7-11 7z',
  clock: 'M12 7v5l3 2M12 3a9 9 0 100 18 9 9 0 000-18z',
  repeat: 'M4 11V9a3 3 0 013-3h11l-3-3m3 3l-3 3M20 13v2a3 3 0 01-3 3H6l3 3m-3-3l3-3',
  branch: 'M6 4v8a4 4 0 004 4h2M6 4a1.5 1.5 0 100 .01M18 8a1.5 1.5 0 100 .01M18 8v1a3 3 0 01-3 3h-3M18 20a1.5 1.5 0 100 .01M12 16l2 4',
  merge: 'M6 4v4a4 4 0 004 4h4a4 4 0 014 4v4M18 4v4a4 4 0 01-4 4',
  stop: 'M7 7h10v10H7z',
  scale: 'M12 4v16M6 8h12M6 8l-3 7a3 3 0 006 0zM18 8l-3 7a3 3 0 006 0z',
  braces: 'M9 4C7 4 6 5 6 7v2c0 1.5-1 3-3 3 2 0 3 1.5 3 3v2c0 2 1 3 3 3M15 4c2 0 3 1 3 3v2c0 1.5 1 3 3 3-2 0-3 1.5-3 3v2c0 2-1 3-3 3',
  search: 'M11 4a7 7 0 100 14 7 7 0 000-14zM16 16l5 5',
  flask: 'M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  chat: 'M4 5h16v11H9l-5 4z',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12.5l4.5 4.5L19 7',
  trash: 'M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13',
  folder: 'M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z',
  layers: 'M12 3l9 5-9 5-9-5zM3 13l9 5 9-5',
  lock: 'M7 11V8a5 5 0 0110 0v3M6 11h12v9H6z',
  alert: 'M12 8v5M12 16.5v.01M10.3 4.3L3 17a2 2 0 001.7 3h14.6A2 2 0 0021 17L13.7 4.3a2 2 0 00-3.4 0z',
  pause: 'M9 6v12M15 6v12',
  half: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 3v18',
  xcircle: 'M12 3a9 9 0 100 18 9 9 0 000-18zM9 9l6 6M15 9l-6 6',
  checkcircle: 'M12 3a9 9 0 100 18 9 9 0 000-18zM8 12.5l3 3 5-6',
  eyeoff: 'M3 3l18 18M10.6 6.2A9.5 9.5 0 0112 6c5 0 8.5 4 9.5 6a12 12 0 01-2.6 3.3M6.3 7.7A12 12 0 002.5 12c1 2 4.5 6 9.5 6 1.4 0 2.6-.3 3.7-.8M9.9 9.9a3 3 0 004.2 4.2',
  help: 'M12 3a9 9 0 100 18 9 9 0 000-18zM9.5 9.5a2.5 2.5 0 114 2c-.9.6-1.5 1-1.5 2M12 17v.01',
  spinner: 'M12 3a9 9 0 019 9',
  arrow: 'M7 17L17 7M9 7h8v8',
  back: 'M10 6l-6 6 6 6M4 12h16',
  skip: 'M5 6l7 6-7 6zM13 6l7 6-7 6z',
}

export function Icon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={PATHS[name] ?? PATHS.braces} />
    </svg>
  )
}
