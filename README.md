# GPS Next Move Prediction

LSTM-based neural network that predicts the next movement direction from GPS track history.

## Overview

1. **Training** - LSTM learns to predict movement direction from GPS point sequences
2. **Prediction** - model estimates the next bearing angle from the last 20 track points
3. **Map Matching** - predicted direction is snapped to the real road network via Mapbox

---

## Requirements

- **Docker**
- **Mapbox API token** - get one at [mapbox.com](https://mapbox.com)

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/slavut1ch/gps_predictor.git
cd gps_predictor
```

### 2. Create config files from samples

```bash
cp config.sample.php config.php
cp config.sample.py  config.py
```

**`config.php`** - set the Python path and minimum CSV count for training:
```php
<?php
define('PY',      '/opt/venv/bin/python3'); // use this exact path when running in Docker
define('MIN_CSV', 50);
?>
```

**`config.py`** - set your Mapbox token (required for map matching):
```python
MAPBOX_TOKEN_KEY = "pk.eyJ1Ijoi..."  # https://console.mapbox.com/account/access-tokens/
```

### 3. Build and run

```bash
docker build -t gps-predictor .

docker run -d \
  -p 8080:80 \
  -v $(pwd)/app/storage:/var/www/app/storage \
  --name gps \
  gps-predictor
```

Open in browser: `http://localhost:8080/app.html`

---

## Usage

### 1. Login
Enter any username - a user folder is created automatically.

### 2. Training
- Upload at least **50 CSV files** with GPS tracks
- Each file must contain columns: `unix` / `timestamp` / `time` / `datetime`, `lat`, `lon`
- Click **Start training** and wait for completion

### 3. Prediction
- Upload a CSV track
- Navigate with `←` `→` buttons or keyboard arrows
- **Red dot** - predicted next position (40m ahead)
- Enable **Map matching** to snap the prediction to the nearest road (**orange dot**)

### CSV format

```csv
unix,lat,lon
1708419600,48.1486,17.1077
1708419601,48.1487,17.1079
```

---

## API Endpoints

All requests go to `index.php` via `POST` with `action` field.

| Action | Parameters | Description |
|---|---|---|
| `login` | `user` | Creates user directory, returns model status and CSV count |
| `upload` | `user`, `files[]` | Uploads CSV training files |
| `train` | `user` | Runs `train.py`, saves `model.pt` |
| `predict` | `user`, `file`, `matching` | Runs `predict.py`, optionally `matching.py` |

**`predict` response:**
```json
{
  "pred_angle": 87.5,
  "match": {
    "status": "success",
    "lat": 52.4371234,
    "lon": 9.7481234,
    "angle": 85.2,
    "dist_m": 41.2,
    "angle_error": 2.3
  }
}
```

---

## Project structure

```
├── Dockerfile
├── requirements.txt
├── config.php              # PHP constants (PY path, MIN_CSV)
├── config.py               # Python config (Mapbox token)
├── config.sample.php       # Template
├── config.sample.py        # Template
├── php.ini                 # PHP settings
├── app/
│   ├── app.html            # Frontend - Leaflet.js map and controls
│   ├── index.php           # Backend API
│   └── storage/
│       └── {username}/
│           ├── csvs/       # Uploaded training CSV files
│           ├── model.pt    # Trained model
│           └── train.log   # Training log
└── scripts/
    ├── train.py            # LSTM model training
    ├── predict.py          # Prediction with saved model
    └── matching.py         # Map matching via Mapbox API
```

---

## Model architecture

LSTM with 3 layers and 128 hidden units. Input is a sequence of 20 GPS points, each represented by 9 features:

- Δlat, Δlon (movement in meters)
- Speed, acceleration
- sin/cos of bearing
- Track curvature
- sin/cos of time of day

Output is a classification into 36 direction bins (10° each).