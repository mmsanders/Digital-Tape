/* Public discovery only. GitHub owns authentication and the approval mutation. */
'use strict';
(() => {
  const endpoint = 'https://api.github.com/repos/mmsanders/Digital-Tape/actions/runs?status=waiting&branch=main&per_page=100';
  let timer, busy = false;
  async function refreshApprovals() {
    clearTimeout(timer);
    if (busy || document.hidden) return;
    busy = true;
    const status = document.getElementById('approval-status');
    const links = document.getElementById('approval-runs');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(endpoint, {cache:'no-cache', signal:controller.signal});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      const data = await response.json();
      const runs = BusDashboard.waitingApprovals(data);
      links.replaceChildren();
      for (const run of runs) {
        const link = document.createElement('a');
        link.className = 'approval-button';
        link.href = run.url;
        link.textContent = 'Review approval in GitHub · run ' + run.id;
        const description = document.createElement('p');
        description.className = 'muted';
        description.textContent = run.title;
        links.append(link, description);
      }
      status.textContent = (runs.length ? runs.length + ' round/test run(s) waiting. Verify the round scope in GitHub before approving.' :
        'No waiting round/test runs found. This does not confirm that the approval environment is configured.') +
        (data.total_count > 100 ? ' Results limited to 100 runs; open the workflow for all runs.' : '') +
        ' Checked ' + new Date().toLocaleTimeString() + '.';
    } catch (error) {
      links.replaceChildren();
      status.textContent = 'Approval status unavailable (' + error.message + '). Open the approval workflow to check directly.';
    } finally {
      clearTimeout(timeout);
      busy = false;
      if (!document.hidden) timer = setTimeout(refreshApprovals, 60000);
    }
  }
  document.addEventListener('visibilitychange', () => { clearTimeout(timer); if (!document.hidden) refreshApprovals(); });
  refreshApprovals();
})();
