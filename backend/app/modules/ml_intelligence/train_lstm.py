"""
AegisAI ML Intelligence — PyTorch LSTM Disaster Trajectory Training Script.

Trains deep recurrent LSTM network on 10,000 disaster sequences:
- 50 epochs, Adam optimizer (lr=1e-3), MSE loss
- 80/20 train/validation split
- Evaluates against Moving-Average baseline
- Serializes trained model weights to disaster_lstm.pt
"""

from pathlib import Path
from typing import cast
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

WEIGHTS_PATH = Path(__file__).parent / "disaster_lstm.pt"


class _LSTMNet(nn.Module):
    def __init__(self, input_size: int = 4, hidden_size: int = 64, num_layers: int = 2, output_size: int = 4):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last_step = out[:, -1, :]
        res = self.fc(last_step)
        assert isinstance(res, torch.Tensor)
        return cast(torch.Tensor, res)


def generate_synthetic_disaster_sequences(n_sequences: int = 10000, seq_len: int = 6, seed: int = 42):
    """
    Generate realistic multi-timestep disaster sequences:
    Features: [casualties, critical_patients, radius_meters, active_teams]
    Target: 4-horizon growth factor delta [5m, 15m, 30m, 60m]
    """
    np.random.seed(seed)
    X = np.zeros((n_sequences, seq_len, 4), dtype=np.float32)
    y = np.zeros((n_sequences, 4), dtype=np.float32)

    minutes = np.array([5.0, 15.0, 30.0, 60.0], dtype=np.float32)

    for i in range(n_sequences):
        # Initial conditions
        init_casualties = np.random.exponential(scale=10.0) + 1.0
        init_critical = init_casualties * np.random.uniform(0.1, 0.4)
        init_radius = np.random.uniform(80.0, 1500.0)
        teams = np.random.randint(1, 6)

        # Growth velocity and suppression factor from responders
        growth_rate = np.random.uniform(0.01, 0.05)
        suppression = min(0.6, teams * 0.08)
        net_rate = max(0.002, growth_rate - suppression)

        # Generate 6 consecutive past intervals
        for t in range(seq_len):
            time_factor = (t + 1) * 2.0
            cas = init_casualties * (1.0 + net_rate * time_factor) + np.random.normal(0, 0.5)
            crit = max(0.0, cas * np.random.uniform(0.15, 0.35))
            rad = init_radius * (1.0 + net_rate * time_factor * 0.6) + np.random.normal(0, 5.0)
            X[i, t] = [max(1.0, cas), crit, max(50.0, rad), float(teams)]

        # Ground truth future growth multipliers for +5m, +15m, +30m, +60m
        noise = np.random.normal(0, 0.01, size=4)
        targets = (net_rate * (minutes / 10.0)) + noise
        y[i] = np.maximum(0.01, targets)

    return X, y


def train_model():
    print("Generating 10,000 synthetic disaster sequences...")
    X, y = generate_synthetic_disaster_sequences(n_sequences=10000, seq_len=6)

    # 80/20 train/validation split
    n_train = 8000
    X_train, y_train = X[:n_train], y[:n_train]
    X_val, y_val = X[n_train:], y[n_train:]

    train_ds = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
    val_ds = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=128, shuffle=False)

    torch.manual_seed(42)
    model = _LSTMNet(input_size=4, hidden_size=64, num_layers=2, output_size=4)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    epochs = 50
    print(f"Beginning PyTorch LSTM training for {epochs} epochs...")

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss = 0.0
        for bx, by in train_loader:
            optimizer.zero_grad()
            preds = model(bx)
            loss = criterion(preds, by)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(bx)
        train_loss /= len(train_ds)

        if epoch % 10 == 0 or epoch == epochs:
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for bx, by in val_loader:
                    preds = model(bx)
                    loss = criterion(preds, by)
                    val_loss += loss.item() * len(bx)
            val_loss /= len(val_ds)
            print(f"Epoch {epoch:2d}/{epochs} - Train Loss (MSE): {train_loss:.6f} - Val Loss (MSE): {val_loss:.6f}")

    # Evaluate on Validation Set
    model.eval()
    all_preds = []
    all_targets = []
    with torch.no_grad():
        for bx, by in val_loader:
            preds = model(bx)
            all_preds.append(preds.numpy())
            all_targets.append(by.numpy())

    val_preds = np.vstack(all_preds)
    val_targets = np.vstack(all_targets)

    lstm_mse = float(np.mean((val_preds - val_targets) ** 2))
    lstm_mae = float(np.mean(np.abs(val_preds - val_targets)))

    # Compute Moving-Average Baseline on the sequences
    # Moving-average estimate: uses average linear growth of last 3 steps
    last_steps = X_val[:, -1, 0]  # last casualty step
    prev_steps = X_val[:, -3, 0]  # two steps before
    estimated_rate = np.maximum(0.005, (last_steps - prev_steps) / (2.0 * last_steps))
    minutes = np.array([5.0, 15.0, 30.0, 60.0], dtype=np.float32)
    ma_preds = estimated_rate[:, None] * (minutes[None, :] / 10.0)

    ma_mse = float(np.mean((ma_preds - val_targets) ** 2))
    ma_mae = float(np.mean(np.abs(ma_preds - val_targets)))

    print("\n================ EVALUATION RESULTS (20% Holdout) ================")
    print(f"PyTorch LSTM Model:        MSE = {lstm_mse:.6f}, MAE = {lstm_mae:.6f}")
    print(f"Moving-Average Baseline:   MSE = {ma_mse:.6f}, MAE = {ma_mae:.6f}")
    improvement = ((ma_mse - lstm_mse) / ma_mse) * 100.0
    print(f"LSTM Error Reduction vs Baseline: {improvement:.2f}%")
    print("===================================================================\n")

    # Save model weights
    torch.save(model.state_dict(), str(WEIGHTS_PATH))
    print(f"Saved trained weights successfully to: {WEIGHTS_PATH}")

    return {
        "lstm_mse": lstm_mse,
        "lstm_mae": lstm_mae,
        "ma_mse": ma_mse,
        "ma_mae": ma_mae,
        "improvement_pct": improvement,
    }


if __name__ == "__main__":
    train_model()
