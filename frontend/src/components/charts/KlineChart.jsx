import { useEffect, useRef, useState, useCallback } from 'react';
import { init, dispose } from 'klinecharts';
import './KlineChart.css';

export function KlineChart({ data = [], height = 500, ticker = 'AAPL', isIntraday = false }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  // Active technical indicator toggles
  const [indicators, setIndicators] = useState({
    MA: false,
    BOLL: false,
    MACD: false,
    RSI: false,
    KDJ: false,
  });

  const [hoveredData, setHoveredData] = useState(null);

  // Helper to re-apply active indicators
  const applyIndicators = useCallback((chart, currentIndicators) => {
    Object.entries(currentIndicators).forEach(([name, isActive]) => {
      if (isActive) {
        try {
          if (name === 'MA' || name === 'BOLL') {
            chart.createIndicator({ name, paneId: 'candle_pane' }, true);
          } else {
            chart.createIndicator({ name }, true);
          }
        } catch (e) {
          console.error(`Error creating indicator ${name}:`, e);
        }
      }
    });
  }, []);

  // Safe Indicator Toggle Handler
  const toggleIndicator = (name) => {
    if (!chartRef.current) return;

    try {
      const isCurrentlyActive = indicators[name];

      if (!isCurrentlyActive) {
        if (name === 'MA' || name === 'BOLL') {
          chartRef.current.createIndicator({ name, paneId: 'candle_pane' });
        } else {
          chartRef.current.createIndicator({ name });
        }
        setIndicators((prev) => ({ ...prev, [name]: true }));
      } else {
        const allIndicators = chartRef.current.getIndicators() || [];
        allIndicators.forEach((ind) => {
          if (ind.name === name) {
            chartRef.current.removeIndicator(ind.paneId || 'candle_pane', ind.instanceId);
          }
        });
        setIndicators((prev) => ({ ...prev, [name]: false }));
      }
    } catch (e) {
      console.error(`Error toggling indicator ${name}:`, e);
    }
  };

  // Helper to format raw data for KLineChart
  const formatKlineData = (rawData) => {
    if (!rawData || rawData.length === 0) return [];

    return rawData.map((d) => {
      let ts = d.timestamp;

      // Handle seconds vs milliseconds conversion if needed
      if (ts && ts < 10000000000) {
        ts = ts * 1000;
      }

      if (!ts && d.label) {
        const parsed = new Date(d.label).getTime();
        ts = !isNaN(parsed) ? parsed : Date.now();
      }

      return {
        timestamp: ts || Date.now(),
        open: d.open ?? 0,
        high: d.high ?? 0,
        low: d.low ?? 0,
        close: d.close ?? 0,
        volume: d.volume ?? 0,
        turnover: (d.close && d.volume) ? (d.close * d.volume) : 0,
      };
    });
  };

  // Chart Initialization Lifecycle
  useEffect(() => {
    if (!containerRef.current) return;

    // Cleanup previous chart instance
    if (chartRef.current) {
      try {
        dispose(containerRef.current);
      } catch (e) {
        console.error('Error disposing chart:', e);
      }
      chartRef.current = null;
    }

    try {
      const chart = init(containerRef.current);
      chartRef.current = chart;

      chart.setSymbol({
        ticker,
        pricePrecision: 3,
        volumePrecision: 0,
      });

      chart.setPeriod({
        span: 1,
        type: isIntraday ? 'minute' : 'day',
      });

      // Styling
      chart.setStyles({
        candle: {
          upColor: '#51a958',
          downColor: '#ea3d3d',
          upBorderColor: '#51a958',
          downBorderColor: '#ea3d3d',
          upWickColor: '#51a958',
          downWickColor: '#ea3d3d',
        },
        grid: {
          show: true,
          horizontal: { color: 'rgba(70, 70, 70, 0.5)', style: 'dashed', size: 1 },
          vertical: { color: 'rgba(70, 70, 70, 0.5)', style: 'dashed', size: 1 },
        },
        xAxis: {
          axisLine: { color: 'rgba(100, 100, 100, 0.6)', size: 1 },
          tickLine: { color: 'rgba(100, 100, 100, 0.4)', size: 1, length: 3 },
          tickText: {
            color: '#a8a8a8',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 14,
            weight: '600',
          },
          title: { show: false },
        },
        yAxis: {
          axisLine: { color: 'rgba(100, 100, 100, 0.6)', size: 1 },
          tickLine: { color: 'rgba(100, 100, 100, 0.4)', size: 1, length: 3 },
          tickText: {
            color: '#a8a8a8',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 14,
            weight: '600',
          },
          title: { show: false },
        },
        background: { color: 'rgba(20, 20, 18, 0.7)' },
        tooltip: {
          text: {
            color: '#f5f5f5',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 14,
            weight: '600',
          },
          backgroundColor: 'rgba(15, 15, 14, 0.98)',
          borderColor: 'rgba(100, 100, 100, 0.6)',
        },
        crosshair: {
          show: true,
          horizontal: {
            show: true,
            line: { color: 'rgba(200, 200, 200, 0.3)', style: 'solid', size: 1 },
            text: {
              backgroundColor: 'rgba(70, 70, 70, 0.8)',
              borderRadius: 2,
              borderColor: 'rgba(70, 70, 70, 0.8)',
              color: '#d4d4d8',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              size: 13,
              weight: '600',
              paddingLeft: 4,
              paddingRight: 4,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
          vertical: {
            show: true,
            line: { color: 'rgba(200, 200, 200, 0.3)', style: 'solid', size: 1 },
            text: {
              backgroundColor: 'rgba(70, 70, 70, 0.8)',
              borderRadius: 2,
              borderColor: 'rgba(70, 70, 70, 0.8)',
              color: '#d4d4d8',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              size: 13,
              weight: '600',
              paddingLeft: 4,
              paddingRight: 4,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
        },
      });

      // Load initial dataset using DataLoader
      const formattedData = formatKlineData(data);
      chart.setDataLoader({
        getBars: ({ callback }) => {
          callback(formattedData);
        },
        subscribeBar: () => {},
        unsubscribeBar: () => {},
      });

      // Re-apply currently active indicators
      applyIndicators(chart, indicators);

      // Subscribe to Crosshair Movement with exact raw timestamp extraction
      chart.subscribeAction('onCrosshairChange', (crosshairData) => {
        if (crosshairData && typeof crosshairData.dataIndex === 'number') {
          const dataList = chart.getDataList() || [];
          if (crosshairData.dataIndex >= 0 && crosshairData.dataIndex < dataList.length) {
            const kline = dataList[crosshairData.dataIndex];

            // Preserve exact original string from props without timezone conversion
            const rawItem = data[crosshairData.dataIndex];
            const rawTimeString = rawItem?.label || rawItem?.time || rawItem?.timestamp || '';

            setHoveredData({
              timestamp: String(rawTimeString),
              open: kline.open?.toFixed(3) || '0.000',
              high: kline.high?.toFixed(3) || '0.000',
              low: kline.low?.toFixed(3) || '0.000',
              close: kline.close?.toFixed(3) || '0.000',
              volume: kline.volume?.toLocaleString?.() || '0',
            });
          }
        }
      });

      const handleResize = () => {
        if (chartRef.current) {
          try {
            chartRef.current.resize();
          } catch (e) {
            console.error('Error resizing chart:', e);
          }
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          try {
            dispose(containerRef.current);
          } catch (e) {
            console.error('Error cleaning up chart:', e);
          }
          chartRef.current = null;
        }
      };
    } catch (e) {
      console.error('Error initializing KLineChart:', e);
    }
  }, [ticker, isIntraday]);

  // Update Data smoothly without re-initializing canvas
  useEffect(() => {
    if (chartRef.current && data && data.length > 0) {
      const formattedData = formatKlineData(data);
      chartRef.current.setDataLoader({
        getBars: ({ callback }) => {
          callback(formattedData);
        },
        subscribeBar: () => {},
        unsubscribeBar: () => {},
      });
    }
  }, [data]);

  return (
    <div className="kline-wrapper">
      {hoveredData && (
        <div className="kline-data-display">
          <div className="data-row">
            <div className="data-item">
              <span className="data-label">Time</span>
              <span className="data-value">{hoveredData.timestamp}</span>
            </div>
            <div className="data-item">
              <span className="data-label">Open</span>
              <span className="data-value">{hoveredData.open}</span>
            </div>
            <div className="data-item">
              <span className="data-label">High</span>
              <span className="data-value">{hoveredData.high}</span>
            </div>
            <div className="data-item">
              <span className="data-label">Low</span>
              <span className="data-value">{hoveredData.low}</span>
            </div>
            <div className="data-item">
              <span className="data-label">Close</span>
              <span className="data-value">{hoveredData.close}</span>
            </div>
            <div className="data-item">
              <span className="data-label">Volume</span>
              <span className="data-value">{hoveredData.volume}</span>
            </div>
          </div>
        </div>
      )}

      <div className="kline-controls">
        {Object.keys(indicators).map((name) => (
          <button
            key={name}
            className={`indicator-btn ${indicators[name] ? 'active' : ''}`}
            onClick={() => toggleIndicator(name)}
            type="button"
          >
            {name}
          </button>
        ))}
      </div>

      <div
        ref={containerRef}
        className="kline-container"
        style={{ height: `${height}px` }}
      />
    </div>
  );
}