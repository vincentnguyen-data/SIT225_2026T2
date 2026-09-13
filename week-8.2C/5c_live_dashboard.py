from arduino_iot_cloud import ArduinoCloudClient
from datetime import datetime
from arduino_credentials import DEVICE_ID, SECRET_KEY

from dash import Dash, dcc, html, Input, Output, no_update
import plotly.graph_objects as go

from collections import deque
import threading
import csv
import os
import time


def create_smooth_live_dashboard(
    sample_queue,
    series_keys,
    series_names=None,
    update_interval_ms=250,
    max_points=200,
    title="Smooth Live Sensor Data"
):
    if series_names is None:
        series_names = series_keys

    app = Dash(__name__)

    figure = go.Figure()

    for name in series_names:
        figure.add_trace(
            go.Scatter(
                x=[],
                y=[],
                mode="lines",
                name=name
            )
        )

    figure.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Acceleration",
        uirevision="constant"
    )

    app.layout = html.Div([
        dcc.Graph(
            id="live-graph",
            figure=figure
        ),

        dcc.Interval(
            id="live-update",
            interval=update_interval_ms,
            n_intervals=0
        )
    ])

    @app.callback(
        Output("live-graph", "extendData"),
        Input("live-update", "n_intervals")
    )
    def update_graph(_):
        new_samples = []

        with queue_lock:
            while sample_queue:
                new_samples.append(sample_queue.popleft())

        if not new_samples:
            return no_update

        timestamps = [sample["timestamp"] for sample in new_samples]

        update_data = {
            "x": [timestamps for _ in series_keys],
            "y": [
                [sample[key] for sample in new_samples]
                for key in series_keys
            ]
        }

        trace_indices = list(range(len(series_keys)))

        return update_data, trace_indices, max_points

    return app


filename = "accelerometer_xyz.csv"

latest = {
    "x": None,
    "y": None,
    "z": None
}

sample_queue = deque()
queue_lock = threading.Lock()


if not os.path.exists(filename):
    with open(filename, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "x", "y", "z"])


def save_if_complete():
    if all(value is not None for value in latest.values()):
        timestamp = datetime.now()

        sample = {
            "timestamp": timestamp,
            "x": latest["x"],
            "y": latest["y"],
            "z": latest["z"]
        }

        with open(filename, "a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([
                timestamp.strftime("%Y-%m-%d %H:%M:%S.%f"),
                latest["x"],
                latest["y"],
                latest["z"]
            ])

        with queue_lock:
            sample_queue.append(sample)

        print(
            "New sample:",
            timestamp.strftime("%H:%M:%S.%f"),
            latest["x"],
            latest["y"],
            latest["z"]
        )

        latest["x"] = None
        latest["y"] = None
        latest["z"] = None


def on_accel_x_changed(client, value):
    latest["x"] = value
    save_if_complete()


def on_accel_y_changed(client, value):
    latest["y"] = value
    save_if_complete()


def on_accel_z_changed(client, value):
    latest["z"] = value
    save_if_complete()


client = ArduinoCloudClient(
    device_id=DEVICE_ID,
    username=DEVICE_ID,
    password=SECRET_KEY,
    sync_mode=True
)

client.register("accel_x", value=0.0, on_write=on_accel_x_changed)
client.register("accel_y", value=0.0, on_write=on_accel_y_changed)
client.register("accel_z", value=0.0, on_write=on_accel_z_changed)


def run_arduino():
    print("Connecting to Arduino Cloud...")
    client.start()
    print("Arduino Cloud CONNECTED!")

    while True:
        client.update()
        time.sleep(0.05)


app = create_smooth_live_dashboard(
    sample_queue=sample_queue,
    series_keys=["x", "y", "z"],
    series_names=[
        "Accelerometer X",
        "Accelerometer Y",
        "Accelerometer Z"
    ],
    update_interval_ms=250,
    max_points=200,
    title="Live Smartphone Accelerometer"
)


if __name__ == "__main__":
    arduino_thread = threading.Thread(
        target=run_arduino,
        daemon=True
    )

    arduino_thread.start()

    app.run(
        debug=False,
        port=8050
    )