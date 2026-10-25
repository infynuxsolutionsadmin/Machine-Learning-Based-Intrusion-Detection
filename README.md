# Machine Learning-Based Intrusion Detection and Trust-Aware Secure Routing in MANETs

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19.x-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-8.x-646CFF.svg?style=flat&logo=vite)](https://vitejs.dev)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.x-EE4C2C.svg?style=flat&logo=pytorch)](https://pytorch.org)
[![NS-3](https://img.shields.io/badge/NS--3-v3.41-orange.svg?style=flat)](https://www.nsnam.org)
[![Tailwind CSS](https://img.shields.io/badge/TailwindCSS-v4.x-38B2AC.svg?style=flat&logo=tailwind-css)](https://tailwindcss.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?style=flat&logo=python)](https://www.python.org)

An end-to-end decentralized framework combining **Network Simulation (NS-3)**, **Cross-Layer Feature Extraction**, **Classical Machine Learning (Random Forest, XGBoost, CatBoost, SVM, MLP)**, **Deep Learning (Temporal LSTM Trust Modeling)**, **Federated Learning (FedAvg)**, and **Location-Aided Trust-Aware Routing** to detect and neutralize Black Hole attacks in Mobile Ad-hoc Networks (MANETs).

---

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Problem Statement and Objectives](#2-problem-statement-and-objectives)
- [3. Key Features](#3-key-features)
- [4. Technology Stack](#4-technology-stack)
- [5. System Architecture and Workflow](#5-system-architecture-and-workflow)
- [6. Project Folder Structure](#6-project-folder-structure)
- [7. Prerequisites and System Requirements](#7-prerequisites-and-system-requirements)
- [8. Installation and Setup](#8-installation-and-setup)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [WSL2 / NS-3 Configuration](#wsl2--ns-3-configuration)
- [9. Environment Variables and Configuration](#9-environment-variables-and-configuration)
- [10. How to Run the Project Locally](#10-how-to-run-the-project-locally)
- [11. Machine Learning and Trust Pipeline](#11-machine-learning-and-trust-pipeline)
  - [Classical Machine Learning Models](#classical-machine-learning-models)
  - [LSTM Trust Evaluation](#lstm-trust-evaluation)
  - [Federated Learning (FedAvg)](#federated-learning-fedavg)
- [12. Network Simulation & Secure Routing (NS-3)](#12-network-simulation--secure-routing-ns-3)
  - [Attack Mechanism](#attack-mechanism)
  - [Two-Pass Trust Rerouting and LAR Filtering](#two-pass-trust-rerouting-and-lar-filtering)
- [13. API Documentation](#13-api-documentation)
- [14. Frontend Dashboard Walkthrough](#14-frontend-dashboard-walkthrough)
- [15. Verification and Testing](#15-verification-and-testing)
- [16. Troubleshooting and Common Errors](#16-troubleshooting-and-common-errors)
- [17. Future Enhancements](#17-future-enhancements)
- [18. Authors and Credits](#18-authors-and-credits)

---

## 1. Project Overview

Mobile Ad-hoc Networks (MANETs) are autonomous, infrastructure-less collections of mobile nodes communicating over wireless links. Due to dynamic topology changes, decentralized architecture, and open wireless mediums, MANETs are susceptible to routing-layer attacks, specifically **Black Hole attacks**.

This project provides a comprehensive security solution:
1. **Simulates Realistic MANET Behavior**: Uses NS-3.41 to model mobile ad-hoc topologies with 802.11b Wi-Fi, Random Waypoint mobility, AODV routing, and radio energy depletion.
2. **Multi-Model Intrusion Detection**: Employs both **Classical Supervised ML** (`Random Forest`, `XGBoost`, `CatBoost`, `SVM`, `MLP`) and a **Deep Recurrent Architecture** (`TrustLSTM`) to detect anomalies across cross-layer telemetry.
3. **Decentralized Privacy with Federated Learning**: Aggregates model updates across multiple distributed client nodes using Federated Averaging (`FedAvg`), preserving data privacy.
4. **Adaptive Route Recovery & Node Isolation**: Dynamically blacklists malicious nodes and applies a **Location-Aided Routing (LAR) Request Zone** constraint to guarantee traffic reaches destinations via verified safe paths.
5. **Interactive Operations Dashboard**: A React 19 + Tailwind CSS v4 dashboard providing live simulation execution, network topology visualization, model performance metrics, route recovery analysis, and energy evaluation.

---

## 2. Problem Statement and Objectives

### Problem Statement
In traditional AODV (Ad hoc On-Demand Distance Vector) routing, intermediate nodes advertise routes to a destination by responding with Route Reply (RREP) packets. A malicious node executing a **Black Hole attack** exploits this by:
- Intercepting Route Request (RREQ) packets.
- Fabricating a high sequence number (e.g., `65535`) and minimum hop count (`1`) to falsely claim the freshest route.
- Intercepting and silently dropping all unicast data packets, degrading Packet Delivery Ratio (PDR) to near zero.

### Core Objectives
- **Accurate Detection**: Accurately classify normal vs. malicious nodes using cross-layer behavioral attributes (packet forwarding ratios, control message frequency, drop rates).
- **Temporal Trust Scoring**: Track node trustworthiness continuously over time using recurrent neural networks (LSTM) to handle intermittent or colluding attacks.
- **Privacy-Preserving Training**: Train models collaboratively across nodes without centralizing raw traffic data using Federated Learning.
- **Autonomous Route Recovery**: Re-run routing protocols with automated interface-down constraints and dynamic trust files to bypass malicious actors.
- **Real-Time Observability**: Provide full visibility into packet delivery ratio (PDR), mean latency, throughput, energy consumption, and hop-by-hop route traces.

---

## 3. Key Features

- **Dynamic Two-Pass Simulation Engine**:
  - **Pass 1**: Executes baseline or attack-injected traffic, recording FlowMonitor XML, ASCII IP routing traces (`.tr`), and per-node behavior CSVs.
  - **Pass 2**: Injects dynamically generated trust predictions into NS-3 to enforce interface isolation and compute recovered routing paths.
- **Cross-Layer Feature Extraction**:
  - Gathers telemetry from Physical, MAC, and Network layers (`rx`, `fw`, `drop`, `drop_ratio`, `control_message_frequency`, `network_avg_pdr`, `network_avg_delay`).
- **5 Classical ML Classifiers**:
  - Pre-trained and dynamically callable models: `RandomForest`, `XGBoost`, `CatBoost`, `SVM`, and `MLP` with standardized feature scaling and RFECV feature selection.
- **Deep Learning Trust Predictor**:
  - PyTorch-based sequential `TrustLSTM` evaluating sliding windows (sequence length = 5) of forwarding rates and ratios (`rx_rate`, `fw_rate`, `drop_rate`, `fw_ratio`).
- **Federated Learning Server**:
  - Multi-round client coordination with local training, weight aggregation, and loss/accuracy tracking.
- **Geographic Request Zone (LAR Filter)**:
  - Constrains route discovery within a spatial boundary defined between source and destination coordinates to prevent route hijacking outside safe operational corridors.
- **Energy Depletion Tracking**:
  - Tracks initial energy, remaining energy, consumed energy, and residual percentage per node using NS-3's `BasicEnergySource` and `WifiRadioEnergyModel`.
- **Modern Full-Stack Dashboard**:
  - Real-time React 19 interface with topology graph positioning, interactive metrics comparison, route comparison badges, and live log polling.

---

## 4. Technology Stack

### Backend
| Technology | Version / Purpose |
| :--- | :--- |
| **Python** | `3.10+` Core runtime |
| **FastAPI** | High-performance asynchronous REST API framework |
| **Uvicorn** | ASGI server for serving the FastAPI application |
| **Pydantic** | Request validation, payload typing, and response models |
| **PyTorch** | Deep Learning engine for `TrustLSTM` and Federated Learning |
| **Scikit-Learn** | Data preprocessing, scalers (`StandardScaler`), ML evaluations |
| **XGBoost / CatBoost** | Gradient boosted decision tree classifiers |
| **Pandas / NumPy** | Numerical computing, feature engineering, and tabular parsing |
| **Joblib** | Model serialization and artifact persistence |

### Network Simulator
| Technology | Details |
| :--- | :--- |
| **NS-3 (ns-allinone-3.41)** | Discrete-event network simulator executing within WSL2 Ubuntu |
| **Routing Protocol** | AODV (`ns3::aodv::RoutingProtocol`) enhanced with Blacklist logic |
| **Wi-Fi Standard** | IEEE 802.11b Ad-hoc (`ns3::AdhocWifiMac`, `ns3::YansWifiPhy`) |
| **Mobility Models** | `RandomWaypointMobilityModel` (relays), `ConstantPositionMobilityModel` (source/dest) |
| **Energy Model** | `ns3::BasicEnergySource` (100J default) + `ns3::WifiRadioEnergyModel` |
| **Flow Monitoring** | `ns3::FlowMonitor` capturing throughput, delay, lost packets, and PDR |

### Frontend
| Technology | Version / Purpose |
| :--- | :--- |
| **React** | `19.2.8` Component-based user interface |
| **Vite** | `8.3.0` Next-generation frontend build tool and dev server |
| **Tailwind CSS** | `4.3.3` Utility-first modern responsive styling |
| **React Router DOM**| `7.18.4` Client-side single-page routing |
| **Lucide React** | `1.47.0` High-quality UI iconography |
| **Recharts** | `3.10.1` Interactive performance charts and metric comparisons |
| **Oxlint** | `1.81.0` High-speed JavaScript/JSX code linter |

---

## 5. System Architecture and Workflow

```mermaid
flowchart TD
    subgraph Frontend["React 19 + Vite Frontend (Port 5173)"]
        UI_Dash["Dashboard (Overview & Quick Run)"]
        UI_Sim["Simulation Control (/simulation)"]
        UI_Topo["Network Topology (/network)"]
        UI_ML["ML Detection & Metrics (/ml-detection)"]
        UI_Prev["Prevention & Isolation (/prevention)"]
        UI_Rec["Route Recovery (/route-recovery)"]
        UI_Perf["Performance Metrics (/performance)"]
    end

    subgraph Backend["FastAPI Backend (Port 8000)"]
        API["FastAPI REST Endpoints (app/main.py)"]
        SimRunner["Simulation Runner (simulation_runner.py)"]
        TrustSvc["Trust Service (trust_service.py)"]
        RouteSvc["Routing Service (routing_service.py)"]
        ResultSvc["Results Service (results_service.py)"]
    end

    subgraph Simulation["WSL2 Ubuntu Subsystem (NS-3.41)"]
        NS3_Pass1["Pass 1: NS-3 Simulation (manet-sim.cc)\n- Injects Black Hole Attack\n- Captures XML, Trace CSV, Route TR"]
        NS3_Pass2["Pass 2: Trust-Aware Rerouting\n- Enforces --trustFile Blacklist\n- Applies LAR Request Zone\n- Reroutes Traffic Safely"]
    end

    subgraph Intelligence["Machine Learning & Trust Engine"]
        CrossLayer["CrossLayerExtractor (app/features/extractor.py)"]
        ClassML["5 Classical Classifiers (RF, XGB, CatBoost, SVM, MLP)"]
        LSTM["TrustLSTM Predictor (ml/predict_trust.py)"]
        FL["Federated Learning Server (fl_server.py)"]
    end

    UI_Sim -->|POST /api/simulation/run| API
    API --> SimRunner
    SimRunner -->|WSL2 CLI Call| NS3_Pass1
    NS3_Pass1 -->|Flowmon XML + Trace CSV| CrossLayer
    CrossLayer --> ClassML
    NS3_Pass1 -->|Per-Node Telemetry| LSTM
    LSTM -->|lstm_pred.csv (Trust Predictions)| SimRunner
    LSTM --> FL
    SimRunner -->|WSL2 CLI Call with --trustFile| NS3_Pass2
    NS3_Pass2 -->|Clean Route TR + XML| ResultSvc
    ResultSvc --> API
    RouteSvc --> API
    TrustSvc --> API
    API --> Frontend
```

---

## 6. Project Folder Structure

```
ML_MANET/
├── ML_backend/                     # FastAPI Backend & ML / Simulation Engine
│   ├── app/
│   │   ├── api/                    # API route definitions and models
│   │   ├── features/               # Cross-layer telemetry extractors
│   │   │   ├── extractor.py        # CrossLayerExtractor combining Phy, MAC, Network
│   │   │   ├── mac.py              # MAC layer feature extraction interface
│   │   │   ├── network.py          # Network layer metrics (drop ratios, frequencies)
│   │   │   └── physical.py         # Physical layer telemetry interface
│   │   ├── ml/                     # ML training, feature selection, and inference
│   │   │   ├── feature_selection.py# RFECV and variance threshold utilities
│   │   │   ├── models.py           # Classifier loader and hyperparameter mapping
│   │   │   ├── predict.py          # MLPredictor production inference pipeline
│   │   │   ├── preprocessing.py    # DataPreprocessor and scaler persistence
│   │   │   └── train.py            # Offline training script for 5 classical models
│   │   ├── models/                 # Model state storage
│   │   ├── services/               # Core business and simulation services
│   │   │   ├── results_service.py  # Parser for baseline and dynamic flow metrics
│   │   │   ├── routing_service.py  # Hop-by-hop route JSON parsing and validation
│   │   │   ├── simulation_runner.py# WSL2 NS-3 runner, 2-pass orchestrator, locks
│   │   │   └── trust_service.py    # Trust aggregation and dynamic trust analysis
│   │   ├── simulation/
│   │   │   └── parser.py           # NS3Parser for FlowMonitor XML and trace files
│   │   ├── utils/                  # Helper utilities and data formatters
│   │   └── main.py                 # FastAPI application root and endpoint handlers
│   ├── data/                       # Raw and processed datasets
│   ├── federated_learning/         # Federated Learning pipeline
│   │   ├── federated_global_model.pth # Saved global PyTorch LSTM model weights
│   │   ├── fl_metrics.json         # Round-by-round client evaluation logs
│   │   └── fl_server.py            # Multi-client Federated Averaging coordinator
│   ├── ml/                         # Standalone LSTM training & inference
│   │   ├── generate_dataset.py     # Script to generate trust datasets
│   │   ├── predict_trust.py        # CLI for TrustLSTM inference on trace CSVs
│   │   ├── train_lstm.py           # Training script for sequence TrustLSTM
│   │   └── trace_seed*.csv         # Simulation trace records used for training
│   ├── models/
│   │   └── baseline/               # Serialized baseline models & artifacts
│   │       ├── CatBoost.pkl        # Pre-trained CatBoost model
│   │       ├── MLP.pkl             # Pre-trained Multi-Layer Perceptron model
│   │       ├── RandomForest.pkl    # Pre-trained Random Forest model
│   │       ├── SVM.pkl             # Pre-trained Support Vector Machine model
│   │       ├── XGBoost.pkl         # Pre-trained XGBoost model
│   │       ├── scaler.pkl          # Scikit-learn StandardScaler
│   │       ├── experiment_metadata.json # Accuracy, precision, recall, confusion matrix
│   │       └── selected_features.json   # Selected features list (rx, control frequency)
│   ├── simulation/                 # NS-3 C++ source and Python trace parsers
│   │   ├── basic_manet_simulation.cc # NS-3 C++ simulation source code
│   │   ├── parse_results.py        # Parses FlowMonitor XML into summary CSV
│   │   ├── parse_route.py          # Extracts hop-by-hop nodes from ASCII routing trace
│   │   ├── find_seed.py            # Deterministic seed finder utility
│   │   └── results/                # Baseline & dynamic simulation outputs
│   ├── lstm_metrics.json           # Standalone LSTM performance evaluation metrics
│   ├── lstm_scaler.pkl             # Serialized scaler for LSTM rate inputs
│   ├── lstm_trust_model.pth        # Trained PyTorch TrustLSTM model weights
│   ├── trust_dataset.csv           # Ground truth dataset with labeled node metrics
│   ├── requirements.txt            # Python dependencies
│   ├── run_sim.sh                  # Bash helper script for manual WSL NS-3 execution
│   └── run_tests.py                # Automated endpoint test suite
│
├── ML_frontend/                    # React 19 + Vite Dashboard
│   ├── public/                     # Static assets
│   ├── src/
│   │   ├── components/layout/      # Layout components
│   │   │   ├── Navbar.jsx          # Header navigation bar with route title
│   │   │   ├── PageWrapper.jsx     # Main responsive page frame
│   │   │   └── Sidebar.jsx         # Sidebar navigation with active indicators
│   │   ├── pages/                  # Dashboard page views
│   │   │   ├── Dashboard.jsx       # Consolidated operations overview
│   │   │   ├── Simulation.jsx      # NS-3 parameter form & live execution
│   │   │   ├── NetworkTopology.jsx # Visual topology layout and node status
│   │   │   ├── MLDetection.jsx     # ML classifier metrics & confusion matrix
│   │   │   ├── Prevention.jsx      # Node isolation and detection comparison
│   │   │   ├── RouteRecovery.jsx   # Before vs. after routing path comparisons
│   │   │   └── PerformanceMetrics.jsx # PDR, delay, throughput, and energy analysis
│   │   ├── router/
│   │   │   └── AppRoutes.jsx       # React Router route registry
│   │   ├── services/
│   │   │   └── apiService.js       # Centralized fetch wrapper for backend endpoints
│   │   ├── App.css                 # Global styling overrides
│   │   ├── App.jsx                 # Application shell
│   │   ├── index.css               # Tailwind CSS entrypoint
│   │   └── main.jsx                # React DOM render entry
│   ├── package.json                # Frontend package dependencies & scripts
│   ├── vite.config.js              # Vite configuration with Tailwind CSS plugin
│   └── .oxlintrc.json              # Oxlint linting rules configuration
│
├── audit.py                        # Inspection script for serialized model files
├── test_sim.py                     # Headless Python test script for simulation runner
├── validate.py                     # Offline validation script for ML feature schemas
└── verify.py                       # Inspection script for scaler and model feature counts
```

---

## 7. Prerequisites and System Requirements

### Host Operating System
- **Windows 10 / 11** (64-bit) with WSL2 enabled.

### Software Prerequisites
1. **Python 3.10+**: Installed on Windows host.
2. **Node.js 18+ and npm**: Installed on Windows host.
3. **WSL2 (Ubuntu)**: Installed with a configured user (e.g., `kumar`).
4. **NS-3 (v3.41)**: Installed inside WSL Ubuntu at `/home/<user>/MANET/ns-3/ns-allinone-3.41/ns-3.41`.
   - Built with C++17 support, FlowMonitor, AODV, and Energy modules enabled.

---

## 8. Installation and Setup

### Backend Setup

1. Open PowerShell or Command Prompt on the Windows host.
2. Navigate to the `ML_backend` directory:
   ```powershell
   cd ML_backend
   ```
3. Create and activate a Python virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   ```
4. Install all required dependencies:
   ```powershell
   pip install -r requirements.txt
   pip install torch
   ```

### Frontend Setup

1. Open a new terminal on the Windows host.
2. Navigate to the `ML_frontend` directory:
   ```powershell
   cd ML_frontend
   ```
3. Install frontend dependencies:
   ```powershell
   npm install
   ```

### WSL2 / NS-3 Configuration

The backend executes NS-3 commands inside WSL2 via `wsl -d Ubuntu -u <username> -- /bin/bash -lc "<command>"`.

1. Ensure NS-3.41 is extracted and built in your WSL Ubuntu home directory:
   ```bash
   # Inside WSL Ubuntu
   cd ~/MANET/ns-3/ns-allinone-3.41/ns-3.41
   ./ns3 configure --build-profile=default --enable-examples --enable-tests
   ./ns3 build
   ```
2. Verify paths in `ML_backend/app/services/simulation_runner.py`:
   - Line 67: `NS3_DIR_WSL = "/home/<username>/MANET/ns-3/ns-allinone-3.41/ns-3.41"`
   - Line 68: `NS3_BIN_WSL = f"{NS3_DIR_WSL}/build/scratch/manet-sim/ns3.41-manet-sim-default"`
   - Line 304: `["wsl", "-d", "Ubuntu", "-u", "<username>", ...]`

---

## 9. Environment Variables and Configuration

### Frontend Configuration
The frontend automatically defaults to `http://127.0.0.1:8000`. To customize the backend connection URL, create a `.env` file inside `ML_frontend/`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Backend Configuration
The backend uses default localhost configurations without requiring mandatory `.env` secrets. CORS is explicitly preconfigured in `app/main.py` for:
- `http://localhost:5173`
- `http://127.0.0.1:5173`

---

## 10. How to Run the Project Locally

To run the complete system, keep both the backend and frontend servers running in separate terminals.

### Step 1: Start the Backend Server

```powershell
# In terminal 1 (ML_backend)
cd ML_backend
.\venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
*The FastAPI backend will start at `http://127.0.0.1:8000`. Interactive OpenAPI documentation will be available at `http://127.0.0.1:8000/docs`.*

### Step 2: Start the Frontend Application

```powershell
# In terminal 2 (ML_frontend)
cd ML_frontend
npm run dev
```
*The React dashboard will start at `http://localhost:5173`.*

---

## 11. Machine Learning and Trust Pipeline

### Classical Machine Learning Models
Cross-layer telemetry parsed from FlowMonitor and routing traces is passed through a standardized `DataPreprocessor` and evaluated across five supervised models saved in `models/baseline/`:

| Model | Accuracy | Precision | Recall | F1-Score | Key Hyperparameters / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Random Forest** | 100.0% | 1.000 | 1.000 | 1.000 | `n_estimators=100`, balanced class weighting |
| **XGBoost** | 100.0% | 1.000 | 1.000 | 1.000 | Gradient boosted trees with log-loss objective |
| **CatBoost** | 100.0% | 1.000 | 1.000 | 1.000 | Categorical gradient boosting |
| **SVM** | 90.0% | 0.500 | 1.000 | 0.667 | Radial Basis Function (RBF) kernel |
| **MLP** | 90.0% | 0.500 | 1.000 | 0.667 | Multi-layer Perceptron neural classifier |

**Selected Model Features**:
- `rx`: Number of packets received.
- `control_message_frequency`: Routing control overhead frequency.

### LSTM Trust Evaluation
Nodes can act maliciously intermittently. The `TrustLSTM` model tracks sequential behavior over sliding time windows (`SEQ_LENGTH = 5`):
- **Architecture**:
  - `nn.LSTM(input_size=4, hidden_size=32, num_layers=1, batch_first=True, dropout=0.2)`
  - `nn.Linear(32, 16)` $\rightarrow$ `nn.ReLU()`
  - `nn.Linear(16, 1)` (Binary classification: 0 = Normal, 1 = Malicious)
- **Input Features**: `rx_rate`, `fw_rate`, `drop_rate`, `fw_ratio`
- **Output**: Trust score $\in [0.0, 1.0]$ and binary prediction. Nodes falling below threshold (`0.5`) are flagged as malicious.

### Federated Learning (FedAvg)
To preserve node privacy and simulate decentralized security:
- **Server**: `ML_backend/federated_learning/fl_server.py`
- **Clients**: 3 simulated ad-hoc cluster clients.
- **Aggregation**: Federated Averaging (`FedAvg`) over 5 global rounds.
- **Output**: Generates `federated_global_model.pth` and records convergence stats in `fl_metrics.json`.

---

## 12. Network Simulation & Secure Routing (NS-3)

### Attack Mechanism
In `basic_manet_simulation.cc`, Black Hole nodes are designated via `--maliciousNodes="<IDs>"`. When triggered:
- The node responds to all incoming RREQ packets with an inflated destination sequence number (`65535`) and hop count `1`.
- Any unicast packet routed through this node is silently dropped in `RouteInput()`.

### Two-Pass Trust Rerouting and LAR Filtering
When an attack simulation is triggered:
1. **Pass 1 (Attack Execution)**: NS-3 runs with the attacker active. Telemetry is collected and sent to `TrustLSTM`.
2. **Trust Analysis & Blacklist Formulation**: Flagged nodes are added to `lstm_pred.csv` and scheduled for dynamic blacklisting in Pass 2.
3. **Pass 2 (Trust-Aware Rerouting)**:
   - NS-3 re-executes with `--trustFile=lstm_pred.csv`.
   - At scheduled timestamps, NS-3 calls `ScheduleBlacklist()`, bringing the malicious node's interface down (`ipv4->SetDown(1)`) and calling `aodv->BlacklistNode(malIp)` on all other nodes.
   - **LAR Request Zone**: `ApplyLARFilter()` computes a bounding box between source and destination coordinates with a margin of $0.5 \times \text{simArea}$. Nodes located outside the Request Zone are restricted from relaying RREQs, preventing detours through unsafe areas.
   - AODV rediscovers an alternative, safe multi-hop path from source to destination.

---

## 13. API Documentation

### System & Health Endpoints

#### `GET /api/health`
Returns system health status.
```json
{
  "status": "healthy",
  "service": "MANET Trust-Aware Routing Backend"
}
```

---

### Simulation Control Endpoints

#### `POST /api/simulation/run`
Executes an NS-3 dynamic simulation run.
- **Request Body**:
  ```json
  {
    "nNodes": 8,
    "sourceNode": 0,
    "destinationNode": 7,
    "attackEnabled": true,
    "maliciousNodes": [4],
    "seed": 42,
    "simArea": 300.0,
    "demoTopology": false
  }
  ```
- **Response**:
  ```json
  {
    "run_id": "20261025_113000_a1b2c3d4_8nodes_attack4",
    "nNodes": 8,
    "status": "completed",
    "duration_seconds": 18.4
  }
  ```

#### `GET /api/simulation/status`
Returns the status and configuration of the latest simulation.
```json
{
  "status": "completed",
  "run_id": "20261025_113000_a1b2c3d4_8nodes_attack4",
  "nNodes": 8,
  "sourceNode": 0,
  "destinationNode": 7,
  "attackEnabled": true,
  "maliciousNodes": [4]
}
```

#### `GET /api/network/nodes`
Returns node identifiers, assigned IP addresses, roles (`Source`, `Destination`, `Relay`), operational statuses (`normal`, `malicious`), topology coordinates, and active link edges.

---

### Machine Learning & Trust Endpoints

#### `GET /api/ml/metrics`
Returns performance evaluation metrics for the classical ML classifiers.

#### `GET /api/ml/features`
Returns the list of features selected via RFECV (`["rx", "control_message_frequency"]`).

#### `GET /api/ml/models`
Returns available model names: `["RandomForest", "XGBoost", "CatBoost", "SVM", "MLP"]`.

#### `GET /api/trust/dynamic`
Returns trust evaluation scores scoped to the current dynamic simulation run, including per-node LSTM trust scores, forwarding rates, drop counts, and predicted malicious classifications.

---

### Routing & Prevention Endpoints

#### `GET /api/routing/path`
Returns the actual hop-by-hop routing path parsed directly from the NS-3 ASCII routing trace.
```json
{
  "run_id": "20261025_113000_a1b2c3d4_8nodes_attack4",
  "route_available": true,
  "destination_reached": true,
  "hops": [
    { "node_id": 0, "ip": "10.1.1.1" },
    { "node_id": 2, "ip": "10.1.1.3" },
    { "node_id": 7, "ip": "10.1.1.8" }
  ],
  "hop_count": 2
}
```

#### `GET /api/prevention/summary`
Returns isolation status, detected low-trust nodes, original vs. recovered routes, and recovery success status.

#### `GET /api/metrics/comparison`
Returns comparative flow metrics between baseline/recovered traffic and attack traffic, including PDR drop percentage, mean delay, throughput, and residual node energy.

---

### Federated Learning Endpoints

#### `GET /api/fl/status`
Returns FL training status, number of connected clients, and completed rounds.

#### `GET /api/fl/rounds`
Returns round-by-round global loss, global accuracy, and individual client metrics.

#### `GET /api/fl/clients`
Returns performance statistics for each client participating in the latest FL round.

---

## 14. Frontend Dashboard Walkthrough

| Route | Page | Purpose & Displayed Information |
| :--- | :--- | :--- |
| `/` | **Dashboard** | Central operations center: displays system health, active simulation summary, detection badges, quick-run simulation controls, and key metric cards. |
| `/simulation` | **Simulation Control** | Interactive parameter configuration (Node count, simulation time, attacker IDs) with live execution progress and pipeline stage indicators. |
| `/network` | **Network Topology** | Topological layout rendering of all nodes, displaying source, destination, intermediate relays, detected attackers, and active communication edges. |
| `/ml-detection` | **ML Detection** | Classical classifier accuracy, precision, recall, and F1 comparisons alongside dynamic per-node LSTM trust score distributions. |
| `/prevention` | **Prevention** | Audit of detected low-trust nodes vs. ground truth attacker nodes, interface teardown verification, and isolation confirmation. |
| `/route-recovery` | **Route Recovery** | Before vs. after routing comparison showing the compromised path under attack vs. the safe recovered path avoiding malicious nodes. |
| `/performance` | **Performance Metrics** | Quantitative comparison of Packet Delivery Ratio (PDR), Mean Latency, Throughput (Kbps/Mbps), Packet Loss, and Residual Battery Energy. |

---

## 15. Verification and Testing

### 1. Headless Simulation Test
Run the headless simulation validation script from the project root:
```powershell
python test_sim.py
```
*Validates the NS-3 execution pipeline, parameter normalization, and dynamic simulation results.*

### 2. ML Schema and Predictor Validation
Verify that the dataset schema and model predictions match expected feature inputs:
```powershell
python validate.py
```
*Tests feature extraction across Physical, MAC, and Network layers, verifies scaler alignment, and executes predictions across all five classical models.*

### 3. Model and Scaler Integrity Audit
Audit the serialized `.pkl` files and verify input feature dimensions:
```powershell
python audit.py
python verify.py
```

### 4. Automated Backend Endpoint Testing
With the FastAPI server running on port 8000, execute the end-to-end endpoint tests:
```powershell
cd ML_backend
python run_tests.py
python test_phase3.py
python test_phase4.py
```

### 5. Frontend Code Quality Check
To lint the React codebase using Oxlint:
```powershell
cd ML_frontend
npm run lint
```

---

## 16. Troubleshooting and Common Errors

### 1. "NS-3 exited with code 1" or "Command not found"
- **Cause**: WSL2 Ubuntu is not running, or NS-3 is not compiled in the expected directory.
- **Solution**:
  1. Open WSL terminal: `wsl -d Ubuntu`
  2. Navigate to your NS-3 path: `cd ~/MANET/ns-3/ns-allinone-3.41/ns-3.41`
  3. Rebuild the scratch target: `./ns3 build`

### 2. "CORS Error" or "Failed to fetch" on Frontend
- **Cause**: The FastAPI backend is not running or running on an unexpected port.
- **Solution**: Ensure Uvicorn is active on `http://127.0.0.1:8000`. Check `app/main.py` to confirm `http://localhost:5173` is listed in `allow_origins`.

### 3. "Scaler missing" or "Model not found"
- **Cause**: Model artifacts in `ML_backend/models/baseline/` are missing or paths are misconfigured.
- **Solution**: Run `python audit.py` from the project root to inspect the model directory.

### 4. "Another simulation is already running"
- **Cause**: Concurrency lock (`_sim_lock`) in `simulation_runner.py` is held by a long-running NS-3 process.
- **Solution**: Wait for the active simulation to complete (default timeout is 300 seconds), or restart the Uvicorn server to reset in-memory lock states.

---

## 17. Future Enhancements

- **Support for Additional Attacks**: Extend simulation to Gray Hole (selective dropping), Sybil, and Wormhole attacks.
- **Mobile Edge Computing (MEC) Integration**: Offload heavy LSTM sequence training to decentralized edge cluster heads.
- **Dynamic Energy Harvesting**: Integrate energy replenishment models (solar/RF harvesting) into the node battery lifecycle.
- **Multi-Radio & 5G-NR V2X Simulation**: Expand physical-layer simulations to modern cellular vehicle-to-everything (C-V2X) standards.

---

## 18. Authors and Credits

- **Repository**: [Machine-Learning-Based-Intrusion-Detection](https://github.com/infynuxsolutionsadmin/Machine-Learning-Based-Intrusion-Detection)
- **Primary Contributor**: Sskumar05 (`sshathiskumar54@gmail.com`)
- **Institution / Organization**: Infynux Solutions
- **License**: Research & Educational Use
