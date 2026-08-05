import { useEffect, useRef, useState, useCallback } from 'react';
import { init, dispose } from 'klinecharts';
import './KlineChart.css';

export function KlineChart({ data = [], height = 500, ticker = 'AAPL', isIntraday = false }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);

  // Active technical indicator toggles
  const [indicators, setIndicators] = useState({
    MA: true,
    BOLL: false,
    MACD: false,
    RSI: false,
    KDJ: false,
  });

  const [hoveredData, setHoveredData] = useState(null);

  // Helper to re-apply active indicators when the chart instance re-initializes
  const applyIndicators = useCallback((chart, currentIndicators) => {
    Object.entries(currentIndicators).forEach(([name, isActive]) => {
      if (isActive) {
        try {
          if (name === 'MA' || name === 'BOLL') {
            // Overlay indicators on main candle pane
            chart.createIndicator({ name, paneId: 'candle_pane' }, true);
          } else {
            // Separate pane indicators
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
        // Create indicator
        if (name === 'MA' || name === 'BOLL') {
          chartRef.current.createIndicator({ name, paneId: 'candle_pane' });
        } else {
          chartRef.current.createIndicator({ name });
        }
        setIndicators((prev) => ({ ...prev, [name]: true }));
      } else {
        // Safe removal across all panes
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
        pricePrecision: 2,
        volumePrecision: 0,
      });

      chart.setPeriod({
        span: 1,
        type: isIntraday ? 'minute' : 'day',
      });

      // Dark Theme Styling
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
          horizontal: { color: 'rgba(24, 24, 22, 0.5)', style: 'dashed', size: 1 },
          vertical: { color: 'rgba(24, 24, 22, 0.5)', style: 'dashed', size: 1 },
        },
        xAxis: {
          axisLine: { color: 'rgba(70, 70, 70, 0.8)', size: 1 },
          tickLine: { color: 'rgba(70, 70, 70, 0.6)', size: 1, length: 3 },
          tickText: {
            color: 'rgba(157, 157, 162, 0.9)',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 12,
            weight: '400',
          },
          title: { show: false },
        },
        yAxis: {
          axisLine: { color: 'rgba(70, 70, 70, 0.8)', size: 1 },
          tickLine: { color: 'rgba(70, 70, 70, 0.6)', size: 1, length: 3 },
          tickText: {
            color: 'rgba(157, 157, 162, 0.9)',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 12,
            weight: '400',
          },
          title: { show: false },
        },
        background: { color: 'transparent' },
        tooltip: {
          text: {
            color: '#cdcdc9',
            family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            size: 12,
          },
          backgroundColor: 'rgba(10, 10, 10, 0.95)',
          borderColor: 'rgba(70, 70, 70, 0.8)',
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
              color: '#9d9da2',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              size: 12,
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
              color: '#9d9da2',
              family: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
              size: 12,
              paddingLeft: 4,
              paddingRight: 4,
              paddingTop: 2,
              paddingBottom: 2,
            },
          },
        },
      });

      // Load initial dataset using v10 API
      const formattedData = formatKlineData(data);
      chart.setDataLoader({
        getBars: ({ callback }) => {
          callback(formattedData);
        },
        subscribeBar: ({ symbol, period, callback }) => {
          // Real-time updates would go here
        },
        unsubscribeBar: ({ symbol, period }) => {
          // Cleanup would go here
        },
      });

      // Re-apply currently active indicators
      applyIndicators(chart, indicators);

      // Subscribe to Crosshair Movement
      chart.subscribeAction('onCrosshairChange', (crosshairData) => {
        if (crosshairData && typeof crosshairData.dataIndex === 'number') {
          const dataList = chart.getDataList() || [];
          if (crosshairData.dataIndex >= 0 && crosshairData.dataIndex < dataList.length) {
            const kline = dataList[crosshairData.dataIndex];
            const date = new Date(kline.timestamp);

            const timeStr = isIntraday
              ? date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
              : date.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });

            setHoveredData({
              timestamp: timeStr,
              open: kline.open?.toFixed(2) || '0.00',
              high: kline.high?.toFixed(2) || '0.00',
              low: kline.low?.toFixed(2) || '0.00',
              close: kline.close?.toFixed(2) || '0.00',
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
  }, [ticker, isIntraday, applyIndicators, indicators]);

  // Update Data Smoothly without destroying/re-creating canvas
  useEffect(() => {
    if (chartRef.current && data && data.length > 0) {
      const formattedData = formatKlineData(data);
      // Update data loader with new data
      chartRef.current.setDataLoader({
        getBars: ({ callback }) => {
          callback(formattedData);
        },
        subscribeBar: ({ symbol, period, callback }) => {
          // Real-time updates
        },
        unsubscribeBar: ({ symbol, period }) => {
          // Cleanup
        },
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
        style={{
          height: `${height}px`,
        }}
      />
    </div>
  );
}
