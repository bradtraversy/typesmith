'use strict';

const $ = id => document.getElementById(id);
let savedState = null;
let draft = null;
let selected = 0;
let dirty = false;
let pendingAction = false;
let polling = false;
let requestId = 0;
const replies = new Map();

window.nativeReply = (id, result) => {
  const reply = replies.get(id);
  if (!reply) return;
  replies.delete(id);
  result.ok ? reply.resolve(result.data) : reply.reject(new Error(result.error || 'The action could not be completed.'));
};

function native(action, payload = {}) {
  return new Promise((resolve, reject) => {
    if (!window.webkit?.messageHandlers?.typesmith) {
      reject(new Error('Open this panel in the TypeSmith Mac app.'));
      return;
    }
    const id = String(++requestId);
    replies.set(id, {resolve, reject});
    window.webkit.messageHandlers.typesmith.postMessage({id, action, ...payload});
  });
}

function notice(message = '', error = false) {
  $('notice').textContent = message;
  $('notice').hidden = !message;
  $('notice').classList.toggle('error', error);
}

function confirmAction(title, text, accept = 'Continue') {
  $('confirmTitle').textContent = title;
  $('confirmText').textContent = text;
  $('confirmAccept').textContent = accept;
  return new Promise(resolve => {
    const dialog = $('confirmDialog');
    const finish = value => {
      dialog.close();
      $('confirmCancel').onclick = null;
      $('confirmAccept').onclick = null;
      dialog.oncancel = null;
      resolve(value);
    };
    $('confirmCancel').onclick = () => finish(false);
    $('confirmAccept').onclick = () => finish(true);
    dialog.oncancel = event => { event.preventDefault(); finish(false); };
    dialog.showModal();
  });
}

function changed() {
  dirty = true;
  notice();
  renderList();
  renderControls();
  native('dirty', {value: true}).catch(() => {});
}

function renderList() {
  const root = $('steps');
  root.replaceChildren();
  if (!draft) return;
  $('stepCount').textContent = `${draft.steps.length} ${draft.steps.length === 1 ? 'step' : 'steps'}`;
  draft.steps.forEach((step, index) => {
    const button = document.createElement('button');
    button.className = 'step' + (index === selected ? ' selected' : '');
    button.setAttribute('aria-current', index === selected ? 'true' : 'false');
    button.setAttribute('aria-label', `Step ${index + 1}: ${step.title || 'Untitled step'}`);
    const number = document.createElement('span');
    number.className = 'step-number-badge'; number.textContent = index + 1;
    const copy = document.createElement('span'); copy.className = 'step-copy';
    const title = document.createElement('span'); title.className = 'step-title'; title.textContent = step.title || 'Untitled step';
    const meta = document.createElement('span'); meta.className = 'step-meta';
    meta.textContent = `${step.mode === 'block' ? 'Code block' : 'Command'}  /  ${step.speed || 0} chars/sec`;
    copy.append(title, meta); button.append(number, copy);
    const nextId = savedState?.project.steps[savedState.nextIndex]?.id;
    if (step.id === nextId) {
      const badge = document.createElement('span'); badge.className = 'next-badge'; badge.textContent = savedState.typing ? 'Typing' : 'Active'; button.append(badge);
    }
    button.disabled = Boolean(savedState?.typing) || pendingAction;
    button.onclick = () => {
      // Unsaved edits may not validate yet, so only move the editor until they are saved.
      if (dirty) { selected = index; renderList(); renderEditor(); }
      else perform('setNext', {index});
    };
    root.append(button);
  });
}

function renderControls() {
  const active = Boolean(savedState?.typing);
  document.querySelectorAll('.step').forEach(button => button.disabled = active || pendingAction);
  $('save').disabled = !dirty || active || pendingAction;
  $('saveCopy').disabled = !draft || active || pendingAction;
  $('open').disabled = active || pendingAction;
  $('add').disabled = active || pendingAction;
  ['stopMode', 'stepName', 'mode', 'speed', 'speedValue', 'source', 'recordingName'].forEach(id => $(id).disabled = active || pendingAction || !draft);
  ['reset', 'skip', 'setNext'].forEach(id => $(id).disabled = active || pendingAction || dirty || !draft);
  $('up').disabled = active || pendingAction || selected === 0;
  $('down').disabled = active || pendingAction || selected === (draft?.steps.length || 0) - 1;
  $('remove').disabled = active || pendingAction || (draft?.steps.length || 0) < 2;
  $('duplicate').disabled = active || pendingAction || !draft;
  $('stop').disabled = pendingAction && !active;
  $('saveState').textContent = dirty ? 'Unsaved changes' : 'Saved locally';
  $('saveState').classList.toggle('dirty', dirty);
  $('statusDot').classList.toggle('typing', active);
  if (savedState) {
    const next = savedState.project.steps[savedState.nextIndex];
    $('nextLabel').textContent = active ? 'Typing now' : savedState.resumeUncertain ? 'Resume unavailable. Clear partial text and reselect this step.' : dirty ? 'Save edits to update the active step' : 'Active for hotkey';
    $('nextStep').textContent = `${savedState.nextIndex + 1}. ${next.title}`;
  }
}

function renderSourceDetails() {
  const text = $('source').value;
  $('charCount').textContent = `${text.length.toLocaleString()} characters`;
  $('lineNumbers').textContent = Array.from({length: text.split('\n').length}, (_, i) => i + 1).join('\n');
  $('lineNumbers').scrollTop = $('source').scrollTop;
}

function renderEditor() {
  if (!draft) return;
  selected = Math.max(0, Math.min(selected, draft.steps.length - 1));
  const step = draft.steps[selected];
  $('stopMode').value = draft.stopMode || 'restart';
  $('stopHint').textContent = draft.stopMode === 'resume' ? 'Leave the cursor after the partial text. The next hotkey press continues there.' : 'Clear partial text before pressing the hotkey to start again.';
  $('stepNumber').textContent = `Step ${selected + 1} of ${draft.steps.length}`;
  $('editorTitle').textContent = step.title || 'Untitled step';
  $('stepName').value = step.title;
  $('mode').value = step.mode;
  $('speed').value = step.speed;
  $('speedValue').value = step.speed;
  $('source').value = step.text;
  $('sourceLabel').textContent = step.mode === 'block' ? 'Code block' : 'Command';
  $('modeHint').textContent = step.mode === 'block' ? 'Types the complete block' : 'You press Enter';
  $('codeNote').hidden = step.mode !== 'block';
  renderSourceDetails(); renderControls();
}

function receiveState(state, force = false) {
  const oldRevision = savedState?.revision;
  const oldPath = savedState?.path;
  const wasTyping = savedState?.typing;
  const oldNext = savedState?.nextIndex;
  if (force || !draft || (!dirty && (state.revision !== oldRevision || state.path !== oldPath))) {
    draft = structuredClone(state.project);
    selected = state.nextIndex;
    $('recordingName').value = draft.name;
    dirty = false;
    native('dirty', {value: false}).catch(() => {});
    savedState = state;
    renderList(); renderEditor();
  } else if (dirty && (state.revision !== oldRevision || state.path !== oldPath)) {
    notice('The saved recording changed elsewhere. Use Open to reload it before saving your edits.', true);
    savedState = {...savedState, typing: state.typing};
  } else {
    savedState = state;
  }
  if (force || oldNext !== state.nextIndex || wasTyping !== state.typing) renderList();
  renderControls();
}

async function perform(action, extra = {}) {
  if (pendingAction || (!savedState && action !== 'open')) return;
  pendingAction = true; renderControls(); notice();
  try {
    const result = await native(action, {path: savedState?.path, revision: savedState?.revision, ...extra});
    if (result?.cancelled) return;
    if (result?.project) receiveState(result, true);
    if (action === 'save') notice('Saved. The active step repeats until you select another.');
  } catch (error) { notice(error.message, true); }
  finally { pendingAction = false; renderControls(); }
}

$('stopMode').onchange = event => { draft.stopMode = event.target.value; changed(); renderEditor(); };
$('recordingName').oninput = event => { draft.name = event.target.value; changed(); };
$('stepName').oninput = event => { draft.steps[selected].title = event.target.value; $('editorTitle').textContent = event.target.value || 'Untitled step'; changed(); };
$('mode').onchange = event => { draft.steps[selected].mode = event.target.value; changed(); renderEditor(); };
for (const id of ['speed', 'speedValue']) $(id).oninput = event => {
  const value = Number(event.target.value);
  draft.steps[selected].speed = value;
  $(id === 'speed' ? 'speedValue' : 'speed').value = value;
  changed();
};
$('source').oninput = event => { draft.steps[selected].text = event.target.value; renderSourceDetails(); changed(); };
$('source').onscroll = () => { $('lineNumbers').scrollTop = $('source').scrollTop; };
$('source').onkeydown = event => {
  if (event.key === 'Tab' && !event.shiftKey && !event.metaKey && !event.ctrlKey && !event.altKey) {
    event.preventDefault();
    const input = event.target;
    input.setRangeText('\t', input.selectionStart, input.selectionEnd, 'end');
    input.dispatchEvent(new Event('input', {bubbles: true}));
  }
};
$('add').onclick = () => {
  draft.steps.push({id: crypto.randomUUID(), title: 'New step', mode: 'lines', text: '', speed: 120});
  selected = draft.steps.length - 1; changed(); renderEditor(); $('stepName').focus(); $('stepName').select();
};
$('duplicate').onclick = () => {
  const copy = structuredClone(draft.steps[selected]); copy.id = crypto.randomUUID(); copy.title += ' copy';
  draft.steps.splice(selected + 1, 0, copy); selected++; changed(); renderEditor();
};
for (const [id, offset] of [['up', -1], ['down', 1]]) $(id).onclick = () => {
  const step = draft.steps.splice(selected, 1)[0]; selected += offset; draft.steps.splice(selected, 0, step); changed(); renderEditor();
};
$('remove').onclick = async () => {
  if (await confirmAction('Remove this step?', `Remove “${draft.steps[selected].title}” from this recording?`, 'Remove step')) {
    draft.steps.splice(selected, 1); selected = Math.min(selected, draft.steps.length - 1); changed(); renderEditor();
  }
};
$('save').onclick = () => perform('save', {project: draft, index: selected});
$('saveCopy').onclick = () => perform('saveCopy', {project: draft, index: selected});
$('open').onclick = async () => {
  if (dirty && !await confirmAction('Open another recording?', 'Unsaved edits will be discarded after you choose a recording.', 'Choose recording')) return;
  perform('open');
};
$('setNext').onclick = () => perform('setNext', {index: selected});
$('reset').onclick = () => perform('reset');
$('skip').onclick = () => perform('skip');
$('stop').onclick = async () => {
  try { await native('stop'); notice(savedState?.project.stopMode === 'resume' ? 'Paused. Keep the cursor in place, then use the hotkey to continue.' : 'Stopped. Clear the partial text before restarting.'); }
  catch (error) { notice(error.message, true); }
};
$('liveSpeed').onclick = () => native('liveSpeed').catch(error => notice(error.message, true));
$('hide').onclick = async () => {
  if (dirty && !await confirmAction('Hide with unsaved changes?', 'The shortcut will use the last saved sequence.', 'Hide panel')) return;
  native('hide').catch(error => notice(error.message, true));
};
window.panelCommand = async command => {
  if (['save', 'open', 'saveCopy'].includes(command)) $(command).click();
  if (command === 'reload') {
    if (dirty && !await confirmAction('Reload this recording?', 'Unsaved edits will be discarded.', 'Reload')) return;
    try { receiveState(await native('state'), true); notice(); }
    catch (error) { notice(error.message, true); }
  }
};

async function poll() {
  if (polling || pendingAction) return;
  polling = true;
  try { receiveState(await native('state')); }
  catch (error) { notice(error.message, true); }
  finally { polling = false; }
}
poll();
setInterval(poll, 1200);
