# Digital Twin for Supply Chain Management

A digital twin simulation of an orange supply chain network featuring real-time agent-based modeling, IoT sensor simulation, and interactive visualization.

## Overview

This Final Year Project implements a dynamic digital twin for a perishable food supply chain. It simulates warehouses, retailers, trucks, and the complete logistics network to provide real-time monitoring, analytics, and optimization capabilities.

## Features

- **Agent-Based Simulation**: Autonomous warehouse, retailer, and truck agents.
- **Real-Time Data Streaming**: MQTT-based telemetry and event logging.
- **Time-Series Database**: InfluxDB for efficient storage and querying.
- **Interactive Dashboard**: React-based visualization with map tracking and charts.
- **IoT Sensor Simulation**: Simulated GPS, temperature, and inventory sensors.
- **Traffic & Weather Modeling**: Incorporation of environmental factors.
- **Route Optimization**: Dynamic pathfinding utilizing real road networks.

## Architecture

```
├── FYP/
│   ├── src/           # Core simulation engine
│   ├── api/           # FastAPI backend
│   ├── dashboard_v2/  # React frontend
│   ├── config/        # Configuration files
│   └── docker-compose.yml
```

## Technology Stack

- **Backend**: Python, FastAPI
- **Simulation**: SimPy, NetworkX, OSMnx
- **Data**: InfluxDB, MQTT (Mosquitto)
- **Frontend**: React, Leaflet.js, Chart.js
- **Infrastructure**: Docker, Docker Compose

## Prerequisites

- Python 3.10+
- Node.js 16+
- Docker & Docker Compose
- Git

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/AryaThePatil/Supply-Chain-Digital-Twin.git
cd Supply-Chain-Digital-Twin/FYP
```

### 2. Set up environment variables

Create a `.env` file in the `FYP` directory:

```bash
# InfluxDB Configuration
DOCKER_INFLUXDB_INIT_MODE=setup
DOCKER_INFLUXDB_INIT_USERNAME=admin
DOCKER_INFLUXDB_INIT_PASSWORD=your_secure_password_here
DOCKER_INFLUXDB_INIT_ORG=digital-twin
DOCKER_INFLUXDB_INIT_BUCKET=supply-chain
DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=your_secure_token_here

# API Configuration
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=your_secure_token_here
INFLUX_ORG=digital-twin
INFLUX_BUCKET=supply-chain
```

### 3. Start infrastructure services

```bash
# Start InfluxDB and MQTT broker
docker-compose up -d influxdb mosquitto
```

### 4. Run the simulation

```bash
# Activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run simulation
python -m src.main --duration-days 7 --speed 10
```

### 5. Start the API server

```bash
cd api
uvicorn main:app --reload --port 8000
```

### 6. Launch the dashboard

```bash
cd dashboard_v2
npm install
npm run dev
```

Access the dashboard at `http://localhost:5173`

## Dashboard Features

- **Interactive Map**: Real-time truck tracking on OpenStreetMap.
- **KPI Cards**: Inventory levels, deliveries, and trucks in transit.
- **Time-Series Charts**: Demand patterns and temperature monitoring.
- **Entity Panels**: Detailed warehouse and retailer information.
- **Analytics**: Historical data visualization and trend tracking.

## Configuration

Edit `config/simulation_config.yaml` to customize:

- Simulation duration and time step
- Number and location of warehouses/retailers
- Truck fleet composition
- Traffic and weather patterns
- Demand models

## Testing

```bash
# Run unit tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

## Performance

- Evaluated to handle 2+ warehouses, 12+ retailers, and 30+ trucks.
- Configurable real-time updates (1-60 minutes).
- Time-series storage for efficient querying.
- Optimized routing algorithms for logistics planning.

## License

MIT License - see LICENSE file for details

## Contact

**Arya Patil**  
GitHub: [@AryaThePatil](https://github.com/AryaThePatil)

## Acknowledgments

- OpenStreetMap for road network data
- SimPy for discrete-event simulation
- InfluxDB for time-series capabilities
