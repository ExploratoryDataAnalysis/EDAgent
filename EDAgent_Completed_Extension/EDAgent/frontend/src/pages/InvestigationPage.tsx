import { Link } from 'react-router-dom';
import { ReleaseStatus, useReleaseRequest } from '../components/layout/ReleaseStatus';
import { loadProvenance } from '../services/roadSafetyService';

export function InvestigationPage() {
  const { state, retry } = useReleaseRequest(loadProvenance);
  return <article className="public-document">
    <header className="public-hero public-measure">
      <p className="public-kicker">Allegheny County, Pennsylvania · 2004–2024</p>
      <h1>What can Allegheny County’s crash reports tell us?</h1>
      <p className="public-lede">A historical investigation of police-reported crashes and what the county record can show about when and where they were recorded.</p>
    </header>
    <div className="public-measure">
      {state.kind === 'ready' && state.data.bundle.version.startsWith('fixture-') &&
        <p>Synthetic test fixture. Counts are invented for verification.</p>}
      <ReleaseStatus kind={state.kind} retry={retry} recordLink />
    </div>
    <section className="public-section" aria-labelledby="assembled">
      <h2 id="assembled">How the record was assembled</h2>
      <p className="public-measure">The investigation uses a fixed county extract. The full record and the mapped subset answer different questions, and changes in reporting affect comparisons over time.</p>
      <div className="public-topics">
        <div>
          <h3><Link to="/methods#inclusion">Which reports count</Link></h3>
          <p>County totals count each crash report once, including reports without usable coordinates.</p>
        </div>
        <div>
          <h3><Link to="/methods#coding">Why 2016 matters</Link></h3>
          <p>PennDOT changed the injury-severity standard. Comparisons of injury categories use separate coding periods.</p>
        </div>
        <div>
          <h3><Link to="/methods#mapping">Which reports can be mapped</Link></h3>
          <p>Location fields can be missing or unusable. Mapped reports pass a coordinate check against the county boundary.</p>
        </div>
      </div>
    </section>
    <section className="public-section" aria-labelledby="tools">
      <h2 id="tools">Explore with your own inputs</h2>
      <p className="public-measure">Use the <Link to="/illustrative-scenario">What-if calculator</Link> to test an invented baseline and crash modification factor. Sign in to the <Link to="/analyser">Dataset analyser</Link> to upload, analyse and export your own data.</p>
    </section>
  </article>;
}
