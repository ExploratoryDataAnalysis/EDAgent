import React from 'react';
import Plotly from 'plotly.js-dist-min';
import createPlotlyComponent from 'react-plotly.js/factory';

// Create pure React-Plotly component instance from lightweight distribution bundle
const Plot = createPlotlyComponent(Plotly);

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
      <Plot
        data={data}
        layout={mergedLayout}
        config={mergedConfig}
        style={style}
        useResizeHandler
      />
    </div>
  );
};

export default PlotlyChart;
