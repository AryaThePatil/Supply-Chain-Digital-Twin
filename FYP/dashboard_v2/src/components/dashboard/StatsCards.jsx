/**
 * StatsCards Component
 * 
 * Displays summary statistics cards for warehouses, retailers, and trucks.
 * Shows entity counts and current simulation speed/update interval.
 * 
 * @component
 */
import React from 'react';
import PropTypes from 'prop-types';

const StatsCards = React.memo(({ warehouseCount, retailerCount, truckCount, speed, pollInterval }) => {
    return (
        <>
            <div className="stat-card">
                <div className="stat-icon">📦</div>
                <div className="stat-content">
                    <div className="stat-value">{warehouseCount}</div>
                    <div className="stat-label">Warehouses</div>
                </div>
            </div>

            <div className="stat-card">
                <div className="stat-icon">🏪</div>
                <div className="stat-content">
                    <div className="stat-value">{retailerCount}</div>
                    <div className="stat-label">Retailers</div>
                </div>
            </div>

            <div className="stat-card active">
                <div className="stat-icon">🚛</div>
                <div className="stat-content">
                    <div className="stat-value">{truckCount}</div>
                    <div className="stat-label">Trucks</div>
                </div>
            </div>

            <div className="info-box">
                <small>
                    Speed: {speed}x | Updates every {(pollInterval / 1000).toFixed(2)}s (synced
                    with simulation timestep)
                </small>
            </div>
        </>
    );
});

StatsCards.displayName = 'StatsCards';

StatsCards.propTypes = {
    warehouseCount: PropTypes.number.isRequired,
    retailerCount: PropTypes.number.isRequired,
    truckCount: PropTypes.number.isRequired,
    speed: PropTypes.number.isRequired,
    pollInterval: PropTypes.number.isRequired,
};

export default StatsCards;
