import math
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split


# distance with curvature of the earth
def calc_distance_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def get_heading_angle(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    br = math.degrees(math.atan2(x, y))
    return (br + 360) % 360

def get_angle_diff(a1, a2):
    d = abs(a1 - a2)
    return min(d, 360 - d)

def time_sin_cos(ts):
    tod = (ts % 86400) / 86400
    return math.sin(2*math.pi*tod), math.cos(2*math.pi*tod)


def parse_gps(path: Path):
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}

    lat = cols.get("lat") or cols.get("latitude")
    lon = cols.get("lon") or cols.get("longitude")

    tcol = None
    for c in ["unix", "timestamp", "time", "datetime"]:
        if c in cols:
            tcol = cols[c]
            break

    ts = pd.to_numeric(df[tcol], errors="coerce")
    if ts.isna().all():
        ts = pd.to_datetime(df[tcol]).astype("int64") // 1_000_000_000

    df2 = pd.DataFrame({
        "lat": df[lat].astype(float),
        "lon": df[lon].astype(float),
        "ts": ts.astype(int)
    }).dropna().sort_values("ts").reset_index(drop=True)

    return df2


def load_tracks(csv_dir: Path):
    tracks = []
    for f in sorted(csv_dir.glob("*.csv")):
        try:
            df = parse_gps(f)
            if len(df) >= 30:
                tracks.append(df)
                print(f"[load] {f.name}, {len(df)} points")
        except:
            print(f"[skip] {f}")
    return tracks


def build_sequences(tracks, seq_len=20, dir_bins=36, min_turn_deg=5, keep_straight_frac=0.1, lookahead=5):

    X = []
    Y = []
    Meta = []

    for df in tracks:
        la = df.lat.values
        lo = df.lon.values
        ts = df.ts.values

        max_i = len(df) - seq_len - lookahead - 1

        for i in range(max_i):

            lat1 = la[i+seq_len-1]
            lon1 = lo[i+seq_len-1]

            lat2 = la[i+seq_len+lookahead]
            lon2 = lo[i+seq_len+lookahead]

            if calc_distance_meters(lat1, lon1, lat2, lon2) < 1.0:
                continue

            br_prev = get_heading_angle(la[i+seq_len-2], lo[i+seq_len-2], lat1, lon1)
            br_next = get_heading_angle(lat1, lon1, lat2, lon2)

            delta = get_angle_diff(br_prev, br_next)

            if delta < min_turn_deg and np.random.rand() > keep_straight_frac:
                continue

            feats = []

            prev_speed = None
            prev_br = None

            for j in range(i, i+seq_len):
                d = calc_distance_meters(la[j], lo[j], la[j+1], lo[j+1])
                dt = max(1, ts[j+1] - ts[j])
                speed = d / dt

                br = get_heading_angle(la[j], lo[j], la[j+1], lo[j+1])
                ts_s, ts_c = time_sin_cos(ts[j+1])

                # acceleration
                if prev_speed is None:
                    acc = 0.0
                else:
                    acc = (speed - prev_speed) / dt

                # curvature
                if prev_br is None:
                    curvature = 0.0
                else:
                    curvature = get_angle_diff(prev_br, br)

                prev_speed = speed
                prev_br = br

                feats.append([
                    (la[j+1]-la[j]) * 111320,
                    (lo[j+1]-lo[j]) * 111320 * math.cos(math.radians(la[j])),
                    speed,
                    acc,
                    math.sin(math.radians(br)),
                    math.cos(math.radians(br)),
                    curvature,
                    ts_s,
                    ts_c,
                ])

            X.append(np.array(feats, np.float32))
            Y.append(int((br_next / 360) * dir_bins) % dir_bins)
            Meta.append({"lat": lat1, "lon": lon1})

    print(f"\n[build] prepared {len(X)} samples\n")
    return X, Y, Meta


class GPSDataset(Dataset):
    def __init__(self, X, Y):
        self.X = [torch.tensor(x) for x in X]
        self.Y = torch.tensor(Y, dtype=torch.long)

    def __len__(self): return len(self.X)
    def __getitem__(self, i): return self.X[i], self.Y[i]


class LSTMDirection(nn.Module):
    def __init__(self, feat_dim, hidden=128, layers=3, dir_bins=36):
        super().__init__()
        self.lstm = nn.LSTM(feat_dim, hidden, layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden, dir_bins)

    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv_dir", required=True)
    ap.add_argument("--seq_len", type=int, default=20)
    ap.add_argument("--dir_bins", type=int, default=36)
    ap.add_argument("--lookahead", type=int, default=8)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", default="model.pt")
    args = ap.parse_args()

    tracks = load_tracks(Path(args.csv_dir))

    X, Y, _ = build_sequences(
        tracks,
        seq_len=args.seq_len,
        dir_bins=args.dir_bins,
        lookahead=args.lookahead
    )

    train_idx, val_idx = train_test_split(range(len(X)), test_size=0.2, random_state=42)

    train_ds = GPSDataset([X[i] for i in train_idx], [Y[i] for i in train_idx])
    val_ds   = GPSDataset([X[i] for i in val_idx], [Y[i] for i in val_idx])

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True)
    val_loader   = DataLoader(val_ds, batch_size=args.batch)

    feat_dim = train_ds[0][0].shape[-1]

    model = LSTMDirection(feat_dim, dir_bins=args.dir_bins).to(args.device)

    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    for ep in range(1, args.epochs+1):
        model.train()
        loss_sum = 0
        correct = 0

        for xb, yb in train_loader:
            xb = xb.to(args.device)
            yb = yb.to(args.device)

            opt.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            opt.step()

            loss_sum += loss.item() * len(yb)
            correct += (logits.argmax(1) == yb).sum().item()

        model.eval()
        val_corr = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(args.device)
                yb = yb.to(args.device)
                logits = model(xb)
                val_corr += (logits.argmax(1) == yb).sum().item()
        
        print(f"Epoch {ep}/{args.epochs}  loss={loss_sum/len(train_ds):.4f}  train={correct/len(train_ds)*100:.1f}%  val={val_corr/len(val_ds)*100:.1f}%", flush=True)

    torch.save({
        "state_dict": model.state_dict(),
        "feat_dim": feat_dim,
        "seq_len": args.seq_len,
        "dir_bins": args.dir_bins,
        "lookahead": args.lookahead
    }, args.out)


if __name__ == "__main__":
    main()
