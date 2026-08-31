const socket = new WebSocket(`ws://${window.location.host}/ws/telemetry`);

socket.addEventListener('open', () => {
  console.log('AegisAgent telemetry socket connected');
});

socket.addEventListener('message', (event) => {
  const payload = JSON.parse(event.data);
  const container = document.getElementById('agents');
  const projectName = document.getElementById('project-name');

  projectName.textContent = `${payload.project} • ${payload.mode} • ${payload.status}`;

  const entries = Object.entries(payload.agents || {});
  container.innerHTML = entries
    .map(
      ([name, state]) => `
        <div class="card">
          <h3>${name}</h3>
          <div class="status">${state}</div>
        </div>
      `
    )
    .join('');
});

socket.addEventListener('close', () => {
  console.log('AegisAgent telemetry socket disconnected');
});
