# Prediction results

The Prediction dashboard displays model results for 12 hours after the prediction
run. The intended cadence is one run per hour. This project does not yet include
a trained LSTM, inference program, or scheduled prediction job. Opening or
refreshing the dashboard does not run a model.

## Result file

Once a model is available, its producer on the Jetson must write
`data/predictions.json` inside the deployment directory. The gateway exposes the
validated latest batch through `GET /api/predictions`. There is no HTTP write
endpoint. The data directory is excluded from Git.

Each batch contains:

| Field | Meaning |
| --- | --- |
| `generated_at` | UTC timestamp of the completed prediction run, such as `2026-11-11T17:00:00Z` |
| `forecast_for` | UTC target timestamp, exactly 12 hours after `generated_at` |
| `model_version` | Nonempty model identifier, at most 120 characters |
| `values` | Object of measurement IDs and finite numeric predictions, or `null` when unavailable |

Supported measurement IDs preserve each probe's temperature separately:

| ID | Measurement | Unit |
| --- | --- | --- |
| `do` | Node 01 dissolved oxygen | mg/L |
| `orp` | Node 02 oxidation–reduction potential | mV |
| `temperature` | Node 01 DO probe temperature | °C |
| `temperature_orp` | Node 02 ORP probe temperature | °C |

Omitted keys and `null` values remain unavailable; they are never converted to
zero. Other sensor IDs are rejected until their integration defines units and
model inputs. Prediction values are model outputs, not measurements or verified
operating limits. The gateway validates their format, not model accuracy.

## Publish a completed batch

Write a temporary file in the same directory and replace the result atomically,
so the gateway never reads half a JSON document. This example belongs in the
future inference program; `outputs` must contain real model results.

```python
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path('/home/lihong/clam_factory_deployment')
target = root / 'data' / 'predictions.json'
target.parent.mkdir(parents=True, exist_ok=True)

completed = datetime.now(timezone.utc)
batch = {
    'generated_at': completed.isoformat(),
    'forecast_for': (completed + timedelta(hours=12)).isoformat(),
    'model_version': model_version,
    'values': outputs,
}
temporary = target.with_suffix('.tmp')
temporary.write_text(json.dumps(batch, allow_nan=False), encoding='utf-8')
os.replace(temporary, target)
```

Use one producer, running as the gateway's `lihong` user or with appropriate file
read permission. Preserve the previous completed batch if inference fails.
The timestamps must describe the actual model horizon; do not relabel a different
forecast as a 12-hour result. Schedule the producer hourly only after the model,
input window, missing-data rules, and inference command are available.

## API states

The response always includes `server_time` (Unix seconds), `horizon_hours: 12`,
`interval_hours: 1`, and `latest` (the validated batch or `null`).

| `status` | Meaning |
| --- | --- |
| `waiting` | No result file exists yet |
| `ready` | A valid batch was generated within the last 90 minutes |
| `stale` | The last valid batch is older than 90 minutes; retain its original timestamps |
| `error` | The file is unreadable, malformed, over 8 KiB, or fails validation; `latest` is `null` |

`ready` means that a batch is recent and structurally valid. It does not certify
forecast quality or prove that an hourly scheduler is running. Future generation
times, timestamps without UTC offsets, unknown measurement IDs, strings in place
of numbers, booleans, and nonfinite values are rejected. Browser polling only
checks for a completed batch; it is independent of hourly model execution.

After deploying changes to `gateway/app.py`, restart `clam-gateway`. Updating
`data/predictions.json` afterward requires no service restart.
