import { useState, useEffect, useCallback } from 'react';
import { getToken } from '../api/client';

const API_BASE = 'http://127.0.0.1:8000/api/v1/backtest';

/**
 * useBacktest - Custom hook for backtest state management
 *
 * Handles:
 * - Fetching available strategies
 * - Managing backtest parameters and form state
 * - Executing backtests
 * - Caching and error handling
 */
export function useBacktest() {
  // Strategies
  const [strategies, setStrategies] = useState([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [strategiesError, setStrategiesError] = useState(null);

  // Selected strategy
  const [selectedStrategyId, setSelectedStrategyId] = useState(null);
  const [selectedStrategy, setSelectedStrategy] = useState(null);

  // Form state
  const [formState, setFormState] = useState({
    symbol: 'AAPL',
    timeframe: '1d',
    startDate: '2026-08-07',
    endDate: '2026-08-08',
    initialCapital: 1000,
    parameters: {},
  });

  // Backtest execution
  const [backtest, setBacktest] = useState(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState(null);

  // Fetch strategies on mount
  useEffect(() => {
    const fetchStrategies = async () => {
      setStrategiesLoading(true);
      setStrategiesError(null);
      try {
        const token = getToken();
        const res = await fetch(`${API_BASE}/strategies`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });
        if (!res.ok) throw new Error('Failed to fetch strategies');
        const data = await res.json();
        setStrategies(data);
        // Auto-select first strategy
        if (data.length > 0) {
          setSelectedStrategyId(data[0].id);
          setSelectedStrategy(data[0]);
          // Initialize parameters with defaults
          const defaults = {};
          data[0].parameters.forEach(param => {
            defaults[param.name] = param.default;
          });
          setFormState(prev => ({ ...prev, parameters: defaults }));
        }
      } catch (err) {
        setStrategiesError(err.message);
      } finally {
        setStrategiesLoading(false);
      }
    };

    fetchStrategies();
  }, []);

  // Update selected strategy
  const selectStrategy = useCallback((strategyId) => {
    const strategy = strategies.find(s => s.id === strategyId);
    if (strategy) {
      setSelectedStrategyId(strategyId);
      setSelectedStrategy(strategy);

      // Reset parameters to defaults
      const defaults = {};
      strategy.parameters.forEach(param => {
        defaults[param.name] = param.default;
      });
      setFormState(prev => ({ ...prev, parameters: defaults }));
    }
  }, [strategies]);

  // Update form field
  const updateFormField = useCallback((field, value) => {
    setFormState(prev => ({
      ...prev,
      [field]: value,
    }));
  }, []);

  // Update strategy parameter
  const updateParameter = useCallback((paramName, value) => {
    setFormState(prev => ({
      ...prev,
      parameters: {
        ...prev.parameters,
        [paramName]: value,
      },
    }));
  }, []);

  // Run backtest
  const runBacktest = useCallback(async () => {
    if (!selectedStrategyId) {
      setBacktestError('No strategy selected');
      return;
    }

    setBacktestLoading(true);
    setBacktestError(null);
    setBacktest(null);

    try {
      const token = getToken();
      const payload = {
        strategy_id: selectedStrategyId,
        symbol: formState.symbol,
        timeframe: formState.timeframe,
        start_date: formState.startDate,
        end_date: formState.endDate,
        initial_capital: parseFloat(formState.initialCapital),
        parameters: formState.parameters,
      };

      console.log('Backtest payload:', payload);

      const res = await fetch(`${API_BASE}/preset`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const responseData = await res.json();
      console.log('Backtest response:', responseData);

      if (!res.ok) {
        const errorMsg = responseData.detail || JSON.stringify(responseData) || 'Backtest failed';
        throw new Error(errorMsg);
      }

      setBacktest(responseData);
    } catch (err) {
      console.error('Backtest error:', err);
      setBacktestError(err.message);
      setBacktest(null);
    } finally {
      setBacktestLoading(false);
    }
  }, [selectedStrategyId, formState]);

  return {
    // Strategies
    strategies,
    strategiesLoading,
    strategiesError,
    selectedStrategy,
    selectStrategy,

    // Form state
    formState,
    updateFormField,
    updateParameter,

    // Backtest
    backtest,
    backtestLoading,
    backtestError,
    runBacktest,
  };
}
