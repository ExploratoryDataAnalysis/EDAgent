
import { useEffect, useRef } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigationType } from 'react-router-dom';
import './public.css';

const titles: Record<string, string> = {
  '/': 'Allegheny County crash investigation',
  '/methods': 'Methods',
  '/road-safety': 'Road Safety Overview',
  '/illustrative-scenario': 'What-if calculator',
};

export function PublicLayout() {
  const { pathname, hash } = useLocation();
  const navigation = useNavigationType();
  const main = useRef<HTMLElement>(null);
  const previousPath = useRef<string>();
  const route = pathname.toLowerCase().replace(/\/$/, '') || '/';

  useEffect(() => {
    document.title = `${titles[route]} | EDAgent`;
    const changedPage = previousPath.current !== undefined && previousPath.current !== pathname;
    previousPath.current = pathname;
    const section = hash && document.getElementById(hash.slice(1));
    if (section) {
      section.focus({ preventScroll: true });
      section.scrollIntoView();
    } else if (changedPage) {
      main.current?.focus({ preventScroll: true });
      if (navigation !== 'POP') window.scrollTo(0, 0);
    }
    return () => { document.title = 'EDAgent'; };
  }, [route, pathname, hash, navigation]);

  return <div className="public-site">
    <a className="public-skip" href="#public-content">Skip to content</a>
    <header className="public-masthead">
      <div className="public-container">
        <Link to="/" className="public-brand">EDAgent</Link>
        <nav aria-label="Main navigation" className="public-nav">
          <Link to="/" aria-current={route === '/' || route === '/road-safety' ? 'page' : undefined}>Investigation</Link>
          <NavLink to="/methods">Methods</NavLink>
          <NavLink to="/illustrative-scenario">What-if calculator</NavLink>
          <NavLink to="/analyser">Dataset analyser</NavLink>
        </nav>
      </div>
    </header>
    <main id="public-content" ref={main} tabIndex={-1} className="public-container public-main">
      <Outlet />
    </main>
    <footer className="public-footer">
      <div className="public-container">Allegheny County, Pennsylvania · Historical crash investigation</div>
    </footer>
  </div>;
}
