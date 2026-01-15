/**
 * AnalyticsTab Component
 * 
 * Displays comprehensive analytics and time-series data visualizations for the supply chain simulation.
 * Includes charts for weather, warehouse inventory, fleet utilization, retailer stock, and truck metrics.
 * 
 * @component
 * @param {Object} props - Component props
 * @param {string} props.simulationId - The ID of the currently active simulation run
 * @param {Object} props.simData - Complete simulation data including warehouses, retailers, and trucks
 * @param {Array} props.simData.warehouses - Array of warehouse entities with IDs
 * @param {Array} props.simData.retailers - Array of retailer entities with IDs
 * @param {Array} props.simData.trucks - Array of truck entities with IDs
 */
import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import './AnalyticsTab.css';
import { API_URL, calculatePollInterval, DEFAULT_SIM_SPEED, DEFAULT_TIMESTEP_MINUTES } from '../../constants';

// Register Chart.js components (required for Chart.js v3+)
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    Filler
);


const AnalyticsTab = ({ simulationId, simData }) => {
    const [selectedWarehouse, setSelectedWarehouse] = useState('');
    const [selectedRetailer, setSelectedRetailer] = useState('');
    const [selectedTruck, setSelectedTruck] = useState('');

    const [weatherData, setWeatherData] = useState([]);
    const [warehouseInventory, setWarehouseInventory] = useState([]);
    const [warehouseFleet, setWarehouseFleet] = useState([]);
    const [retailerStock, setRetailerStock] = useState([]);
    const [truckFuel, setTruckFuel] = useState([]);
    const [truckFatigue, setTruckFatigue] = useState([]);

    // CLIENT-SIDE CACHING FOR PERFORMANCE
    // Cache fetched data per entity to eliminate delays when switching
    // Each cache entry: { entityId: { inventory: [...], fleet: [...], lastFetch: timestamp } }
    const [warehouseCache, setWarehouseCache] = useState({});
    const [retailerCache, setRetailerCache] = useState({});
    const [truckCache, setTruckCache] = useState({});

    // Calculate dynamic aggregation window based on simulation metadata
    // Window = timestep (in minutes) from simulation parameters
    // This ensures charts match the actual data arrival rate (timestep/speed)
    const getAggregationWindow = useCallback(() => {
        if (!simData?.time_step_minutes) {
            return '1m'; // Fallback if metadata not available
        }
        // Use simulation timestep as aggregation window
        // Data arrives at rate of timestep/speed in real-time
        return `${simData.time_step_minutes}m`;
    }, [simData]);

    // Poll interval calculation (using metadata from useEffect)
    const [pollInterval, setPollInterval] = useState(
        calculatePollInterval(DEFAULT_TIMESTEP_MINUTES, DEFAULT_SIM_SPEED)
    ); // Dynamic default based on constants

    // Initialize selections when simData loads
    useEffect(() => {
        if (simData?.warehouses?.length > 0 && !selectedWarehouse) {
            setSelectedWarehouse(simData.warehouses[0].id);
        }
        if (simData?.retailers?.length > 0 && !selectedRetailer) {
            setSelectedRetailer(simData.retailers[0].id);
        }
        if (simData?.trucks?.length > 0 && !selectedTruck) {
            setSelectedTruck(simData.trucks[0].truck_id);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [simData]); // Only re-run when simData changes, not when selections change

    // Fetch simulation metadata and calculate poll interval
    useEffect(() => {
        if (!simulationId) return;

        fetch(`${API_URL}/simulations/${simulationId}`)
            .then(res => res.json())
            .then(metadata => {
                const speed = metadata.speed || 10;
                const timestep = metadata.time_step_minutes || 1;

                // Calculate poll interval: (timestep_minutes * 60 / speed) * 1000ms
                // Example: 1 min @ 10x = (1 * 60 / 10) * 1000 = 6000ms
                const interval = (timestep * 60 / speed) * 1000;
                setPollInterval(interval);
                console.log(`📊 Analytics refresh: ${interval}ms (${timestep}min @ ${speed}x)`);
            })
            .catch(err => console.error('Metadata fetch error:', err));
    }, [simulationId]);

    // Fetch weather history with auto-refresh
    const fetchWeatherData = useCallback(() => {
        if (!simulationId) return;

        fetch(`${API_URL}/timeseries/weather?run_id=${simulationId}`)
            .then(res => res.json())
            .then(data => {
                console.log('🌡️ Weather API response:', {
                    count: data.length,
                    first: data[0],
                    last: data[data.length - 1]
                });

                // Sort by timestamp to ensure correct chronological order
                const sortedData = data.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));

                // SMART DYNAMIC DOWNSAMPLING - Adapts to simulation duration
                // Ensures optimal quality for any run length (1 day to 30+ days)
                let displayData;
                let targetPoints;

                // Determine target points based on data size
                if (sortedData.length < 1000) {
                    // Short simulations (< 1 day): Keep ALL data
                    targetPoints = sortedData.length;
                } else if (sortedData.length < 5000) {
                    // Medium simulations (1-3 days): High detail
                    targetPoints = 1500;
                } else if (sortedData.length < 20000) {
                    // Long simulations (3-14 days): Good detail
                    targetPoints = 2000;
                } else {
                    // Very long simulations (14+ days): Balanced detail/performance
                    targetPoints = 2500;
                }

                // Apply downsampling if needed
                if (sortedData.length > targetPoints) {
                    const step = Math.ceil(sortedData.length / targetPoints);
                    displayData = sortedData.filter((_, index) => index % step === 0);
                    console.log(`🌡️ Smart downsample: ${sortedData.length} → ${displayData.length} points (step=${step}, ~${Math.round(sortedData.length / displayData.length)} min/point)`);
                } else {
                    displayData = sortedData;
                    console.log(`🌡️ No downsampling needed: ${sortedData.length} points (every minute)`);
                }

                // Filter out any invalid data points
                const validData = displayData.filter(point =>
                    point &&
                    point.temperature !== undefined &&
                    point.temperature !== null &&
                    !isNaN(point.temperature)
                );

                console.log('🌡️ Setting weather data:', validData.length, 'valid points');
                setWeatherData(validData);
            })
            .catch(err => {
                console.error('Weather fetch error:', err);
                console.error('Weather API URL:', `${API_URL}/timeseries/weather?run_id=${simulationId}`);
            });
    }, [simulationId]);

    useEffect(() => {
        fetchWeatherData(); // Initial fetch
        const interval = setInterval(fetchWeatherData, pollInterval);
        return () => clearInterval(interval);
    }, [simulationId, pollInterval, fetchWeatherData]);

    // Fetch warehouse data with auto-refresh and intelligent caching
    const fetchWarehouseData = useCallback((forceRefresh = false) => {
        if (!simulationId || !selectedWarehouse) return;

        // Check cache first (unless forcing refresh for live updates)
        if (!forceRefresh && warehouseCache[selectedWarehouse]) {
            const cached = warehouseCache[selectedWarehouse];
            console.log(`📦 Cache HIT: Warehouse ${selectedWarehouse} (instant load)`);
            setWarehouseInventory(cached.inventory);
            setWarehouseFleet(cached.fleet);
            return;
        }

        console.log(`🌐 Cache MISS: Fetching Warehouse ${selectedWarehouse}...`);
        const window = getAggregationWindow();

        Promise.all([
            fetch(`${API_URL}/timeseries/warehouse/inventory?run_id=${simulationId}&warehouse_id=${selectedWarehouse}&window=${window}`),
            fetch(`${API_URL}/timeseries/warehouse/fleet?run_id=${simulationId}&warehouse_id=${selectedWarehouse}&window=${window}`)
        ])
            .then(([inv, fleet]) => Promise.all([inv.json(), fleet.json()]))
            .then(([invData, fleetData]) => {
                setWarehouseInventory(invData);
                setWarehouseFleet(fleetData);

                // Update cache with fresh data
                setWarehouseCache(prev => ({
                    ...prev,
                    [selectedWarehouse]: {
                        inventory: invData,
                        fleet: fleetData,
                        lastFetch: Date.now()
                    }
                }));
            })
            .catch(err => console.error('Warehouse fetch error:', err));
    }, [simulationId, selectedWarehouse, getAggregationWindow, warehouseCache]);

    useEffect(() => {
        fetchWarehouseData(); // Initial fetch (use cache if available)
        // Periodic refresh with forceRefresh=true to get live updates
        const interval = setInterval(() => fetchWarehouseData(true), pollInterval);
        return () => clearInterval(interval);
    }, [simulationId, selectedWarehouse, pollInterval, fetchWarehouseData]);

    // Fetch retailer data with auto-refresh and intelligent caching
    const fetchRetailerData = useCallback((forceRefresh = false) => {
        if (!simulationId || !selectedRetailer) return;

        // Check cache first (unless forcing refresh for live updates)
        if (!forceRefresh && retailerCache[selectedRetailer]) {
            const cached = retailerCache[selectedRetailer];
            console.log(`📦 Cache HIT: Retailer ${selectedRetailer} (instant load)`);
            setRetailerStock(cached.stock);
            return;
        }

        console.log(`🌐 Cache MISS: Fetching Retailer ${selectedRetailer}...`);
        const window = getAggregationWindow();

        fetch(`${API_URL}/timeseries/retailer/stock?run_id=${simulationId}&retailer_id=${selectedRetailer}&window=${window}`)
            .then(res => res.json())
            .then(data => {
                setRetailerStock(data);

                // Update cache with fresh data
                setRetailerCache(prev => ({
                    ...prev,
                    [selectedRetailer]: {
                        stock: data,
                        lastFetch: Date.now()
                    }
                }));
            })
            .catch(err => console.error('Retailer fetch error:', err));
    }, [simulationId, selectedRetailer, getAggregationWindow, retailerCache]);

    useEffect(() => {
        fetchRetailerData(); // Initial fetch (use cache if available)
        // Periodic refresh with forceRefresh=true to get live updates
        const interval = setInterval(() => fetchRetailerData(true), pollInterval);
        return () => clearInterval(interval);
    }, [simulationId, selectedRetailer, pollInterval, fetchRetailerData]);

    // Fetch truck data with auto-refresh and intelligent caching
    const fetchTruckData = useCallback((forceRefresh = false) => {
        if (!simulationId || !selectedTruck) return;

        // Check cache first (unless forcing refresh for live updates)
        if (!forceRefresh && truckCache[selectedTruck]) {
            const cached = truckCache[selectedTruck];
            console.log(`📦 Cache HIT: Truck ${selectedTruck} (instant load)`);
            setTruckFuel(cached.fuel);
            setTruckFatigue(cached.fatigue);
            return;
        }

        console.log(`🌐 Cache MISS: Fetching Truck ${selectedTruck}...`);
        const window = getAggregationWindow();

        Promise.all([
            fetch(`${API_URL}/timeseries/truck/fuel?run_id=${simulationId}&truck_id=${selectedTruck}&window=${window}`),
            fetch(`${API_URL}/timeseries/truck/fatigue?run_id=${simulationId}&truck_id=${selectedTruck}&window=${window}`)
        ])
            .then(([fuel, fatigue]) => Promise.all([fuel.json(), fatigue.json()]))
            .then(([fuelData, fatigueData]) => {
                setTruckFuel(fuelData);
                setTruckFatigue(fatigueData);

                // Update cache with fresh data
                setTruckCache(prev => ({
                    ...prev,
                    [selectedTruck]: {
                        fuel: fuelData,
                        fatigue: fatigueData,
                        lastFetch: Date.now()
                    }
                }));
            })
            .catch(err => console.error('Truck fetch error:', err));
    }, [simulationId, selectedTruck, getAggregationWindow, truckCache]);

    useEffect(() => {
        fetchTruckData(); // Initial fetch (use cache if available)
        // Periodic refresh with forceRefresh=true to get live updates
        const interval = setInterval(() => fetchTruckData(true), pollInterval);
        return () => clearInterval(interval);
    }, [simulationId, selectedTruck, pollInterval, fetchTruckData]);

    /**
     * Formats simulation time for display in charts
     * 
     * @param {string} isoString - ISO 8601 timestamp string (fallback)
     * @param {number} timestamp - Simulation time in minutes since start (preferred)
     * @returns {string} Formatted time string in "Day X, HH:MM" format or locale time string
     */
    const formatTime = (isoString, timestamp) => {
        if (timestamp !== undefined) {
            // Convert timestamp (minutes since start) to Day X, HH:MM format
            const day = Math.floor(timestamp / 1440); // 1440 minutes in a day
            const minutesInDay = timestamp % 1440;
            const hours = Math.floor(minutesInDay / 60);
            const minutes = Math.floor(minutesInDay % 60);
            return `Day ${day}, ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`;
        }
        // Fallback to time if timestamp not available
        const date = new Date(isoString);
        return date.toLocaleTimeString();
    };

    // Weather chart data
    const weatherChartData = {
        labels: weatherData.map(w => formatTime(w.time, w.timestamp)),
        datasets: [{
            label: 'Temperature (°C)',
            data: weatherData.map(w => w.temperature),
            borderColor: 'rgb(255, 99, 132)',
            tension: 0.4  // Smooth curve to hide downsampling jumps (0 = straight lines, 1 = very curvy)
        }]
    };

    // Warehouse inventory chart
    const warehouseInventoryChartData = {
        labels: warehouseInventory.map(d => formatTime(d.time, d.timestamp)),
        datasets: [{
            label: 'Inventory (kg)',
            data: warehouseInventory.map(d => d.value),
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            fill: true,
            tension: 0.1
        }]
    };

    // Warehouse fleet chart
    const warehouseFleetChartData = {
        labels: warehouseFleet
            .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))  // Sort by timestamp for correct chronological order
            .map(d => formatTime(d.time, d.timestamp)),
        datasets: [
            {
                label: 'Available Trucks',
                data: warehouseFleet
                    .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
                    .map(d => d.available),
                borderColor: 'rgb(54, 162, 235)',
                backgroundColor: 'rgba(54, 162, 235, 0.5)',
                fill: true
            },
            {
                label: 'In Transit',
                data: warehouseFleet
                    .sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0))
                    .map(d => d.in_transit),
                borderColor: 'rgb(255, 159, 64)',
                backgroundColor: 'rgba(255, 159, 64, 0.5)',
                fill: true
            }
        ]
    };

    // Retailer stock chart
    const retailerStockChartData = {
        labels: retailerStock.map(d => formatTime(d.time, d.timestamp)),
        datasets: [{
            label: 'Stock (kg)',
            data: retailerStock.map(d => d.value),
            borderColor: 'rgb(153, 102, 255)',
            backgroundColor: 'rgba(153, 102, 255, 0.2)',
            fill: true,
            tension: 0.1
        }]
    };

    // Truck fuel chart
    const truckFuelChartData = {
        labels: truckFuel.map(d => formatTime(d.time, d.timestamp)),
        datasets: [{
            label: 'Fuel Level (%)',
            data: truckFuel.map(d => d.value),
            borderColor: 'rgb(255, 205, 86)',
            backgroundColor: 'rgba(255, 205, 86, 0.2)',
            fill: true,
            tension: 0.1
        }]
    };

    // Truck fatigue chart
    const truckFatigueChartData = {
        labels: truckFatigue.map(d => formatTime(d.time, d.timestamp)),
        datasets: [{
            label: 'Driver Fatigue (hours)',
            data: truckFatigue.map(d => d.value),
            borderColor: 'rgb(255, 99, 132)',
            backgroundColor: 'rgba(255, 99, 132, 0.2)',
            fill: true,
            tension: 0.1
        }]
    };

    // Chart options with proper Y-axis scaling
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
            }
        },
        scales: {
            y: {
                beginAtZero: true,  // Start from zero
                min: 0,             // Minimum value is 0
                ticks: {
                    callback: function (value) {
                        return Number.isInteger(value) ? value : value.toFixed(1);
                    }
                }
            },
            x: {
                type: 'category',
                ticks: {
                    maxTicksLimit: 8,
                    autoSkip: true,
                    autoSkipPadding: 10
                }
            }
        }
    };

    // Percentage chart options (for fuel level: 0-100%)
    const percentageChartOptions = {
        ...chartOptions,
        scales: {
            ...chartOptions.scales,
            y: {
                beginAtZero: true,
                min: 0,
                max: 100,
                ticks: {
                    callback: function (value) {
                        return value + '%';
                    }
                }
            }
        }
    };

    return (
        <div className="analytics-tab">
            <h2>📊 Analytics & Trends</h2>

            {/* Weather Panel */}
            <div className="analytics-section">
                <h3>🌦️ Weather History</h3>
                <div className="chart-container" style={{ height: '200px' }} aria-label="Weather temperature chart over time">
                    <Line data={weatherChartData} options={chartOptions} />
                </div>
                <div className="weather-list">
                    {weatherData.slice(-5).reverse().map((w) => (
                        <div key={`weather-${w.timestamp || w.time}`} className="weather-item">
                            <span className="weather-time">{formatTime(w.time, w.timestamp)}</span>
                            <span className={`weather-state state-${w.state}`}>{w.state}</span>
                            <span className="weather-temp">{w.temperature?.toFixed(1)}°C</span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Warehouse Panel */}
            <div className="analytics-section">
                <h3>🏭 Warehouse Analytics</h3>
                <select
                    value={selectedWarehouse}
                    onChange={(e) => setSelectedWarehouse(e.target.value)}
                    className="entity-selector"
                    aria-label="Select warehouse to view analytics"
                >
                    {simData?.warehouses?.map(wh => (
                        <option key={wh.id} value={wh.id}>
                            {wh.id}
                        </option>
                    ))}
                </select>

                <div className="chart-row">
                    <div className="chart-col">
                        <h4>Inventory Over Time</h4>
                        <div className="chart-container" style={{ height: '250px' }} aria-label="Warehouse inventory levels over time">
                            <Line data={warehouseInventoryChartData} options={chartOptions} />
                        </div>
                    </div>
                    <div className="chart-col">
                        <h4>Fleet Utilization</h4>
                        <div className="chart-container" style={{ height: '250px' }} aria-label="Warehouse fleet availability and utilization over time">
                            <Line data={warehouseFleetChartData} options={chartOptions} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Retailer Panel */}
            <div className="analytics-section">
                <h3>🏪 Retailer Analytics</h3>
                <select
                    value={selectedRetailer}
                    onChange={(e) => setSelectedRetailer(e.target.value)}
                    className="entity-selector"
                    aria-label="Select retailer to view analytics"
                >
                    {simData?.retailers?.map(ret => (
                        <option key={ret.id} value={ret.id}>
                            {ret.id}
                        </option>
                    ))}
                </select>

                <div className="chart-container" style={{ height: '250px' }} aria-label="Retailer stock levels over time">
                    <Line data={retailerStockChartData} options={chartOptions} />
                </div>
            </div>

            {/* Truck Panel */}
            <div className="analytics-section">
                <h3>🚛 Truck Analytics</h3>
                <select
                    value={selectedTruck}
                    onChange={(e) => setSelectedTruck(e.target.value)}
                    className="entity-selector"
                    aria-label="Select truck to view analytics"
                >
                    {simData?.trucks?.map(truck => (
                        <option key={truck.truck_id} value={truck.truck_id}>
                            {truck.truck_id}
                        </option>
                    ))}
                </select>

                <div className="chart-row">
                    <div className="chart-col">
                        <h4>Fuel Level Over Time</h4>
                        <div className="chart-container" style={{ height: '250px' }} aria-label="Truck fuel level percentage over time">
                            <Line data={truckFuelChartData} options={percentageChartOptions} />
                        </div>
                    </div>
                    <div className="chart-col">
                        <h4>Driver Fatigue Over Time</h4>
                        <div className="chart-container" style={{ height: '250px' }} aria-label="Driver fatigue hours over time">
                            <Line data={truckFatigueChartData} options={chartOptions} />
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

// PropTypes validation for type safety and documentation
AnalyticsTab.propTypes = {
    simulationId: PropTypes.string.isRequired,
    simData: PropTypes.shape({
        warehouses: PropTypes.arrayOf(PropTypes.shape({
            id: PropTypes.string.isRequired
        })),
        retailers: PropTypes.arrayOf(PropTypes.shape({
            id: PropTypes.string.isRequired
        })),
        trucks: PropTypes.arrayOf(PropTypes.shape({
            truck_id: PropTypes.string.isRequired
        }))
    }).isRequired
};

export default AnalyticsTab;
