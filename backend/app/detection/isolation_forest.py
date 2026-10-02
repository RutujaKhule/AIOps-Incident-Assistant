from sklearn.ensemble import IsolationForest

from backend.app.detection import config


FEATURES = (
    "cpu_percent",
    "memory_percent",
    "disk_percent",
    "network_bytes_sent",
    "network_bytes_received",
)


def is_anomalous(
    history,
    minimum_samples=config.ISOLATION_FOREST_MIN_SAMPLES,
    contamination=config.ISOLATION_FOREST_CONTAMINATION,
    random_state=config.ISOLATION_FOREST_RANDOM_STATE,
):
    """Train on prior samples and score the newest sample when history is sufficient.

    `minimum_samples` prior metrics are required; the final item is the sample
    being checked and is not included in training.
    """
    if len(history) <= minimum_samples:
        return False

    ordered_history = sorted(history, key=lambda metric: metric["timestamp"])
    training_samples = ordered_history[:-1]
    sample_to_check = ordered_history[-1]

    training_data = [[float(sample[field]) for field in FEATURES] for sample in training_samples]
    current_data = [[float(sample_to_check[field]) for field in FEATURES]]

    model = IsolationForest(contamination=contamination, random_state=random_state)
    model.fit(training_data)
    return model.predict(current_data)[0] == -1