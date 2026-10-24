import { mountScreen } from './screen.mjs';

// The same component binding is used by the production page and test-DOM adapter.
export async function mountApp(root, host) {
  const screen = mountScreen(root, {
    label: text => { host.set_label(text).catch(() => {}); },
    dropPaths: paths => { host.drop_paths(paths).catch(() => {}); },
    startOver: () => { host.start_over().catch(() => {}); },
    details: () => host.raw_details()
  });
  let disposed = false;
  const apply = view => { if (!disposed) screen.render(view); };
  apply(await host.snapshot());
  const unsubscribe = await host.subscribe(apply);
  return {
    dropPaths: paths => screen.dropPaths(paths),
    destroy() { disposed = true; unsubscribe(); screen.destroy(); }
  };
}

if (window.__TAURI__) {
  const { invoke } = window.__TAURI__.core;
  const { listen } = window.__TAURI__.event;
  const host = {
    snapshot: () => invoke('snapshot'),
    set_label: text => invoke('set_label', { text }),
    drop_paths: paths => invoke('drop_paths', { paths }),
    start_over: () => invoke('start_over'),
    raw_details: () => invoke('raw_details'),
    async subscribe(callback) {
      let arrivals = 0;
      const off = await listen('app-state', event => { arrivals++; callback(event.payload); });
      // Close the snapshot/subscription gap without replacing a newer event.
      const before = arrivals;
      const current = await invoke('snapshot');
      if (arrivals === before) callback(current);
      return off;
    }
  };
  mountApp(document.getElementById('app'), host).catch(error => {
    document.getElementById('app').textContent = `The app could not start. ${String(error)}`;
  });
}
