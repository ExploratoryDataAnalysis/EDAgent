import { useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import { ReleaseStatus, useReleaseRequest } from '../components/layout/ReleaseStatus';
import { count, DataTable, evidenceCard, EvidenceHeader, EvidenceIdentity, EvidenceSource, percent } from '../components/road-safety/EvidenceFigure';
import { apiClient } from '../services/apiClient';
import {
  confirmRelease, loadProvenance, overviewPath, pinnedArtifactPath, pinnedArtifactUrl, releaseTables,
  type Coordinates, type Provenance, type RoadSafetyError,
} from '../services/roadSafetyService';

type Cell = { lat_bin: number; lon_bin: number; mapped_crashes: number; years_observed: number };
type Ring = [number, number][];
type Bounds = Provenance['grid']['county_bbox_wsen'];
type Polygon = { type: 'Polygon'; coordinates: Ring[] } | { type: 'MultiPolygon'; coordinates: Ring[][] };
type Boundary = { type: 'Feature'; properties: { geoid: string }; geometry: Polygon };
const side = 0.001;
const half = side / 2;
// The ID stays at the precision of the frozen WGS 84 cell centres across zooms.
const cellId = (lon: number, lat: number) => `${lon.toFixed(3)}:${lat.toFixed(3)}`;
const bands = [
  { min: 1, label: '1–4', color: '#a1c9c1' },
  { min: 5, label: '5–19', color: '#418980' },
  { min: 20, label: '20–49', color: '#145d57' },
  { min: 50, label: '50+', color: '#27254e' },
];
const descendingBands = [...bands].reverse();
const bandFor = (n: number) => descendingBands.find(band => n >= band.min)!;
const pageSize = 10;

async function loadGrid(signal: AbortSignal) {
  const provenance = await loadProvenance(signal);
  const { table, caveats } = releaseTables(provenance, signal);
  const boundaryName = 'county_boundary.geojson';
  const [cells, coordinates, boundaryResponse] = await Promise.all([
    table<Cell>('historical_grid'),
    table<Coordinates>('coordinate_coverage'),
    apiClient.get<Boundary>(`${overviewPath}${pinnedArtifactPath(`/assets/${boundaryName}`, provenance)}`, { signal, timeout: 12000 })
      .catch((error: RoadSafetyError) => {
        if (error.status === 503 || signal.aborted) throw error;
        return null;
      }),
  ]);
  const mapped = coordinates.find(row => row.period_grain === 'county');
  const { grid, scope, bundle } = provenance;
  const byId = new Map(cells.map(cell => [cellId(cell.lon_bin, cell.lat_bin), cell]));
  if (!mapped || scope.geoid !== '42003' || grid.crs !== 'EPSG:4326' || grid.side_degrees !== side
    || byId.size !== cells.length || cells.length !== grid.occupied_cells
    || cells.some(cell => !Number.isSafeInteger(cell.mapped_crashes) || cell.mapped_crashes < 1
      || Number(cell.lat_bin.toFixed(3)) !== cell.lat_bin || Number(cell.lon_bin.toFixed(3)) !== cell.lon_bin)
    || cells.reduce((total, cell) => total + cell.mapped_crashes, 0) !== mapped.mapped_crashes
    || grid.reported_crashes !== mapped.reported_crashes || grid.mapped_crashes !== mapped.mapped_crashes
    || mapped.reported_crashes !== mapped.unusable_decimal_crashes + mapped.usable_decimal_crashes
    || mapped.usable_decimal_crashes !== mapped.outside_county_crashes + mapped.mapped_crashes
    || mapped.unusable_decimal_crashes !== mapped.missing_decimal_pair_crashes
      + mapped.invalid_decimal_pair_crashes + mapped.placeholder_decimal_pair_crashes) {
    throw new Error('The grid and coordinate coverage do not reconcile.');
  }

  let rings: Ring[] | null = null;
  if (boundaryResponse) {
    const { data, headers } = boundaryResponse;
    if (headers['x-manifest-sha256'] !== bundle.manifest_sha256 || headers['x-bundle-version'] !== bundle.version
      || headers['x-artifact-sha256'] !== provenance.outputs[boundaryName]
      || data.type !== 'Feature' || data.properties?.geoid !== scope.geoid) {
      throw new Error('The county boundary could not be verified.');
    }
    if (data.geometry?.type === 'Polygon') rings = data.geometry.coordinates;
    if (data.geometry?.type === 'MultiPolygon') rings = data.geometry.coordinates.flat();
  }
  await confirmRelease(provenance, signal);
  return { provenance, cells, mapped, byId, rings, caveats };
}

const confirmGrid = ({ provenance }: Awaited<ReturnType<typeof loadGrid>>, signal: AbortSignal) =>
  confirmRelease(provenance, signal);

function GridCanvas({ cells, rings, bounds, selected, onSelect, onFailure }: {
  cells: Cell[]; rings: Ring[]; bounds: Bounds; selected?: Cell;
  onSelect: (id: string) => void; onFailure: () => void;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const clip = useRef<Path2D>();
  const [west, south, east, north] = bounds;
  const width = 1000;
  const height = Math.round(width * (north - south) / (east - west) / Math.cos(40.45 * Math.PI / 180));

  useEffect(() => {
    try {
      const ctx = canvas.current?.getContext('2d');
      if (!ctx) throw new Error('Canvas is unavailable.');
      const x = (lon: number) => (lon - west) * width / (east - west);
      const y = (lat: number) => (north - lat) * height / (north - south);
      const boundary = new Path2D();
      for (const ring of rings) {
        ring.forEach(([lon, lat], index) => index === 0 ? boundary.moveTo(x(lon), y(lat)) : boundary.lineTo(x(lon), y(lat)));
        boundary.closePath();
      }
      clip.current = boundary;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#f1eee3';
      ctx.fill(boundary, 'evenodd');
      // Clip centred rectangles to the county polygon without generating new geometry.
      ctx.save();
      ctx.clip(boundary, 'evenodd');
      const cellWidth = side * width / (east - west);
      const cellHeight = side * height / (north - south);
      for (const cell of cells) {
        if (cell.lon_bin + half < west || cell.lon_bin - half > east
          || cell.lat_bin + half < south || cell.lat_bin - half > north) continue;
        ctx.fillStyle = bandFor(cell.mapped_crashes).color;
        ctx.fillRect(x(cell.lon_bin - half), y(cell.lat_bin + half), cellWidth, cellHeight);
      }
      ctx.restore();
      ctx.strokeStyle = '#505852';
      ctx.stroke(boundary);
    } catch {
      onFailure();
    }
  }, [cells, rings, west, south, east, north, height, onFailure]);

  function select(event: MouseEvent<HTMLCanvasElement>) {
    const target = event.currentTarget;
    const rect = target.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    if (clip.current && target.getContext('2d')?.isPointInPath(clip.current, x * width, y * height, 'evenodd')) {
      onSelect(cellId(west + x * (east - west), north - y * (north - south)));
    }
  }

  return <div className="relative overflow-hidden" aria-hidden="true">
    <canvas ref={canvas} width={width} height={height} onClick={select} className="block h-auto w-full cursor-crosshair bg-white" />
    {/* Keep selection separate from the full county paint. */}
    {selected && <span className="pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 border-2 border-[#a0381e]" style={{
      left: `${100 * (selected.lon_bin - west) / (east - west)}%`,
      top: `${100 * (north - selected.lat_bin) / (north - south)}%`,
      width: `max(14px, ${100 * side / (east - west)}%)`,
      height: `max(14px, ${100 * side / (north - south)}%)`,
    }} />}
  </div>;
}

export function CountyGridPage() {
  const { state, retry } = useReleaseRequest(loadGrid, confirmGrid);
  return <article className="public-document">
    <EvidenceHeader title="County crash grid">
      Each 0.001° × 0.001° cell shows a count of police-reported crashes mapped to that part of the county over the full 2004–2024 period.
      All reports in the fixed extract include crashes with unusable coordinates and crashes whose coordinates fall outside the county.
    </EvidenceHeader>
    {state.kind === 'ready' ? <GridFigure data={state.data} /> : <div className="public-measure"><ReleaseStatus kind={state.kind} retry={retry} /></div>}
  </article>;
}

function GridFigure({ data }: { data: Awaited<ReturnType<typeof loadGrid>> }) {
  const { cells, provenance, mapped, byId, rings, caveats } = data;
  const { grid } = provenance;
  const [selectedId, selectId] = useState('');
  const [page, setPage] = useState(0);
  const [failed, setFailed] = useState(!rings);
  const mapFailed = useCallback(() => setFailed(true), []);
  const [imageFailed, setImageFailed] = useState(false);
  const [zoom, setZoom] = useState<Bounds>();
  const selected = byId.get(selectedId);
  const bounds = zoom ?? grid.county_bbox_wsen;

  return <div className="space-y-5">
    <figure className={evidenceCard}>
      <h2>Where are mapped reports concentrated?</h2>
      <p><strong>{count(mapped.mapped_crashes)} of {count(mapped.reported_crashes)} reports ({percent(mapped.mapped_percent_of_reported)})</strong> map to {count(grid.occupied_cells)} occupied {grid.occupied_cells === 1 ? 'cell' : 'cells'}.</p>
      <p>{count(mapped.unusable_decimal_crashes)} reports have unusable coordinate pairs
        ({count(mapped.missing_decimal_pair_crashes)} missing, {count(mapped.invalid_decimal_pair_crashes)} invalid and {count(mapped.placeholder_decimal_pair_crashes)} placeholders).
        {' '}{count(mapped.outside_county_crashes)} of {count(mapped.usable_decimal_crashes)} usable pairs fall outside the county boundary.</p>
      <p className="text-sm">{caveats.GRID_CONCENTRATION} The grid uses WGS 84 coordinates and the Census boundary for GEOID 42003.</p>

      {!failed && rings ? <>
        <ul aria-label="Mapped reports per cell" className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {bands.map(({ label, color }) => <li key={label}><span aria-hidden="true" className="mr-2 inline-block size-3 border border-stone-500" style={{ background: color }} />{label} reports</li>)}
        </ul>
        <GridCanvas cells={cells} rings={rings} bounds={bounds} selected={selected} onSelect={selectId} onFailure={mapFailed} />
      </> : <div className="space-y-2">
        <p role="status">Interactive map unavailable. Use the cell table below to inspect counts.</p>
        {!imageFailed && <img className="h-auto w-full bg-white" onError={() => setImageFailed(true)}
          src={pinnedArtifactUrl('/assets/county_grid.svg', provenance)}
          alt="Approved reference map of reports per occupied cell on a logarithmic colour scale. Counts and coverage are available in the table." />}
      </div>}

      <section className="space-y-3" aria-labelledby="grid-cell-lookup">
        <h3 className="font-semibold" id="grid-cell-lookup">Inspect a cell</h3>
        <p className="text-sm">Choose a cell on the map, browse the table or enter a cell ID using longitude then latitude, for example {cells[0] && cellId(cells[0].lon_bin, cells[0].lat_bin)}.</p>
        <form className="flex flex-wrap items-end gap-2" onSubmit={event => {
          event.preventDefault();
          const id = String(new FormData(event.currentTarget).get('cell')).trim();
          selectId(id);
        }}>
          <label className="min-w-0 text-sm">Cell ID
            <input name="cell" required maxLength={24} className="block w-40 max-w-full rounded border border-stone-500 bg-white px-2 py-1" />
          </label>
          <button className="rounded border border-teal-800 px-3 py-1 text-sm text-teal-900">Find cell</button>
        </form>
        <p aria-live="polite" className="break-words text-sm">
          {selected ? `Cell ${selectedId} contains ${count(selected.mapped_crashes)} mapped reports (${bandFor(selected.mapped_crashes).label} reports band).`
            : selectedId ? `No occupied cell appears for ${selectedId}. Its count is unavailable.` : 'Choose an occupied cell to see its count.'}
        </p>
        {!failed && <div className="public-actions">
          <button className="disabled:text-stone-500 disabled:no-underline" type="button" disabled={!selected} onClick={() => {
            if (!selected) return;
            const { lon_bin: lon, lat_bin: lat } = selected;
            setZoom([lon - 0.015, lat - 0.01, lon + 0.015, lat + 0.01]);
          }}>Zoom to selected cell</button>
          <button className="disabled:text-stone-500 disabled:no-underline" type="button" disabled={!zoom} onClick={() => setZoom(undefined)}>Show whole county</button>
        </div>}
        {selected && <DataTable label="Selected grid cell" columns={['Cell ID', 'Mapped reports']}
          rows={[[selectedId, count(selected.mapped_crashes)]]} />}
        <details open={failed || undefined}>
          <summary className="cursor-pointer font-semibold">Occupied cell table</summary>
          <DataTable label="Occupied grid cells" columns={['Cell ID', 'Mapped reports']}
            rows={cells.slice(page * pageSize, (page + 1) * pageSize).map(cell => {
              const id = cellId(cell.lon_bin, cell.lat_bin);
              return [<button key={id} type="button" aria-pressed={selectedId === id} className="text-teal-900 underline" onClick={() => selectId(id)}>{id}</button>,
                count(cell.mapped_crashes)];
            })} />
          <div className="public-actions items-center">
            <button className="disabled:text-stone-500 disabled:no-underline" type="button" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous cells</button>
            <span aria-live="polite">Page {page + 1} of {Math.ceil(cells.length / pageSize)}</span>
            <button className="disabled:text-stone-500 disabled:no-underline" type="button" disabled={(page + 1) * pageSize >= cells.length} onClick={() => setPage(page + 1)}>Next cells</button>
          </div>
        </details>
      </section>
      <EvidenceSource provenance={provenance} tables={[[ 'historical_grid', 'All occupied cells' ], [ 'coordinate_coverage', 'Coordinate coverage' ]]} />
    </figure>
    <EvidenceIdentity provenance={provenance} />
  </div>;
}
