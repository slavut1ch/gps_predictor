import sys
import json
import torch
import torch.nn as nn
import numpy as np
import pandas as pd
import math

class LSTMDirection(nn.Module):
    def __init__(self, feat_dim, hidden=128, layers=3, dir_bins=36):
        super().__init__()
        self.lstm = nn.LSTM(feat_dim, hidden, layers, batch_first=True, dropout=0.2)
        self.fc = nn.Linear(hidden, dir_bins)
    def forward(self, x):
        _, (h, _) = self.lstm(x)
        return self.fc(h[-1])

def get_heading_angle(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

def get_angle_diff(a1, a2):
    d = abs(a1 - a2)
    return min(d, 360 - d)

def main():
    if len(sys.argv) < 2: return
    ckpt = torch.load("model.pt", map_location="cpu")
    model = LSTMDirection(ckpt["feat_dim"], 128, 3, ckpt["dir_bins"])
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    df = pd.read_csv(sys.argv[1])
    lats, lons, ts = df['lat'].values, df['lon'].values, df['unix'].values
    seq_len = ckpt["seq_len"]

    feats = []
    prev_speed, prev_br = None, None
    for j in range(len(lats)-1):
        d = math.sqrt(((lats[j+1]-lats[j])*111320)**2 + ((lons[j+1]-lons[j])*111320*math.cos(math.radians(lats[j])))**2)
        dt = max(1, int(ts[j+1]) - int(ts[j]))
        speed = d / dt
        br = get_heading_angle(lats[j], lons[j], lats[j+1], lons[j+1])
        acc = 0.0 if prev_speed is None else (speed - prev_speed) / dt
        curv = 0.0 if prev_br is None else get_angle_diff(prev_br, br)
        prev_speed, prev_br = speed, br
        ts_s, ts_c = math.sin(2*math.pi*(int(ts[j+1])%86400)/86400), math.cos(2*math.pi*(int(ts[j+1])%86400)/86400)
        feats.append([(lats[j+1]-lats[j])*111320, (lons[j+1]-lons[j])*111320*math.cos(math.radians(lats[j])), speed, acc, math.sin(math.radians(br)), math.cos(math.radians(br)), curv, ts_s, ts_c])

    x = torch.tensor([feats[-(seq_len):]], dtype=torch.float32)
    with torch.no_grad():
        probs = torch.softmax(model(x), dim=-1).numpy()[0]
        pred_bin = np.argmax(probs)
        pred_angle = (pred_bin + 0.5) * (360.0 / ckpt["dir_bins"])

    print(json.dumps({"pred_angle": float(pred_angle)}))

if __name__ == "__main__":
    main()