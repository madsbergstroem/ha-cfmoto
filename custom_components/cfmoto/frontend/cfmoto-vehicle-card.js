/** CFMoto vehicle card. Renders existing HA entities; no cloud calls of its own. */

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
  avg_speed: '_average_speed',
  ignition: '_ignition',
  tbox: '_t_box_online',
  last_update: '_last_update',
};

const LABELS = {
  de: {
    eyebrow: 'CFMoto',
    range: 'Reichweite',
    fuel: 'Tank',
    odometer: 'Kilometer',
    month: 'Diesen Monat',
    battery: 'Bordspannung',
    online: 'Online',
    offline: 'Offline',
    ignition_on: 'Zündung an',
    ready: 'Bereit',
    home: 'Zuhause',
    away: 'Unterwegs',
    tbox: 'T-Box',
    tbox_off: 'T-Box offline',
    updated: 'aktualisiert',
    vehicle_image: 'Fahrzeugbild',
    unavailable: 'Keine Daten',
    no_entity: 'Keine CFMoto-Entität gefunden',
  },
  en: {
    eyebrow: 'CFMoto',
    range: 'Range',
    fuel: 'Fuel',
    odometer: 'Odometer',
    month: 'This month',
    battery: 'Battery',
    online: 'Online',
    offline: 'Offline',
    ignition_on: 'Ignition on',
    ready: 'Ready',
    home: 'Home',
    away: 'Away',
    tbox: 'T-Box',
    tbox_off: 'T-Box offline',
    updated: 'updated',
    vehicle_image: 'Vehicle image',
    unavailable: 'No data',
    no_entity: 'No CFMoto entity found',
  },
};

function labelsFor(language) {
  return (language || 'en').toLowerCase().startsWith('de') ? LABELS.de : LABELS.en;
}

function element(tag, text = '', className = '') {
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

function usable(state) {
  return state && !['unavailable', 'unknown'].includes(state.state);
}

function number(state) {
  const value = Number.parseFloat(state?.state);
  return Number.isFinite(value) ? value : null;
}

/** All entity ids that belong to the same device as the configured entity. */
function deviceEntityIds(hass, entityId) {
  const all = Object.keys(hass.states || {});
  const deviceId = hass.entities?.[entityId]?.device_id;
  if (!deviceId) return all;
  return all.filter((id) => hass.entities?.[id]?.device_id === deviceId);
}

function pick(ids, suffix) {
  const matches = ids.filter((id) => id.endsWith(suffix));
  matches.sort((a, b) => a.length - b.length);
  return matches[0];
}

function resolveEntities(hass, entityId) {
  const ids = deviceEntityIds(hass, entityId);
  const result = {};
  for (const [key, suffix] of Object.entries(SUFFIX)) {
    result[key] = pick(ids, suffix);
  }
  result.location = ids.find((id) => id.startsWith('device_tracker.'));
  return result;
}

function stubConfig(hass) {
  const entity = Object.keys(hass?.states || {}).find(
    (id) => id.startsWith('sensor.') && id.endsWith('_odometer') && id.includes('450mt')
  );
  return { type: `custom:${CARD_TYPE}`, entity: entity || '' };
}

const CSS = `
:host{display:block;container-type:inline-size}*{box-sizing:border-box}
ha-card{display:block;overflow:hidden;border:1px solid var(--divider-color);border-radius:20px;background:var(--card-background-color);color:var(--primary-text-color)}
button{font:inherit}
.header{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:14px 16px 0}
.eyebrow{margin:0 0 2px;color:var(--secondary-text-color);font-size:9px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}
h2{margin:0;font-size:18px;font-weight:650;letter-spacing:-.025em;line-height:1.2;overflow-wrap:anywhere}
.status{display:inline-flex;align-items:center;gap:5px;flex:none;border-radius:999px;padding:4px 9px;background:color-mix(in srgb,var(--success-color,#4ade80) 13%,transparent);color:var(--success-color,#4ade80);font-size:10.5px;font-weight:650}
.status::before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}
.status.riding{color:var(--warning-color,#f59e0b);background:color-mix(in srgb,var(--warning-color,#f59e0b) 13%,transparent)}
.status.off{color:var(--secondary-text-color);background:color-mix(in srgb,var(--secondary-text-color) 10%,transparent)}
.hero{display:grid;grid-template-columns:112px minmax(0,1fr);align-items:center;gap:6px;min-height:132px;padding:4px 16px 0}
.readout{display:flex;flex-direction:column;align-items:center;min-width:0}
.readout .value{display:flex;align-items:baseline;gap:3px;font-size:30px;font-weight:700;letter-spacing:-.055em;line-height:1}
.readout .value small{margin-bottom:3px;font-size:13px;font-weight:600;letter-spacing:0}
.readout .label{margin-top:5px;color:var(--secondary-text-color);font-size:10px}
.chip{display:inline-flex;align-items:center;gap:4px;margin-top:8px;border-radius:999px;padding:4px 9px;background:color-mix(in srgb,var(--secondary-text-color) 10%,transparent);color:var(--secondary-text-color);font-size:10.5px;font-weight:600;white-space:nowrap}
.chip ha-icon{--mdc-icon-size:13px}
.vehicle{display:flex;align-items:center;justify-content:center;width:100%;height:128px;min-width:0;padding:0;border:0;border-radius:18px;background:radial-gradient(ellipse at 50% 65%,color-mix(in srgb,var(--primary-color) 12%,transparent),transparent 70%);color:var(--primary-color);cursor:pointer}
.vehicle img{display:block;width:100%;height:124px;object-fit:contain;filter:drop-shadow(0 14px 12px rgb(0 0 0 / .22))}
.vehicle ha-icon{--mdc-icon-size:64px;opacity:.5}
.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:8px 16px 10px}
.metric{display:flex;flex-direction:column;align-items:flex-start;min-width:0;min-height:52px;padding:8px;border:0;border-radius:13px;background:color-mix(in srgb,var(--secondary-text-color) 7%,transparent);color:var(--primary-text-color);text-align:left;cursor:pointer}
.metric ha-icon{margin-bottom:5px;color:var(--secondary-text-color);--mdc-icon-size:15px}
.metric .value{display:block;max-width:100%;overflow:hidden;font-size:13px;font-weight:650;letter-spacing:-.02em;text-overflow:ellipsis;white-space:nowrap}
.metric .label{display:block;max-width:100%;margin-top:2px;overflow:hidden;color:var(--secondary-text-color);font-size:9px;text-overflow:ellipsis;white-space:nowrap}
.metric:disabled{cursor:default;opacity:.58}
.presence{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:0 16px 11px;color:var(--secondary-text-color);font-size:11px}
.presence ha-icon{--mdc-icon-size:15px}
.presence span+span::before{content:"·";margin-right:6px}
.error{margin:0;padding:9px 16px;background:color-mix(in srgb,var(--error-color) 9%,transparent);color:var(--error-color);font-size:11.5px;line-height:1.4}
button:focus-visible{outline:2px solid var(--primary-color);outline-offset:-3px}
@media(prefers-reduced-motion:no-preference){.metric{transition:background .16s ease}.metric:hover{background:color-mix(in srgb,var(--primary-color) 8%,transparent)}}
@container(max-width:430px){.hero{grid-template-columns:100px minmax(0,1fr);padding-inline:12px}.readout .value{font-size:26px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));padding-inline:12px}.header{padding-inline:12px}.presence{margin-inline:12px}.vehicle{height:112px}.vehicle img{height:108px}}
@container(max-width:310px){.hero{grid-template-columns:1fr}.vehicle{order:-1;height:124px}.vehicle img{height:120px}.readout{padding-bottom:6px}.status{padding:4px 8px}}
`;

export class CfMotoVehicleCard extends (globalThis.HTMLElement ?? class {}) {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = { ...config };
    this.render();
  }

  set hass(hass) {
    const previous = this._hass;
    this._hass = hass;
    if (!this.config) return;
    if (!previous) {
      this.ids = resolveEntities(hass, this.config.entity);
      this.render();
      return;
    }
    const ids = this.ids || {};
    const changed =
      previous.language !== hass.language ||
      Object.values(ids).some((id) => id && previous.states?.[id] !== hass.states?.[id]);
    if (changed) this.render();
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    this.render();
  }

  getCardSize() {
    return 4;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
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
      if (typeof this._hass?.formatEntityState === 'function') {
        return this._hass.formatEntityState(state);
      }
    } catch {
      /* fall through to the raw state */
    }
    const unit = state.attributes?.unit_of_measurement;
    const value = Number.parseFloat(state.state);
    const text = Number.isFinite(value) ? String(Math.round(value * 10) / 10) : state.state;
    return unit ? `${text} ${unit}` : text;
  }

  openMoreInfo(key) {
    const entityId = this.ids?.[key];
    if (!entityId || !this._hass?.states?.[entityId]) return;
    this.dispatchEvent(
      new CustomEvent('hass-more-info', { detail: { entityId }, bubbles: true, composed: true })
    );
  }

  navigate(path) {
    globalThis.history?.pushState?.(null, '', path);
    globalThis.dispatchEvent?.(
      new CustomEvent('location-changed', { bubbles: true, composed: true, detail: { replace: false } })
    );
  }

  title() {
    if (this.config.name) return this.config.name;
    for (const key of ['odometer', 'location', 'range']) {
      const name = this.state(key)?.attributes?.friendly_name;
      if (name) return name;
    }
    return 'CFMoto';
  }

  status(labels) {
    if (this.state('ignition')?.state === 'on') return { text: labels.ignition_on, className: 'riding' };
    const tbox = this.state('tbox');
    if (tbox && tbox.state === 'on') return { text: labels.ready, className: '' };
    if (tbox) return { text: labels.offline, className: 'off' };
    return null;
  }

  readout(labels) {
    const wrap = element('div', '', 'readout');
    const range = this.state('range');
    const value = element('div', '', 'value');
    const numeric = number(range);
    value.append(element('span', numeric === null ? '—' : String(Math.round(numeric))));
    const unit = range?.attributes?.unit_of_measurement;
    if (numeric !== null && unit) value.append(element('small', unit));
    wrap.append(value, element('div', labels.range, 'label'));

    const fuel = this.state('fuel_text') || this.state('fuel');
    if (usable(fuel)) {
      const chip = element('span', '', 'chip');
      chip.append(icon('gas-station'), element('span', this.display(fuel)));
      chip.title = labels.fuel;
      wrap.append(chip);
    }
    return wrap;
  }

  vehicleImage(labels) {
    const button = element('button', '', 'vehicle');
    button.type = 'button';
    button.setAttribute('aria-label', labels.vehicle_image);
    const source = this.config.image || DEFAULT_IMAGE;
    const image = document.createElement('img');
    image.src = source;
    image.alt = labels.vehicle_image;
    image.addEventListener('error', () => image.replaceWith(icon('motorbike')), { once: true });
    button.append(image);
    button.addEventListener('click', () => {
      if (this.config.image_navigate) this.navigate(this.config.image_navigate);
      else this.openMoreInfo('odometer');
    });
    return button;
  }

  metric(key, label, iconName, stateKey = key) {
    const state = this.state(stateKey);
    const button = element('button', '', 'metric');
    button.type = 'button';
    button.append(
      icon(iconName),
      element('span', this.display(state), 'value'),
      element('span', label, 'label')
    );
    button.disabled = !usable(state);
    button.addEventListener('click', () => this.openMoreInfo(stateKey));
    return button;
  }

  presence(labels) {
    const row = element('div', '', 'presence');
    row.append(icon('map-marker'));
    const location = this.state('location');
    if (usable(location)) {
      const text =
        location.state === 'home'
          ? labels.home
          : location.state === 'not_home'
            ? labels.away
            : location.state;
      row.append(element('span', text));
    }
    const tbox = this.state('tbox');
    if (usable(tbox)) {
      row.append(element('span', `${labels.tbox} ${tbox.state === 'on' ? labels.online.toLowerCase() : labels.offline.toLowerCase()}`));
    }
    const updated = this.state('last_update');
    if (usable(updated)) {
      const stamp = new Date(updated.state);
      if (!Number.isNaN(stamp.getTime())) {
        const minutes = Math.round((Date.now() - stamp.getTime()) / 60000);
        const text =
          minutes < 1
            ? 'gerade eben'
            : minutes < 60
              ? `vor ${minutes} Min`
              : `vor ${Math.round(minutes / 60)} Std`;
        row.append(element('span', `${labels.updated} ${text}`));
      }
    }
    if (!row.querySelector('span')) row.append(element('span', labels.unavailable));
    return row;
  }

  render() {
    if (!this.config || !this._hass || !this.shadowRoot) return;
    const labels = this.labels();
    const card = element('ha-card');

    if (!this.config.entity) {
      card.append(element('p', labels.no_entity, 'error'));
      this.shadowRoot.replaceChildren(element('style', CSS), card);
      return;
    }
    this.ids = resolveEntities(this._hass, this.config.entity);

    const header = element('header', '', 'header');
    const heading = element('div');
    heading.append(element('p', labels.eyebrow, 'eyebrow'), element('h2', this.title()));
    header.append(heading);
    const status = this.status(labels);
    if (status) header.append(element('span', status.text, `status ${status.className}`));

    const hero = element('div', '', 'hero');
    hero.append(this.readout(labels), this.vehicleImage(labels));

    card.append(header, hero);

    if (this.config.show_metrics !== false) {
      const metrics = element('div', '', 'metrics');
      metrics.append(
        this.metric('odometer', labels.odometer, 'counter'),
        this.metric('month', labels.month, 'calendar-month'),
        this.metric('battery', labels.battery, 'car-battery'),
        this.metric('avg_speed', labels.avg_speed, 'speedometer')
      );
      card.append(metrics);
    }
    if (this.config.show_presence !== false) card.append(this.presence(labels));

    this.shadowRoot.replaceChildren(element('style', CSS), card);
  }
}

if (globalThis.customElements && !customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, CfMotoVehicleCard);
  globalThis.customCards ??= [];
  globalThis.customCards.push({
    type: CARD_TYPE,
    name: 'CFMoto Vehicle',
    description: 'Fahrzeugbild, Reichweite, Tank, Kilometer und Live-Status',
    preview: true,
  });
}
