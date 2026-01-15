/**
 * MapView Component
 * 
 * Interactive Leaflet map displaying warehouses, retailers, and trucks.
 * Shows entity locations with emoji markers and popup information.
 * 
 * @component
 */
import React from 'react';
import PropTypes from 'prop-types';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { createEmojiIcon } from '../../utils/mapHelpers';
import { MAP_CENTER } from '../../constants';

const MapView = React.memo(({ warehouses, retailers, trucks }) => {
    return (
        <MapContainer
            center={[MAP_CENTER.lat, MAP_CENTER.lon]}
            zoom={MAP_CENTER.zoom}
            style={{ height: '100%', width: '100%' }}
        >
            <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution="&copy; OpenStreetMap"
            />

            {/* Warehouse Markers */}
            {warehouses?.map((wh) => (
                <Marker key={wh.id} position={[wh.lat, wh.lon]} icon={createEmojiIcon('🏭')}>
                    <Popup>
                        <strong>📦 {wh.id}</strong>
                        <br />
                        Warehouse
                        <br />
                        <small>Data from IoT: warehouse_state</small>
                    </Popup>
                </Marker>
            ))}

            {/* Retailer Markers */}
            {retailers?.map((ret) => (
                <Marker key={ret.id} position={[ret.lat, ret.lon]} icon={createEmojiIcon('🏪')}>
                    <Popup>
                        <strong>🏪 {ret.id}</strong>
                        <br />
                        Retailer
                        <br />
                        <small>Data from IoT: retailer_state</small>
                    </Popup>
                </Marker>
            ))}

            {/* Truck Markers */}
            {trucks
                .filter((t) => t.location && Array.isArray(t.location))
                .map((truck) => (
                    <Marker
                        key={truck.truck_id}
                        position={truck.location}
                        icon={createEmojiIcon('🚛')}
                    >
                        <Popup>
                            <strong>🚛 {truck.truck_id}</strong>
                            <br />
                            Status: {truck.status}
                            <br />
                            Speed: {truck.speed_kmh} km/h
                            <br />
                            Cargo: {truck.cargo_kg} kg
                            <br />
                            <small>Data from IoT: truck_telemetry</small>
                        </Popup>
                    </Marker>
                ))}
        </MapContainer>
    );
});

MapView.displayName = 'MapView';

MapView.propTypes = {
    warehouses: PropTypes.arrayOf(
        PropTypes.shape({
            id: PropTypes.string.isRequired,
            lat: PropTypes.number.isRequired,
            lon: PropTypes.number.isRequired,
        })
    ),
    retailers: PropTypes.arrayOf(
        PropTypes.shape({
            id: PropTypes.string.isRequired,
            lat: PropTypes.number.isRequired,
            lon: PropTypes.number.isRequired,
        })
    ),
    trucks: PropTypes.arrayOf(
        PropTypes.shape({
            truck_id: PropTypes.string.isRequired,
            location: PropTypes.arrayOf(PropTypes.number),
            status: PropTypes.string.isRequired,
            speed_kmh: PropTypes.number.isRequired,
            cargo_kg: PropTypes.number.isRequired,
        })
    ),
};

MapView.defaultProps = {
    warehouses: [],
    retailers: [],
    trucks: [],
};

export default MapView;
