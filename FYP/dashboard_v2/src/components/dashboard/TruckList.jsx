/**
 * TruckList Component
 * 
 * Displays a sorted, collapsible list of trucks with their current status,
 * fuel levels, cargo, and speed. Trucks are sorted by priority: active > crashed > idle.
 * 
 * @component
 */
import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { TRUCK_STATUS_INFO } from '../../constants';

const TruckList = React.memo(({ trucks }) => {
    // Memoize sorted trucks to avoid recalculation on every render
    const sortedTrucks = useMemo(() => {
        return [...trucks].sort((a, b) => {
            // Define status priority: active > crashed > idle
            const activeTrucks = ['in_transit', 'loading', 'unloading', 'returning'];
            const isActiveA = activeTrucks.includes(a.status);
            const isActiveB = activeTrucks.includes(b.status);
            const isCrashedA = ['crashed', 'broken'].includes(a.status);
            const isCrashedB = ['crashed', 'broken'].includes(b.status);

            // Sort: active first, then crashed, then idle
            if (isActiveA && !isActiveB) return -1;
            if (!isActiveA && isActiveB) return 1;
            if (isCrashedA && !isCrashedB) return -1;
            if (!isCrashedA && isCrashedB) return 1;

            // Within same category, sort alphabetically
            return a.truck_id.localeCompare(b.truck_id);
        });
    }, [trucks]);

    // Calculate summary statistics
    const stats = useMemo(() => {
        const active = trucks.filter((t) =>
            ['in_transit', 'loading', 'unloading', 'returning'].includes(t.status)
        ).length;
        const idle = trucks.filter((t) => t.status === 'idle').length;
        const crashed = trucks.filter((t) => ['crashed', 'broken'].includes(t.status)).length;

        return {
            active,
            idle,
            crashed,
            summary: `• ${active} Active, ${idle} Idle${crashed > 0 ? `, ${crashed} ⚠️` : ''}`,
        };
    }, [trucks]);

    return (
        <details>
            <summary>
                🚛 Trucks ({trucks.length}) {stats.summary}
            </summary>
            <ul style={{ listStyle: 'none', padding: '0' }}>
                {sortedTrucks.map((truck) => {
                    // Use status info from constants for consistency
                    const info = TRUCK_STATUS_INFO[truck.status] || TRUCK_STATUS_INFO.idle;
                    const fuelColor =
                        truck.fuel_percent < 20
                            ? '#ef4444'
                            : truck.fuel_percent < 50
                                ? '#f59e0b'
                                : '#10b981';

                    return (
                        <li
                            key={truck.truck_id}
                            style={{
                                marginBottom: '12px',
                                padding: '10px',
                                background:
                                    'linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
                                borderRadius: '8px',
                                border: '1px solid rgba(255,255,255,0.1)',
                                fontSize: '12px',
                                lineHeight: '1.6',
                            }}
                        >
                            <div style={{ fontWeight: 'bold', marginBottom: '6px', color: '#e2e8f0' }}>
                                {truck.truck_id}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>{info.icon}</span>
                                    <span style={{ color: info.color, fontWeight: '600' }}>
                                        {info.label}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>⛽</span>
                                    <span style={{ color: fuelColor }}>
                                        {truck.fuel_percent.toFixed(1)}%
                                    </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>📦</span>
                                    <span style={{ color: '#94a3b8' }}>
                                        {truck.cargo_kg.toFixed(0)} kg
                                    </span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                    <span>⚡</span>
                                    <span style={{ color: '#94a3b8' }}>
                                        {truck.speed_kmh.toFixed(1)} km/h
                                    </span>
                                </div>
                            </div>
                        </li>
                    );
                })}
            </ul>
        </details>
    );
});

TruckList.displayName = 'TruckList';

TruckList.propTypes = {
    trucks: PropTypes.arrayOf(
        PropTypes.shape({
            truck_id: PropTypes.string.isRequired,
            status: PropTypes.string.isRequired,
            fuel_percent: PropTypes.number.isRequired,
            cargo_kg: PropTypes.number.isRequired,
            speed_kmh: PropTypes.number.isRequired,
        })
    ).isRequired,
};

export default TruckList;
