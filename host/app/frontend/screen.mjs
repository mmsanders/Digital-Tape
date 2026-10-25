// Production presentation only. The host owns filesystem admission and job outcomes.
export function mountScreen(root, actions = {}) {
  const doc = root.ownerDocument;
  const make = (tag, id, text) => {
    const node = doc.createElement(tag);
    if (id) node.id = id;
    if (text) node.textContent = text;
    return node;
  };
  const screen = make('section', 'screen');
  screen.setAttribute('aria-label', 'Make a cartridge');
  const heading = make('h1', null, 'Make a cartridge');
  const drop = make('p', 'drop', 'Drop a folder of music here.');
  const caption = make('label', null, 'Cartridge label');
  caption.htmlFor = 'label';
  const label = make('input', 'label');
  label.type = 'text';
  label.autocomplete = 'off';
  label.spellcheck = false;
  const meterLabel = make('label', null, 'Music length');
  meterLabel.htmlFor = 'length';
  const meter = make('progress', 'length');
  meter.max = 1;
  const length = make('p', 'length-text');
  const message = make('p', 'message');
  message.setAttribute('role', 'status');
  const card = make('p', 'card');
  const makeButton = make('button', 'make', 'Make cartridge');
  makeButton.type = 'button';
  makeButton.disabled = true;
  const reset = make('button', 'reset');
  reset.type = 'button';
  const show = make('button', 'show-details', 'Show details');
  show.type = 'button';
  const details = make('pre', 'details');
  details.tabIndex = 0;
  details.style.userSelect = 'text';
  details.setAttribute('aria-label', 'Details');
  screen.append(heading, drop, caption, label, meterLabel, meter, length,
    message, card, makeButton, reset, show, details);
  root.replaceChildren(screen);
  let previousLabel = '';
  let serial = 0;
  let disposed = false;
  const encoder = new TextEncoder();
  const validText = text => {
    if (text.includes('\0') || encoder.encode(text).length > 32) return false;
    // Reject unpaired UTF-16 surrogates instead of silently replacing them in UTF-8.
    for (let i = 0; i < text.length; i++) {
      const c = text.charCodeAt(i);
      if (c >= 0xd800 && c <= 0xdbff) {
        const next = text.charCodeAt(++i);
        if (!(next >= 0xdc00 && next <= 0xdfff)) return false;
      } else if (c >= 0xdc00 && c <= 0xdfff) return false;
    }
    return true;
  };
  const empty = () => ({view: 'empty', checking: false, bar: 0,
    total_frames: 0, label: '', message: null, too_long: false,
    card_line: "Finding cards isn't part of this build yet.",
    make_enabled: false, details_available: false, card_details_available: false});
  function render(view, detailsText = '') {
    if (disposed) return;
    serial++;
    const state = view.checking ? 'Checking' : view.too_long || view.view === 'problem' || (['empty', 'ready'].includes(view.view) && !!view.message)
      ? 'Problem' : ({empty: 'Empty', ready: 'Ready', making: 'Making', done: 'Done'}[view.view] || 'Problem');
    screen.dataset.state = state;
    previousLabel = typeof view.label === 'string' ? view.label : '';
    label.value = previousLabel;
    const bar = state === 'Problem' && view.view === 'empty' ? null : view.bar;
    meter.hidden = state === 'Done' || (state !== 'Checking' && state !== 'Making' && !(typeof bar === 'number' && Number.isFinite(bar)));
    meterLabel.hidden = meter.hidden;
    meter.dataset.kind = state === 'Making' ? 'writing' : 'length';
    if (state === 'Checking') meter.removeAttribute('value');
    else if (typeof bar === 'number' && Number.isFinite(bar)) meter.value = Math.min(1, Math.max(0, bar));
    else meter.removeAttribute('value');
    meter.dataset.tooLong = String(!!view.too_long);
    meter.dataset.indeterminate = String(state === 'Checking');
    const frames = state === 'Empty' ? 0 : view.total_frames;
    if (Number.isSafeInteger(frames) && frames >= 0) {
      length.dataset.frames = String(frames);
      const seconds = Math.ceil(frames / 44100);
      length.textContent = `${Math.floor(seconds / 60)} min ${seconds % 60} s of 60 min`;
    } else {
      delete length.dataset.frames;
      length.textContent = '';
    }
    const defaults = {Checking: 'Checking the music…', Making: 'Writing the music…',
      Done: 'Your cartridge is ready. You can take the card out now.'};
    message.textContent = view.message ?? defaults[state] ?? '';
    card.textContent = view.card_line ?? '';
    reset.textContent = state === 'Done' ? 'Make another' : 'Start over';
    reset.hidden = !['Ready', 'Problem', 'Done'].includes(state);
    // INGEST details belong to a Problem; a card check's diagnostic is offered in any state.
    show.hidden = !((view.details_available && state === 'Problem') || view.card_details_available === true);
    details.textContent = typeof detailsText === 'string' ? detailsText : '';
    details.hidden = true;
    // This candidate has no production Make, discovery or elevation action.
    makeButton.disabled = true;
    label.disabled = state === 'Making';
  }
  const onInput = () => {
    const next = label.value;
    if (!validText(next)) { label.value = previousLabel; return; }
    previousLabel = next;
    actions.label?.(next);
  };
  const onReset = () => { render(empty()); actions.startOver?.(); };
  const onDetails = () => {
    details.hidden = false;
    const ticket = serial;
    const response = actions.details?.();
    if (response !== undefined) Promise.resolve(response).then(text => {
      if (!disposed && serial === ticket && typeof text === 'string') details.textContent = text;
    }).catch(() => {}); // Host supplies any authoritative error status.
  };
  label.addEventListener('input', onInput);
  reset.addEventListener('click', onReset);
  show.addEventListener('click', onDetails);
  render(empty());
  return {
    render,
    // Native shell calls this with the entire ordered path batch. The host
    // classifies filesystem objects atomically; presentation never guesses kinds.
    dropPaths(paths) {
      if (disposed || !Array.isArray(paths) || !paths.length ||
          paths.some(p => typeof p !== 'string' || !p.length || p.includes('\0'))) return;
      actions.dropPaths?.([...paths]);
    },
    destroy() {
      disposed = true;
      serial++;
      label.removeEventListener('input', onInput);
      reset.removeEventListener('click', onReset);
      show.removeEventListener('click', onDetails);
      screen.remove();
    }
  };
}
