/**
 * WeatherPanel Component
 * 
 * Displays current weather conditions based on the simulation timeline.
 * Fetches weather time-series data and shows the current weather state
 * synchronized with the simulation's current time.
 * 
 * @component
 * @param {Object} props - Component props
 * @param {string} props.runId - The ID of the currently running simulation
 * @param {number} props.currentTime - Current simulation time in minutes since start
 */
import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import axios from 'axios';
import { API_URL, WEATHER_ICONS, calculatePollInterval, DEFAULT_SIM_SPEED, DEFAULT_TIMESTEP_MINUTES } from '../../constants';


function WeatherPanel({ runId, currentTime }) {
    const [weatherData, setWeatherData] = useState([]);
    const [currentWeather, setCurrentWeather] = useState(null);
    const [loading, setLoading] = useState(true);
    const [pollInterval, setPollInterval] = useState(
        calculatePollInterval(DEFAULT_TIMESTEP_MINUTES, DEFAULT_SIM_SPEED)
    ); // Dynamic default based on constants

    // Fetch simulation metadata to calculate poll interval
    useEffect(() => {
        if (!runId) return;

        const fetchMetadata = async () => {
            try {
                const res = await axios.get(`${API_URL}/simulations/${runId}`);
                const speed = res.data.speed || 10;
                const timestep = res.data.time_step_minutes || 1;
                const interval = (timestep * 60 / speed) * 1000;
                setPollInterval(interval);
                console.log(`🌦️ Weather refresh: ${interval}ms (${timestep}min @ ${speed}x)`);
            } catch (err) {
                console.error('Metadata fetch error:', err);
            }
        };

        fetchMetadata();
    }, [runId]);

    // Fetch weather timeseries data with auto-refresh
    const fetchWeatherData = useCallback(async () => {
        if (!runId) return;

        try {
            // Only show loading on initial fetch (when weatherData is empty)
            // Keep previous data visible during background refreshes
            if (weatherData.length === 0) {
                setLoading(true);
            }
            const res = await axios.get(`${API_URL}/timeseries/weather?run_id=${runId}`);
            setWeatherData(res.data || []);
        } catch (err) {
            console.error('Weather fetch error:', err);
        } finally {
            // Only clear loading if it was set (initial load)
            if (weatherData.length === 0) {
                setLoading(false);
            }
        }
    }, [runId, weatherData.length]);

    useEffect(() => {
        fetchWeatherData(); // Initial fetch
        const interval = setInterval(fetchWeatherData, pollInterval);
        return () => clearInterval(interval);
    }, [runId, pollInterval, fetchWeatherData]);

    // Update current weather based on simulation timestamp
    useEffect(() => {
        if (!weatherData.length || currentTime === null || currentTime === undefined) return;

        // IMPORTANT: Sort data by timestamp first (API returns unsorted!)
        const sortedWeather = [...weatherData].sort((a, b) => a.timestamp - b.timestamp);

        // Find the most recent weather event before or at currentTime
        const current = sortedWeather
            .filter(w => w.timestamp <= currentTime)
            .pop(); // Last element = most recent

        setCurrentWeather(current || sortedWeather[0]);
    }, [weatherData, currentTime]);

    if (loading) {
        return (
            <div className="panel weather-panel">
                <h3>🌦️ Weather Conditions</h3>
                <div className="weather-display">Loading...</div>
            </div>
        );
    }

    if (!currentWeather) {
        return (
            <div className="panel weather-panel">
                <h3>🌦️ Weather Conditions</h3>
                <div className="weather-display">No weather data available</div>
            </div>
        );
    }

    const icon = WEATHER_ICONS[currentWeather.state] || '🌤️';
    const stateName = (currentWeather.state || 'unknown')
        .replace('_', ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');

    return (
        <div className="panel weather-panel">
            <h3>🌦️ Weather Conditions</h3>
            <div className="weather-display">
                <div className="weather-icon">{icon}</div>
                <div className="weather-state">{stateName}</div>
            </div>
        </div>
    );
}

// PropTypes validation for type safety
WeatherPanel.propTypes = {
    runId: PropTypes.string.isRequired,
    currentTime: PropTypes.number.isRequired
};

export default WeatherPanel;
