# 🛡️ AegisAI — Emergency Response & Multi-Agent Digital Twin Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3.1-61DAFB.svg?style=flat&logo=React&logoColor=black)](https://reactjs.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg?style=flat&logo=PostgreSQL&logoColor=white)](https://www.postgresql.org)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4-5B8A3C.svg?style=flat&logo=PostgreSQL&logoColor=white)](https://postgis.net)
[![OSRM](https://img.shields.io/badge/OSRM-Routing-008080.svg?style=flat&logo=OpenStreetMap&logoColor=white)](https://project-osrm.org)
[![Ollama](https://img.shields.io/badge/Ollama-Llama_3.2-black.svg?style=flat)](https://ollama.com)

**AegisAI** is a mission-critical emergency response, resource allocation, and digital-twin disaster simulation platform, currently evolving into a **Multi-Agent System (MAS)**. It integrates geospatial intelligence (PostGIS + OSRM), deterministic AI decision optimization (Scipy Linear Sum Assignment + multi-criteria scoring), Explainable AI (XAI) operational briefings (Ollama Llama 3.2), multi-horizon predictive forecasting (+5m, +15m, +30m, +60m), and an upcoming coordinated multi-agent orchestration layer into a unified command and control system.

---

## 📌 Implementation Status Matrix

| Priority / Module | Backend Status | Frontend Status | Overall Status | Notes & Capabilities |
| :--- | :---: | :---: | :---: | :--- |
| **Priority 1: Core System & Integration** | ✅ Complete | ✅ Complete | **DONE** | Full JWT lifecycle, REST endpoints, and WebSocket sync. Currently implementing strict 6-role RBAC & Audit logging. |
| **Priority 2: Digital Twin EOC UI** | ✅ Complete | ✅ Complete | **DONE** | Palantir-style EOC command center, real-time tick engine, map layers, live HUD, and event ring buffer. |
| **Priority 3: Scenario Designer & Studio** | ✅ Complete | ✅ Complete | **DONE** | Disaster blueprint designer, multi-hazard presets, parameter overrides, and live injection. |
| **Priority 4: AI Decision Engine** | 🔄 In Progress | ✅ Complete | **IN PROGRESS** | Global Scipy LSA optimization (replacing Kuhn-Munkres), hard constraints, multi-criteria scoring, transaction-safe dispatch. |
| **Priority 5: Predictive AI Dashboard** | ✅ Complete | ✅ Complete | **DONE** | Multi-horizon (+5m, +15m, +30m, +60m) forecasting for casualties, hospital ICU overload, fleet shortages. |
| **Priority 6: Multi-Agent System (NEW)** | ⏳ Pending | ⏳ Pending | **PENDING** | 8 coordinating AI agents (Orchestrator, Commander, Dispatcher, Medic, Responder, Intel, PublicInfo, ScenarioDirector). |
| **Incident & Resource Management** | ✅ Complete | ✅ Complete | **DONE** | Spatial indexing, severity tagging, resource state machine (`ASSIGNED` ➔ `DISPATCHED` ➔ `EN_ROUTE` ➔ `ARRIVED`). |
| **Hospitals & Shelters** | ✅ Complete | ✅ Complete | **DONE** | Facility capacity, ICU occupancy, supply tracking, spatial proximity. |

---

## 🤖 Priority 6: Multi-Agent System Architecture (Upcoming)

The platform is transitioning to a **Multi-Agent System** where each operational role is paired with an AI agent. These agents coordinate through typed messages, share a global blackboard, and can operate under variable autonomy levels.

- **Human-in-the-Loop:** Admins assign roles. Agents function under specific Autonomy levels (OFF, ADVISE, SUPERVISED, AUTONOMOUS).
- **Core Agents:** Orchestrator (Coordinates), Commander (Strategic), Dispatcher (Tactical), Medic (Triage), Responder (Field Ops), Intel (Data), PublicInfo (Comms), ScenarioDirector (Simulations).
- **Agent API & Event Bus:** Agents communicate via an in-process bus and Redis streams, interacting through a unified Agent API.

---

## 🔮 Priority 5: Predictive AI Dashboard & Forecasting Intelligence

The **Predictive Intelligence Layer** translates live disaster telemetry and simulation state into actionable multi-horizon projections across **+5m, +15m, +30m, and +60m** horizons.

### Architecture
```text
                    DIGITAL TWIN
                         │
                         ▼
                  CURRENT STATE
                         │
                         ▼
              ┌─────────────────────┐
              │ Prediction Engine   │
              └──────────┬──────────┘
                         │
        ┌────────────────┼─────────────────┐
        ▼                ▼                 ▼
   Casualty         Hospital Load      Resource Demand
   Prediction       Prediction         Prediction
        │                │                 │
        └────────────────┼─────────────────┘
                         ▼
                 Risk Aggregation
                         │
                         ▼
                Predictive Analytics
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        REST API                WebSocket
```

---

## 🧠 Priority 4: AI Decision Intelligence Engine

The **AI Decision Engine** determines the mathematically optimal emergency response action given the disaster state, available resources, hospital capacities, weather, and road conditions. It uses `scipy.optimize.linear_sum_assignment` for global cost optimization.

### Architectural Pipeline
```text
       ┌───────────────────────────────┐
       │   Digital Twin / DB State     │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │     Candidate Generator       │
       │  (Route & ETA via OSRM)       │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │   Scoring & Optimization      │
       │ (Normalized Criteria / Solver)│
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │     Explainability Engine     │
       │ (Structured XAI + Ollama LLM) │
       └───────────────┬───────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │   Transaction-Safe Execution  │
       └───────────────────────────────┘
```

---

## 🏗️ Architecture & Technology Stack

### Core Technologies:
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10 compatible) with Pydantic v2 and SQLAlchemy 2.0.
- **Database**: PostgreSQL 15 + [PostGIS](https://postgis.net/) Extension.
- **Optimization & Math**: `scipy.optimize` LSA matching solver.
- **Routing Engine**: [OSRM](https://project-osrm.org/) API with automatic road-factored Haversine fallback.
- **AI / LLM Engine**: [Ollama](https://ollama.com/) running `llama3.2:3b`.
- **Frontend**: [React 18/19](https://reactjs.org/), [Vite](https://vitejs.dev/), [Leaflet](https://leafletjs.com/).
- **Messaging & Cache**: Redis 5+ and RabbitMQ.

---

## 🚀 Getting Started

### Prerequisites
- **Python**: `3.10`
- **Node.js**: `v18+` or `v20+`
- **PostgreSQL**: `15+` with `PostGIS` extension.
- **Ollama**: (Optional) running `llama3.2:3b`.

---

### 1. Database Setup
Create a PostgreSQL database named `rescuenet`:
```sql
CREATE DATABASE rescuenet;
\c rescuenet
CREATE EXTENSION IF NOT EXISTS postgis;
```

---

### 2. Backend Setup

1. **Activate Python environment & install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Copy `.env.example` to `.env` and set `SEED_ADMIN_PASSWORD`, `SEED_COMMANDER_PASSWORD`, etc.

3. **Apply Alembic Migrations**:
   ```bash
   alembic upgrade head
   ```

4. **Seed the database (Development Only)**:
   Ensure `ENVIRONMENT=development` and run:
   ```bash
   python seed_data.py
   ```

5. **Start FastAPI Backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   - Interactive Swagger API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### 3. Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   - Access the dashboard at [http://localhost:5173](http://localhost:5173)

---

## 🧪 Testing Suite & Quality Assurance

Run the test suite (requires `SECRET_KEY` in env):
```bash
cd backend
pytest -v
```

---

## 📄 License
This project is licensed under the MIT License.
