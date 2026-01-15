/**
 * EntityPanel Component
 * 
 * Collapsible panel displaying warehouse or retailer entity information.
 * Shows entity IDs and current inventory levels.
 * 
 * @component
 */
import React from 'react';
import PropTypes from 'prop-types';

const EntityPanel = React.memo(({ title, icon, entities, entityIds, openByDefault = false }) => {
    const count = entities.length > 0 ? entities.length : entityIds.length;

    return (
        <details open={openByDefault}>
            <summary>
                {icon} {title} ({count})
            </summary>
            <ul>
                {entities.length > 0
                    ? entities.map((entity) => (
                        <li key={entity.id}>
                            <strong>{entity.id}</strong>
                            {entity.current_inventory_kg !== undefined && (
                                <>
                                    <br />
                                    📦 Inventory: {Math.round(entity.current_inventory_kg)} kg
                                </>
                            )}
                            {entity.total_orders_fulfilled !== undefined && (
                                <>
                                    <br />
                                    📋 Orders: {entity.total_orders_fulfilled}
                                </>
                            )}
                        </li>
                    ))
                    : entityIds.map((id) => <li key={id}>{id}</li>)}
            </ul>
        </details>
    );
});

EntityPanel.displayName = 'EntityPanel';

EntityPanel.propTypes = {
    title: PropTypes.string.isRequired,
    icon: PropTypes.string.isRequired,
    entities: PropTypes.arrayOf(
        PropTypes.shape({
            id: PropTypes.string.isRequired,
            current_inventory_kg: PropTypes.number,
            total_orders_fulfilled: PropTypes.number,
        })
    ),
    entityIds: PropTypes.arrayOf(PropTypes.string),
    openByDefault: PropTypes.bool,
};

EntityPanel.defaultProps = {
    entities: [],
    entityIds: [],
    openByDefault: false,
};

export default EntityPanel;
