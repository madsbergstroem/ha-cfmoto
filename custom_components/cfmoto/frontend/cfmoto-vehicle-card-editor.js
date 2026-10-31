/** Native visual editor for the CFMoto vehicle card's common options. */
import { labelsFor, normalizeConfig } from './cfmoto-vehicle-card.js';

const CARD_TYPE = 'cfmoto-vehicle-card-editor';

function odometerCandidates(states) {
  return Object.entries(states || {})
    .filter(([id]) => id.startsWith('sensor.') && id.endsWith('_odometer'))
    .sort(([a], [b]) => a.localeCompare(b));
}

export class CfMotoVehicleCardEditor extends (globalThis.HTMLElement ?? class {}) {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = normalizeConfig(config);
    this.render();
  }

  set hass(value) {
    this._hass = value;
    this.render();
  }

  emit(candidate) {
    const config = normalizeConfig(candidate);
    this.config = config;
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config }, bubbles: true, composed: true }));
    this.render();
  }

  field(text, input) {
    const label = document.createElement('label');
    label.append(document.createTextNode(text), input);
    return label;
  }

  render() {
    if (!this.config) return;
    const labels = labelsFor(this._hass?.language ?? 'en');
    const root = document.createElement('div');
    const style = document.createElement('style');
    style.textContent =
      ':host{display:block}label{display:flex;flex-direction:column;gap:6px;margin:12px 0;font-size:14px}input,select{font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:10px;min-width:0}.check{flex-direction:row;align-items:center}.check input{width:20px;height:20px}small{color:var(--secondary-text-color);line-height:1.5}p{color:var(--error-color)}';

    const select = document.createElement('select');
    const candidates = odometerCandidates(this._hass?.states);
    if (this.config.entity && !candidates.some(([id]) => id === this.config.entity)) {
      candidates.unshift([this.config.entity, this._hass?.states?.[this.config.entity]]);
    }
    if (candidates.length === 0) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = labels.no_entity;
      select.append(option);
    }
    for (const [id, state] of candidates) {
      const option = document.createElement('option');
      option.value = id;
      option.textContent = `${state?.attributes?.friendly_name ?? id} (${id})`;
      select.append(option);
    }
    select.value = this.config.entity ?? '';
    select.addEventListener('change', () => this.emit({ ...this.config, entity: select.value }));
    root.append(this.field(labels.editor_vehicle, select));

    const name = document.createElement('input');
    name.type = 'text';
    name.value = this.config.name ?? '';
    name.addEventListener('change', () => this.emit({ ...this.config, name: name.value }));
    root.append(this.field(labels.editor_name, name));

    const image = document.createElement('input');
    image.type = 'text';
    image.value = this.config.image ?? '';
    image.placeholder = '/cfmoto-static/cfmoto-450mt.png';
    image.addEventListener('change', () => this.emit({ ...this.config, image: image.value }));
    root.append(this.field(labels.editor_image, image));

    const switches = [
      ['show_metrics', labels.editor_metrics],
      ['show_presence', labels.editor_presence],
      ['tabs', labels.editor_tabs],
      ['map', labels.editor_map],
      ['details', labels.editor_details],
      ['show_background', labels.editor_background],
    ];
    for (const [key, text] of switches) {
      const row = document.createElement('label');
      row.className = 'check';
      const box = document.createElement('input');
      box.type = 'checkbox';
      box.checked = this.config[key] !== false;
      box.addEventListener('change', () => this.emit({ ...this.config, [key]: box.checked }));
      row.append(box, document.createTextNode(text));
      root.append(row);
    }

    const path = document.createElement('input');
    path.type = 'text';
    path.value = this.config.image_navigate ?? '';
    path.placeholder = '/lovelace/REPLACE_WITH_DETAILS_VIEW';
    path.addEventListener('change', () => this.emit({ ...this.config, image_navigate: path.value }));
    root.append(this.field(labels.editor_image_path, path));

    const note = document.createElement('small');
    note.textContent = labels.editor_note;
    root.append(note);

    this.shadowRoot.replaceChildren(style, root);
  }
}

if (globalThis.customElements && !customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, CfMotoVehicleCardEditor);
}
