const STATUS_LABELS = {
  checking: 'Checking backend',
  connected: 'Backend Connected',
  disconnected: 'Backend Disconnected',
};

export default function StatusIndicator({ status }) {
  return (
    <div className={`connection-status connection-status--${status}`} role="status">
      <span className="connection-status__dot" aria-hidden="true" />
      <span>{STATUS_LABELS[status] || STATUS_LABELS.checking}</span>
    </div>
  );
}