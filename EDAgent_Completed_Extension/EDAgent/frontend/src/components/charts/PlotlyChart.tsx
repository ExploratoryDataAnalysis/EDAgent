import React from 'react';
import type * as Plotly from 'plotly.js';
import createPlotlyComponent from 'react-plotly.js/factory';

let chartComponent: ReturnType<typeof createPlotlyComponent> | undefined;

export interface PlotlyChartProps {
  data: any[];
  layout?: any;
  config?: any;
  className?: string;
  style?: React.CSSProperties;
}

export const PlotlyChart: React.FC<PlotlyChartProps> = ({
  data,
  layout = {},
  config = {},
  className = 'w-full h-full min-h-[350px]',
  style = { width: '100%', height: '100%' },
}) => {
  const [Plot, setPlot] = React.useState(() => chartComponent);
  const [unavailable, setUnavailable] = React.useState(false);
  React.useEffect(() => {
    if (Plot) return;
    let active = true;
    // Routes with native charts or tables skip the Plotly payload.
    import('plotly.js-dist-min').then(({ default: plotly }) => {
      chartComponent ??= createPlotlyComponent(plotly);
      if (active) setPlot(() => chartComponent);
    }).catch(() => {
      if (active) setUnavailable(true);
    });
    return () => { active = false; };
  }, [Plot]);

  const mergedConfig: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d'],
    toImageButtonOptions: {
      format: 'png',
      filename: 'edagent_plot',
      height: 600,
      width: 900,
      scale: 2,
    },
    ...config,
  };

  const mergedLayout: Partial<Plotly.Layout> = {
    autosize: true,
    margin: { l: 50, r: 30, t: 40, b: 50 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: {
      family: 'Inter, system-ui, -apple-system, sans-serif',
      color: '#64748b',
    },
    hoverlabel: {
      font: { family: 'Inter, sans-serif' },
    },
    ...layout,
  };

  return (
    <div className={className}>
      {Plot ? <Plot
        data={data}
        layout={mergedLayout}
        config={mergedConfig}
        style={style}
        useResizeHandler
      /> : <p role="status">{unavailable ? 'Chart unavailable.' : 'Loading chart…'}</p>}
    </div>
  );
};

export default PlotlyChart;
