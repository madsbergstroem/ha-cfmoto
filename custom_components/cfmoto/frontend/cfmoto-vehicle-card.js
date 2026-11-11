/** CFMoto vehicle card. Renders existing HA entities; no cloud calls of its own. */
import './cfmoto-vehicle-card-editor.js';

const CARD_TYPE = 'cfmoto-vehicle-card';
const DEFAULT_IMAGE = '/cfmoto-static/cfmoto-450mt.png';

/** Entity suffixes published by the integration, resolved inside the same device. */
const SUFFIX = {
  odometer: '_odometer',
  range: '_range',
  battery: '_battery_voltage',
  fuel: '_fuel_level',
  fuel_text: '_fuel_level_display',
  month: '_ride_mileage_this_month',
  riding_time: '_riding_time_this_month',
  avg_speed: '_average_speed',
  gsm: '_gsm_signal',
  ignition: '_ignition',
  tbox: '_t_box_online',
  last_update: '_last_update',
  speed: '_speed',
  vehicle_online: '_vehicle_online',
  seat_lock: '_seat_lock',
  steering_lock: '_steering_lock',
  fuel_lock: '_fuel_lock',
  battery_lock: '_battery_lock',
};

/** Button entities published by the BLE control platform, resolved by suffix. */
const CONTROL_KEYS = Object.freeze(['power_on', 'power_off', 'unlock', 'lock', 'horn']);

/** Controls shown in the bottom row: key, icon, label key. */
const CONTROLS = Object.freeze([
  ['power', 'power', 'power'],
  ['unlock', 'lock-open-variant-outline', 'unlock'],
  ['lock', 'lock-outline', 'lock'],
  ['horn', 'bullhorn-outline', 'horn'],
]);

const LABELS = {
  de: {
    eyebrow: 'CFMoto',
    range: 'Reichweite',
    fuel: 'Tank',
    odometer: 'Kilometer',
    month: 'Diesen Monat',
    battery: 'Bordspannung',
    avg_speed: 'Ø Tempo',
    online: 'Online',
    offline: 'Offline',
    ignition: 'Zündung',
    ignition_on: 'Zündung an',
    ignition_off: 'Zündung aus',
    state_on: 'An',
    state_off: 'Aus',
    ready: 'Bereit',
    home: 'Zuhause',
    away: 'Unterwegs',
    tbox: 'T-Box',
    tbox_off: 'T-Box offline',
    updated: 'aktualisiert',
    riding_time: 'Fahrzeit',
    gsm: 'Signal',
    last_update: 'Letzte Daten',
    speed: 'Tempo',
    vehicle_online: 'Fahrzeug online',
    seat_lock: 'Sitzbank',
    steering_lock: 'Lenkschloss',
    fuel_lock: 'Tankdeckel',
    battery_lock: 'Batterieschloss',
    vehicle_image: 'Fahrzeugbild',
    unavailable: 'Keine Daten',
    no_entity: 'Keine CFMoto-Entität gefunden',
    tab_overview: 'Übersicht',
    tab_map: 'Karte',
    tab_details: 'Details',
    power: 'Zündung',
    unlock: 'Aufschließen',
    lock: 'Zusperren',
    horn: 'Hupe',
    confirm_power: 'Zündung schalten?',
    confirm_unlock: 'Fahrzeug aufschließen?',
    action_error: 'Aktion fehlgeschlagen.',
    map_placeholder: 'Kartenkarte ist noch nicht geladen.',
    now: 'gerade eben',
    minutes: 'vor {n} Min',
    hours: 'vor {n} Std',
    days: 'vor {n} Tagen',
    editor_vehicle: 'Fahrzeug-Entität',
    editor_name: 'Titel (optional)',
    editor_image: 'Bild-URL (optional)',
    editor_image_path: 'Klick aufs Bild öffnet',
    editor_metrics: 'Kennzahlen anzeigen',
    editor_presence: 'Standort & Status anzeigen',
    editor_tabs: 'Tabs anzeigen',
    editor_map: 'Karten-Tab',
    editor_details: 'Details-Tab',
    editor_background: 'Hintergrundbild',
    editor_note: 'Tabs aus = nur die Übersicht ohne Tab-Leiste.',
  },
  en: {
    eyebrow: 'CFMoto',
    range: 'Range',
    fuel: 'Fuel',
    odometer: 'Odometer',
    month: 'This month',
    battery: 'Battery',
    avg_speed: 'Avg speed',
    online: 'Online',
    offline: 'Offline',
    ignition: 'Ignition',
    ignition_on: 'Ignition on',
    ignition_off: 'Ignition off',
    state_on: 'On',
    state_off: 'Off',
    ready: 'Ready',
    home: 'Home',
    away: 'Away',
    tbox: 'T-Box',
    tbox_off: 'T-Box offline',
    updated: 'updated',
    riding_time: 'Riding time',
    gsm: 'Signal',
    last_update: 'Last data',
    speed: 'Speed',
    vehicle_online: 'Vehicle online',
    seat_lock: 'Seat',
    steering_lock: 'Steering lock',
    fuel_lock: 'Fuel cap',
    battery_lock: 'Battery lock',
    vehicle_image: 'Vehicle image',
    unavailable: 'No data',
    no_entity: 'No CFMoto entity found',
    tab_overview: 'Overview',
    tab_map: 'Map',
    tab_details: 'Details',
    power: 'Power',
    unlock: 'Unlock',
    lock: 'Lock',
    horn: 'Horn',
    confirm_power: 'Switch the ignition?',
    confirm_unlock: 'Unlock the bike?',
    action_error: 'Action failed.',
    map_placeholder: 'Map card is not loaded yet.',
    now: 'just now',
    minutes: '{n} min ago',
    hours: '{n} h ago',
    days: '{n} d ago',
    editor_vehicle: 'Vehicle entity',
    editor_name: 'Title (optional)',
    editor_image: 'Image URL (optional)',
    editor_image_path: 'Clicking the image opens',
    editor_metrics: 'Show metrics',
    editor_presence: 'Show location & status',
    editor_tabs: 'Show tabs',
    editor_map: 'Map tab',
    editor_details: 'Details tab',
    editor_background: 'Background image',
    editor_note: 'Tabs off = overview only, no tab bar.',
  },
};

/** key, icon, label key, value kind */
const DETAIL_ROWS = Object.freeze([
  ['fuel_text', 'gas-station', 'fuel', 'text'],
  ['riding_time', 'timer-outline', 'riding_time', 'duration'],
  ['gsm', 'signal', 'gsm', 'number'],
  ['ignition', 'key-variant', 'ignition', 'onoff'],
  ['tbox', 'access-point', 'tbox', 'online'],
  ['last_update', 'clock-outline', 'last_update', 'ago'],
  ['speed', 'speedometer', 'speed', 'number'],
  ['vehicle_online', 'lan-connect', 'vehicle_online', 'online'],
  ['seat_lock', 'seat', 'seat_lock', 'onoff'],
  ['steering_lock', 'steering', 'steering_lock', 'onoff'],
  ['fuel_lock', 'gas-station', 'fuel_lock', 'onoff'],
  ['battery_lock', 'battery', 'battery_lock', 'onoff'],
]);

export function labelsFor(language) {
  return (language || 'en').toLowerCase().startsWith('de') ? LABELS.de : LABELS.en;
}

export function normalizeConfig(config) {
  const result = { ...(config ?? {}) };
  for (const key of ['name', 'image', 'image_navigate']) {
    if (typeof result[key] === 'string') {
      const trimmed = result[key].trim();
      if (trimmed) result[key] = trimmed; else delete result[key];
    } else if (result[key] !== undefined) {
      delete result[key];
    }
  }
  if (typeof result.entity === 'string') result.entity = result.entity.trim();
  return result;
}

export function element(tag, text = '', className = '') {
  const result = document.createElement(tag);
  if (text !== '') result.textContent = String(text);
  if (className) result.className = className;
  return result;
}

function icon(name) {
  const result = document.createElement('ha-icon');
  result.setAttribute('icon', `mdi:${name}`);
  result.setAttribute('aria-hidden', 'true');
  return result;
}

export function usable(state) {
  return Boolean(state) && !['unavailable', 'unknown'].includes(state.state);
}

export function number(state) {
  const value = Number.parseFloat(state?.state);
  return Number.isFinite(value) ? value : null;
}

/** All entity ids that belong to the same device as the configured entity. */
export function deviceEntityIds(hass, entityId) {
  const all = Object.keys(hass?.states || {});
  const deviceId = hass?.entities?.[entityId]?.device_id;
  if (!deviceId) return all;
  return all.filter((id) => hass.entities?.[id]?.device_id === deviceId);
}

export function pick(ids, suffix) {
  const matches = ids.filter((id) => id.endsWith(suffix));
  matches.sort((a, b) => a.length - b.length);
  return matches[0];
}

export function resolveEntities(hass, entityId) {
  const ids = deviceEntityIds(hass, entityId);
  const suffixes = Object.values(SUFFIX);
  const result = {};
  for (const [key, suffix] of Object.entries(SUFFIX)) {
    // `_speed` must not resolve to `*_average_speed`: skip ids that end in a longer known suffix.
    const longer = suffixes.filter((other) => other.length > suffix.length && other.endsWith(suffix));
    result[key] = pick(ids.filter((id) => !longer.some((other) => id.endsWith(other))), suffix);
  }
  result.location = ids.find((id) => id.startsWith('device_tracker.'));
  for (const key of CONTROL_KEYS) result[key] = pick(ids.filter((id) => id.startsWith('button.')), `_${key}`);
  return result;
}

export function stubConfig(hass) {
  const states = hass?.states || {};
  const entity =
    Object.keys(states).find((id) => id.startsWith('sensor.') && id.endsWith('_odometer')) ||
    Object.keys(states).find((id) => id.startsWith('sensor.') && id.includes('450mt'));
  return { type: `custom:${CARD_TYPE}`, entity: entity || '' };
}

/** Seconds into a compact h/min string. */
export function formatDuration(seconds, language) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  if (hours === 0) return `${minutes} min`;
  return (language || 'en').toLowerCase().startsWith('de')
    ? `${hours} Std ${minutes} min`
    : `${hours} h ${minutes} min`;
}

/** Relative age of a timestamp, using the labels of the given language. */
export function relativeTime(value, labels, now = Date.now()) {
  const stamp = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(stamp.getTime())) return '—';
  const minutes = Math.round((now - stamp.getTime()) / 60000);
  if (minutes < 1) return labels.now;
  if (minutes < 60) return labels.minutes.replace('{n}', String(minutes));
  const hours = Math.round(minutes / 60);
  if (hours < 24) return labels.hours.replace('{n}', String(hours));
  return labels.days.replace('{n}', String(Math.round(hours / 24)));
}

const CSS = `
:host{display:block;container-type:inline-size}*{box-sizing:border-box}
ha-card{position:relative;isolation:isolate;display:block;overflow:hidden;border:1px solid var(--divider-color);border-radius:20px;background:var(--card-background-color);color:var(--primary-text-color)}
.header,.tabs,.panel,.controls,.error{position:relative;z-index:1}
button{font:inherit}.header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px 16px 0}
.eyebrow{margin:0 0 2px;color:var(--secondary-text-color);font-size:9px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}
h2{margin:0;font-size:18px;font-weight:650;letter-spacing:-.025em;line-height:1.2;overflow-wrap:anywhere}
.status{display:inline-flex;align-items:center;gap:5px;flex:none;border-radius:999px;padding:4px 9px;background:color-mix(in srgb,var(--success-color,#4ade80) 13%,transparent);color:var(--success-color,#4ade80);font-size:10.5px;font-weight:650}
.status::before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}
.status.riding{color:var(--warning-color,#f59e0b);background:color-mix(in srgb,var(--warning-color,#f59e0b) 13%,transparent)}
.status.off{color:var(--secondary-text-color);background:color-mix(in srgb,var(--secondary-text-color) 10%,transparent)}
.tabs{display:flex;gap:2px;margin:10px 12px 0;padding:3px;border-radius:999px;background:color-mix(in srgb,var(--secondary-text-color) 14%,var(--card-background-color))}
.tab{flex:1 1 0;min-width:0;padding:6px 8px;border:0;border-radius:999px;background:transparent;color:var(--secondary-text-color);font-size:11px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.tab[aria-selected="true"]{background:color-mix(in srgb,var(--primary-color) 22%,var(--card-background-color));color:var(--primary-text-color)}
.panel[hidden]{display:none}
.hero{display:grid;grid-template-columns:112px minmax(0,1fr);align-items:center;gap:6px;min-height:210px;padding:4px 16px 0}
.readout{display:flex;flex-direction:column;align-items:center;min-width:0}
.readout .value{display:flex;align-items:baseline;gap:3px;font-size:32px;font-weight:700;letter-spacing:-.055em;line-height:1}
.readout .value small{margin-bottom:3px;font-size:13px;font-weight:600;letter-spacing:0}
.readout .label{margin-top:5px;color:var(--secondary-text-color);font-size:10px}
.chip{display:inline-flex;align-items:center;gap:4px;margin-top:8px;border-radius:999px;padding:4px 9px;background:color-mix(in srgb,var(--secondary-text-color) 10%,transparent);color:var(--secondary-text-color);font-size:10.5px;font-weight:600;white-space:nowrap}
.chip ha-icon{--mdc-icon-size:13px}
.vehicle{display:flex;align-items:center;justify-content:center;width:100%;height:194px;min-width:0;padding:0;border:0;border-radius:18px;background:radial-gradient(ellipse at 50% 65%,color-mix(in srgb,var(--primary-color) 12%,transparent),transparent 70%);color:var(--primary-color);cursor:pointer}
.vehicle img{display:block;width:100%;height:190px;object-fit:contain;filter:drop-shadow(0 14px 12px rgb(0 0 0 / .22))}
.vehicle ha-icon{--mdc-icon-size:64px;opacity:.5}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:8px 16px 10px}
.metric{display:flex;flex-direction:column;align-items:flex-start;min-width:0;min-height:52px;padding:8px;border:0;border-radius:13px;background:color-mix(in srgb,var(--secondary-text-color) 9%,var(--card-background-color));color:var(--primary-text-color);text-align:left;cursor:pointer}
.metric ha-icon{margin-bottom:5px;color:var(--secondary-text-color);--mdc-icon-size:15px}
.metric .value{display:block;max-width:100%;overflow:hidden;font-size:13px;font-weight:650;letter-spacing:-.02em;text-overflow:ellipsis;white-space:nowrap}
.metric .label{display:block;max-width:100%;margin-top:2px;overflow:hidden;color:var(--secondary-text-color);font-size:9px;text-overflow:ellipsis;white-space:nowrap}
.metric:disabled{cursor:default;opacity:.58}
.presence{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 16px 11px;color:var(--secondary-text-color);font-size:11px}
.presence ha-icon{--mdc-icon-size:15px}
.presence span+span::before{content:"·";margin-right:6px}
.map{height:210px;margin:8px 12px 10px;border-radius:14px;overflow:hidden;background:color-mix(in srgb,var(--secondary-text-color) 8%,var(--card-background-color))}
.map hui-map-card{display:block;height:100%}.map-note{margin:0;padding:14px;color:var(--secondary-text-color);font-size:11.5px;line-height:1.5}
.details{margin:8px 12px 10px;border-radius:14px;overflow:hidden;background:color-mix(in srgb,var(--secondary-text-color) 8%,var(--card-background-color))}
.row{display:flex;align-items:center;gap:8px;width:100%;min-width:0;padding:9px 11px;border:0;border-bottom:1px solid color-mix(in srgb,var(--divider-color) 65%,transparent);background:transparent;color:var(--primary-text-color);font-size:12px;text-align:left;cursor:pointer}
.row:last-child{border-bottom:0}.row ha-icon{flex:none;--mdc-icon-size:15px;color:var(--secondary-text-color)}
.row-label{flex:1 1 auto;min-width:0;overflow:hidden;color:var(--secondary-text-color);text-overflow:ellipsis;white-space:nowrap}
.row-value{flex:none;font-weight:650;letter-spacing:-.01em;white-space:nowrap}.row:disabled{cursor:default;opacity:.5}
.controls{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--divider-color)}
.control{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-width:0;min-height:52px;padding:6px 4px;border:0;border-right:1px solid var(--divider-color);background:transparent;color:var(--primary-text-color);font-size:10px;cursor:pointer}
.control:last-child{border-right:0}.control ha-icon{--mdc-icon-size:18px;color:var(--primary-color)}
.control span{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.control:disabled{cursor:default;opacity:.42}.control.busy{opacity:.6}
.error{margin:0;padding:9px 16px;background:color-mix(in srgb,var(--error-color) 9%,transparent);color:var(--error-color);font-size:11.5px;line-height:1.4}
button:focus-visible{outline:2px solid var(--primary-color);outline-offset:-3px}
@media(prefers-reduced-motion:no-preference){.metric,.tab,.row,.control{transition:background .16s ease}.metric:hover,.row:hover,.control:hover{background:color-mix(in srgb,var(--primary-color) 8%,transparent)}}
@container(max-width:430px){.hero{grid-template-columns:100px minmax(0,1fr);padding-inline:12px}.readout .value{font-size:26px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));padding-inline:12px}.header{padding-inline:12px}.presence{margin-inline:12px}.vehicle{height:178px}.vehicle img{height:176px}}
@container(max-width:310px){.hero{grid-template-columns:1fr}.vehicle{order:-1;height:160px}.vehicle img{height:158px}.readout{padding-bottom:6px}.status{padding:4px 8px}.controls{grid-template-columns:repeat(2,minmax(0,1fr))}.control:nth-child(2){border-right:0}.control:nth-child(-n+2){border-bottom:1px solid var(--divider-color)}}
`;

export class CfMotoVehicleCard extends (globalThis.HTMLElement ?? class {}) {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.activeTab = 'overview';
    this.busy = false;
    this.actionError = false;
  }

  setConfig(config) {
    this.config = normalizeConfig(config);
    this.activeTab = 'overview';
    this.ids = undefined;
    this.ui = undefined;
    this.render();
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!this.config) return;
    if (!this.ids) {
      this.ids = resolveEntities(hass, this.config.entity);
      this.render();
      return;
    }
    const languageChanged = !previous || previous.language !== hass.language;
    const stateChanged = !previous || Object.values(this.ids).some((id) => id && previous.states?.[id] !== hass.states?.[id]);
    if (!languageChanged && !stateChanged) return;
    if (languageChanged || !this.ui) this.render(); else this.update();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this.render();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement('cfmoto-vehicle-card-editor');
  }

  static getStubConfig(hass) {
    return stubConfig(hass);
  }

  labels() {
    return labelsFor(this._hass?.language);
  }

  state(key) {
    const id = this.ids?.[key];
    return id ? this._hass?.states?.[id] : undefined;
  }

  display(state, fallback = '—') {
    if (!usable(state)) return fallback;
    try {
      if (typeof this._hass?.formatEntityState === 'function') return this._hass.formatEntityState(state);
    } catch {
      /* fall through to the raw state */
    }
    const unit = state.attributes?.unit_of_measurement;
    const value = Number.parseFloat(state.state);
    const text = Number.isFinite(value) ? String(Math.round(value * 10) / 10) : state.state;
    return unit ? `${text} ${unit}` : text;
  }

  /** Value for a details row, formatted by its kind. */
  detailValue(key, kind, digits = 0) {
    const labels = this.labels();
    const state = this.state(key);
    if (!usable(state)) return '—';
    if (kind === 'duration') return formatDuration(number(state), this._hass?.language);
    if (kind === 'ago') return relativeTime(state.state, labels);
    if (kind === 'onoff') return state.state === 'on' ? labels.state_on : labels.state_off;
    if (kind === 'online') return state.state === 'on' ? labels.online : labels.offline;
    if (kind === 'number') {
      const value = number(state);
      return value === null ? '—' : String(Math.round(value * 10 ** digits) / 10 ** digits);
    }
    return this.display(state);
  }

  openMoreInfo(key) {
    const entityId = this.ids?.[key];
    if (!entityId || !this._hass?.states?.[entityId]) return;
    this.dispatchEvent(new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true }));
  }

  navigate(path) {
    globalThis.history?.pushState?.(null, '', path);
    globalThis.dispatchEvent?.(new CustomEvent('location-changed', { bubbles: true, composed: true, detail: { replace: false } }));
  }

  /** Control keys whose button entity exists on the device. */
  controlKeys() {
    return CONTROLS.map(([key]) => key).filter((key) => this.controlEntity(key));
  }

  /** Entity behind a control key; the power control swaps between the two buttons. */
  controlEntity(key) {
    if (key === 'power') return this.state('ignition')?.state === 'on' ? this.ids?.power_off : this.ids?.power_on;
    return this.ids?.[key];
  }

  controlAvailable(key) {
    const entityId = this.controlEntity(key);
    return Boolean(entityId && this._hass?.states?.[entityId]);
  }

  async runAction(key) {
    if (this.busy || !this.controlAvailable(key)) return;
    const labels = this.labels();
    const entityId = this.controlEntity(key);
    if (key === 'power' && globalThis.confirm && !globalThis.confirm(labels.confirm_power)) return;
    if (key === 'unlock' && globalThis.confirm && !globalThis.confirm(labels.confirm_unlock)) return;
    this.busy = true;
    this.actionError = false;
    this.refresh();
    try {
      await this._hass.callService('button', 'press', { entity_id: entityId });
    } catch {
      this.actionError = true;
    } finally {
      this.busy = false;
      this.refresh();
    }
  }

  refresh() {
    if (this.ui) this.update(); else this.render();
  }

  title() {
    if (this.config.name) return this.config.name;
    for (const key of ['odometer', 'location', 'range']) {
      const name = this.state(key)?.attributes?.friendly_name;
      if (name) return name;
    }
    return 'CFMoto';
  }

  status() {
    const labels = this.labels();
    if (this.state('ignition')?.state === 'on') return { text: labels.ignition_on, className: 'riding' };
    const tbox = this.state('tbox');
    if (tbox && tbox.state === 'on') return { text: labels.ready, className: '' };
    if (tbox) return { text: labels.offline, className: 'off' };
    return null;
  }

  tabList() {
    const labels = this.labels();
    const tabs = [{ id: 'overview', label: labels.tab_overview }];
    if (this.config.map !== false && this.state('location')) tabs.push({ id: 'map', label: labels.tab_map });
    if (this.config.details !== false) tabs.push({ id: 'details', label: labels.tab_details });
    return tabs;
  }

  selectTab(id) {
    this.activeTab = id;
    this.syncTabs();
  }

  syncTabs() {
    const tabs = this.tabList();
    if (!tabs.some((tab) => tab.id === this.activeTab)) this.activeTab = 'overview';
    for (const [id, button] of Object.entries(this.ui?.tabs ?? {})) {
      const selected = id === this.activeTab;
      button.setAttribute('aria-selected', String(selected));
      button.classList.toggle('active', selected);
    }
    for (const [id, panel] of Object.entries(this.ui?.panels ?? {})) panel.hidden = id !== this.activeTab;
    if (this.activeTab === 'map') this.ensureMap();
  }

  ensureMap() {
    const host = this.ui?.mapHost;
    if (!host) return;
    const entity = this.ids.location;
    if (this.ui.mapEntity === entity) return;
    this.ui.mapEntity = entity;
    this.ui.map = null;
    host.replaceChildren();
    if (!entity) return;
    if (globalThis.customElements?.get('hui-map-card')) {
      const map = document.createElement('hui-map-card');
      map.setConfig({ entities: [{ entity }] });
      map.hass = this._hass;
      host.append(map);
      this.ui.map = map;
    } else {
      host.append(element('p', this.labels().map_placeholder, 'map-note'));
    }
  }

  buildReadout() {
    const labels = this.labels();
    const wrap = element('div', '', 'readout');
    const value = element('div', '', 'value');
    const amount = element('span'), unit = element('small');
    value.append(amount, unit);
    const chip = element('span', '', 'chip');
    const chipText = element('span');
    chip.append(icon('gas-station'), chipText);
    chip.title = labels.fuel;
    wrap.append(value, element('div', labels.range, 'label'), chip);
    this.ui.readout = { amount, unit, chip, chipText };
    return wrap;
  }

  buildVehicle() {
    const labels = this.labels();
    const button = element('button', '', 'vehicle');
    button.type = 'button';
    button.setAttribute('aria-label', labels.vehicle_image);
    button.addEventListener('click', () => {
      if (this.config.image_navigate) this.navigate(this.config.image_navigate);
      else this.openMoreInfo('odometer');
    });
    this.ui.vehicle = button;
    this.ui.vehicleSrc = undefined;
    return button;
  }

  buildMetrics() {
    const labels = this.labels();
    const grid = element('div', '', 'metrics');
    this.ui.metrics = {};
    const rows = [
      ['odometer', labels.odometer, 'counter'],
      ['month', labels.month, 'calendar-month'],
      ['battery', labels.battery, 'car-battery'],
      ['avg_speed', labels.avg_speed, 'speedometer'],
    ];
    for (const [key, label, iconName] of rows) {
      const button = element('button', '', 'metric');
      button.type = 'button';
      const value = element('span', '', 'value');
      button.append(icon(iconName), value, element('span', label, 'label'));
      button.addEventListener('click', () => this.openMoreInfo(key));
      grid.append(button);
      this.ui.metrics[key] = { button, value };
    }
    return grid;
  }

  buildPresence() {
    const row = element('div', '', 'presence');
    const location = element('span'), tbox = element('span'), updated = element('span');
    row.append(icon('map-marker'), location, tbox, updated);
    this.ui.presence = { row, location, tbox, updated };
    return row;
  }

  buildDetails() {
    const labels = this.labels();
    const list = element('div', '', 'details');
    this.ui.details = {};
    for (const [key, iconName, labelKey, kind] of DETAIL_ROWS) {
      const row = element('button', '', 'row');
      row.type = 'button';
      const value = element('span', '', 'row-value');
      row.append(icon(iconName), element('span', labels[labelKey], 'row-label'), value);
      row.addEventListener('click', () => this.openMoreInfo(key));
      list.append(row);
      this.ui.details[key] = { row, value, kind };
    }
    return list;
  }

  buildControls() {
    const labels = this.labels();
    const row = element('div', '', 'controls');
    this.ui.controls = {};
    const available = this.controlKeys();
    for (const [key, iconName, labelKey] of CONTROLS) {
      if (!available.includes(key)) continue;
      const button = element('button', '', 'control');
      button.type = 'button';
      const label = element('span', labels[labelKey]);
      const mark = icon(iconName);
      button.append(mark, label);
      button.addEventListener('click', () => void this.runAction(key));
      row.append(button);
      this.ui.controls[key] = { button, label, mark };
    }
    return row;
  }

  render() {
    if (!this.config || !this._hass || !this.shadowRoot) return;
    const labels = this.labels();
    this.ui = {};
    const card = element('ha-card');

    if (!this.config.entity) {
      card.append(element('p', labels.no_entity, 'error'));
      this.shadowRoot.replaceChildren(element('style', CSS), card);
      this.ui = undefined;
      return;
    }
    this.ids = resolveEntities(this._hass, this.config.entity);

    const header = element('header', '', 'header');
    const heading = element('div');
    heading.append(element('p', labels.eyebrow, 'eyebrow'), element('h2', this.title()));
    header.append(heading);
    const status = element('span', '', 'status');
    status.hidden = true;
    header.append(status);
    this.ui.status = status;
    card.append(header);

    const tabs = this.tabList();
    const showTabs = this.config.tabs !== false && tabs.length > 1;
    if (showTabs) {
      const bar = element('nav', '', 'tabs');
      bar.setAttribute('role', 'tablist');
      this.ui.tabs = {};
      for (const tab of tabs) {
        const button = element('button', tab.label, 'tab');
        button.type = 'button';
        button.setAttribute('role', 'tab');
        button.addEventListener('click', () => this.selectTab(tab.id));
        bar.append(button);
        this.ui.tabs[tab.id] = button;
      }
      card.append(bar);
    }

    const panels = {};
    const overview = element('div', '', 'panel');
    const hero = element('div', '', 'hero');
    hero.append(this.buildReadout(), this.buildVehicle());
    overview.append(hero);
    if (this.config.show_metrics !== false) overview.append(this.buildMetrics());
    if (this.config.show_presence !== false) overview.append(this.buildPresence());
    panels.overview = overview;

    if (showTabs && tabs.some((tab) => tab.id === 'map')) {
      const panel = element('div', '', 'panel');
      const host = element('div', '', 'map');
      panel.append(host);
      this.ui.mapHost = host;
      panels.map = panel;
    }
    if (showTabs && tabs.some((tab) => tab.id === 'details')) {
      const panel = element('div', '', 'panel');
      panel.append(this.buildDetails());
      panels.details = panel;
    }
    for (const panel of Object.values(panels)) card.append(panel);
    this.ui.panels = panels;
    this.ui.tabIds = tabs.map((tab) => tab.id).join();

    if (this.controlKeys().length > 0) {
      card.append(this.buildControls());
      const error = element('p', labels.action_error, 'error');
      error.setAttribute('role', 'alert');
      error.hidden = true;
      card.append(error);
      this.ui.error = error;
    }

    this.shadowRoot.replaceChildren(element('style', CSS), card);
    this.syncTabs();
    this.update();
  }

  update() {
    if (!this.config || !this._hass) return;
    if (!this.ui) {
      this.render();
      return;
    }
    if (this.ui.tabIds !== this.tabList().map((tab) => tab.id).join()) {
      this.render();
      return;
    }

    const status = this.status();
    this.ui.status.hidden = !status;
    if (status) {
      this.ui.status.textContent = status.text;
      this.ui.status.className = `status ${status.className}`.trim();
    }

    this.updateReadout();
    this.updateVehicle();
    this.updateMetrics();
    this.updatePresence();
    this.updateDetails();
    this.updateControls();
    if (this.ui.error) this.ui.error.hidden = !this.actionError;
    this.ensureMap();
    if (this.ui.map) this.ui.map.hass = this._hass;
  }

  updateReadout() {
    const ui = this.ui.readout;
    if (!ui) return;
    const range = this.state('range');
    const numeric = number(range);
    ui.amount.textContent = numeric === null ? '—' : String(Math.round(numeric));
    const unit = range?.attributes?.unit_of_measurement;
    ui.unit.textContent = numeric !== null && unit ? unit : '';
    const fuel = this.state('fuel_text') || this.state('fuel');
    ui.chip.hidden = !usable(fuel);
    if (usable(fuel)) ui.chipText.textContent = this.display(fuel);
  }

  updateVehicle() {
    const button = this.ui.vehicle;
    if (!button) return;
    const src = this.config.image || DEFAULT_IMAGE;
    if (src !== this.ui.vehicleSrc) {
      this.ui.vehicleSrc = src;
      button.replaceChildren();
      const image = document.createElement('img');
      image.src = src;
      image.alt = this.labels().vehicle_image;
      image.addEventListener('error', () => image.replaceWith(icon('motorbike')), { once: true });
      button.append(image);
    }
    button.disabled = !usable(this.state('odometer'));
  }

  updateMetrics() {
    for (const [key, entry] of Object.entries(this.ui.metrics ?? {})) {
      entry.value.textContent = this.display(this.state(key));
      entry.button.disabled = !usable(this.state(key));
    }
  }

  updatePresence() {
    const ui = this.ui.presence;
    if (!ui) return;
    const labels = this.labels();
    const location = this.state('location');
    ui.location.hidden = !usable(location);
    if (usable(location)) {
      ui.location.textContent =
        location.state === 'home' ? labels.home : location.state === 'not_home' ? labels.away : location.state;
    }
    const tbox = this.state('tbox');
    ui.tbox.hidden = !usable(tbox);
    if (usable(tbox)) ui.tbox.textContent = `${labels.tbox} ${tbox.state === 'on' ? labels.online.toLowerCase() : labels.offline.toLowerCase()}`;
    const updated = this.state('last_update');
    ui.updated.hidden = !usable(updated);
    if (usable(updated)) ui.updated.textContent = `${labels.updated} ${relativeTime(updated.state, labels)}`;
  }

  updateDetails() {
    for (const [key, entry] of Object.entries(this.ui.details ?? {})) {
      entry.value.textContent = this.detailValue(key, entry.kind);
      entry.row.disabled = !usable(this.state(key));
    }
  }

  updateControls() {
    const ui = this.ui.controls;
    if (!ui) return;
    const labels = this.labels();
    const powerOn = this.state('ignition')?.state === 'on';
    for (const [key, entry] of Object.entries(ui)) {
      if (key === 'power') {
        entry.label.textContent = powerOn ? labels.ignition_off : labels.ignition_on;
        entry.mark?.setAttribute('icon', `mdi:${powerOn ? 'power-off' : 'power'}`);
      }
      entry.button.disabled = this.busy || !this.controlAvailable(key);
      entry.button.classList.toggle('busy', this.busy);
    }
  }
}

if (globalThis.customElements && !customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, CfMotoVehicleCard);
  globalThis.customCards ??= [];
  globalThis.customCards.push({
    type: CARD_TYPE,
    name: 'CFMoto Vehicle',
    description: 'Fahrzeugbild, Reichweite, Tank, Kilometer, Details und Live-Status',
    preview: true,
  });
}
