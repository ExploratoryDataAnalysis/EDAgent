/// <reference types="vite/client" />

declare module 'plotly.js-dist-min' {
  import * as Plotly from 'plotly.js';
  export default Plotly;
}

declare module 'react-plotly.js/factory' {
  import * as React from 'react';
  import * as Plotly from 'plotly.js';

  export interface PlotParams {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    frames?: Plotly.Frame[];
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: Readonly<Plotly.Figure>, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: Readonly<Plotly.Figure>, graphDiv: HTMLElement) => void;
    onPurge?: (figure: Readonly<Plotly.Figure>, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
  }

  export default function createPlotlyComponent(plotly: unknown): React.ComponentClass<PlotParams>;
}
