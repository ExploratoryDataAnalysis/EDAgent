import { Link } from 'react-router-dom';

const projectDocs = 'https://github.com/ExploratoryDataAnalysis/EDAgent/blob/87a7aea1d10300151bafa33a21a1735d4a011e29/docs';

export function MethodsPage() {
  return <article className="public-document public-measure">
    <header className="public-hero">
      <p className="public-kicker">Allegheny County, Pennsylvania · 2004–2024</p>
      <h1>Methods</h1>
      <p className="public-lede">How police-reported crashes enter the record, how coverage changes across years, and what comparisons the data support.</p>
      <nav className="public-actions" aria-label="On this page">
        <Link to="#inclusion">Inclusion</Link>
        <Link to="#coding">Coding and coverage</Link>
        <Link to="#mapping">Mapping</Link>
        <Link to="#interpretation">Interpretation</Link>
        <Link to="#sources">Sources and citation</Link>
      </nav>
    </header>

    <section className="public-section" aria-labelledby="inclusion">
      <h2 id="inclusion" tabIndex={-1}>Which reports are included?</h2>
      <p>The record uses the Western Pennsylvania Regional Data Center’s fixed cumulative Allegheny County extract of police-reported crashes from 2004 through 2024. Each unique crash report number contributes one crash, even if multiple people or vehicles were involved. County totals keep reports with unknown severity or unusable coordinates. The separately published 2025 resource is outside the fixed record.</p>
    </section>

    <section className="public-section" aria-labelledby="coding">
      <h2 id="coding" tabIndex={-1}>Coding changes and missing fields</h2>
      <p>PennDOT adopted the federal injury-severity standard on 1 January 2016. The record separates 2004–2015 from 2016–2024 when comparing injury categories. Combined serious or fatal counts and shares use the later period. Known severity uses codes 0–4. Severity shares specify whether they use known-severity reports or all reports, with unknown, blank and unrecognised values tracked separately.</p>
      <p>A valid hour is in the range 0–23. A populated illumination field may still carry an unknown code. Hour and lighting coverage is too sparse in 2024 for full-year comparisons. Exact crash dates are withheld in the public extract. Historical weather and road-surface code mappings still require verification.</p>
    </section>

    <section className="public-section" aria-labelledby="mapping">
      <h2 id="mapping" tabIndex={-1}>Why the map covers fewer reports</h2>
      <p>Mapping uses the source’s decimal coordinate pair. Both values must pass the format and plausibility checks, clear the placeholder screen and fall inside or on the 2024 Census county boundary. The format of the police-text coordinates remains unverified, so mapping excludes those fields. Mapping coverage divides mapped reports by all reports in the same period. A map cell counts only reports that passed the mapping rules.</p>
    </section>

    <section className="public-section" aria-labelledby="interpretation">
      <h2 id="interpretation" tabIndex={-1}>What the evidence supports</h2>
      <p>Once reviewed and released, the aggregates can describe reported crash counts, recording coverage, and the concentration of mapped reports. The severity association tests cover known-severity reports from 2016–2023 and describe relationships within that population. They cannot establish why a crash happened.</p>
      <p>The extract contains no measure of travel exposure, such as vehicle miles travelled, and the investigation has no validated assignment of crashes to individual road sites. The record cannot estimate exposure-adjusted site risk, rank routes, forecast crashes, or predict the effect of a real treatment.</p>
    </section>

    <section className="public-section" aria-labelledby="sources">
      <h2 id="sources" tabIndex={-1}>Sources, reproduction and citation</h2>
      <p className="public-actions">
        <a href="https://data.wprdc.org/dataset/allegheny-county-crash-data/resource/2c13021f-74a9-4289-a1e5-fe0472c89881">WPRDC cumulative crash resource</a>
        <a href="https://crashinfo.penndot.pa.gov/PCIT/">PennDOT coding notice</a>
        <a href={`${projectDocs}/sources_and_decisions.md`}>Frozen source and decision notes</a>
        <a href={`${projectDocs}/v6_reproduction_inventory.md`}>Reproduction inventory</a>
      </p>
      <p>The frozen v6 analysis run was recorded on 11 November 2026. Its reproduction inventory records the input checksum, notebook revision and commands. When citing a released result, include the publisher, cumulative resource, years, fixed extract and run, figure or complete table row key, and the approved bundle version. The crash record carries release identifiers and source checksums when the files pass verification.</p>
      <p><Link to="/road-safety">Open the crash record</Link></p>
    </section>
  </article>;
}
