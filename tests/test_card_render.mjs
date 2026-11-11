import test from 'node:test';
import assert from 'node:assert/strict';

/** Minimal DOM shim: enough for the card's shadow-root rendering. */
class FakeElement {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.className = '';
    this.hidden = false;
    this.disabled = false;
    this.type = '';
    this._text = '';
    this.classList = {
      toggle: (name, force) => {
        const names = new Set(this.className.split(/\s+/).filter(Boolean));
        if (force) names.add(name); else names.delete(name);
        this.className = [...names].join(' ');
      },
    };
  }

  get textContent() {
    return this._text + this.children.map((child) => child.textContent ?? '').join('');
  }

  set textContent(value) {
    this._text = String(value ?? '');
    this.children = [];
  }

  append(...nodes) {
    for (const node of nodes) this.children.push(node);
  }

  replaceChildren(...nodes) {
    this.children = [];
    this._text = '';
    this.append(...nodes);
  }

  attachShadow() {
    this.shadowRoot = new FakeElement('#shadow-root');
    return this.shadowRoot;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  removeAttribute(name) {
    delete this.attributes[name];
  }

  addEventListener(type, handler) {
    (this.listeners[type] ??= []).push(handler);
  }

  click() {
    for (const handler of this.listeners.click ?? []) handler();
  }

  querySelectorAll(predicate, out = []) {
    for (const child of this.children) {
      if (predicate(child)) out.push(child);
      if (child.querySelectorAll) child.querySelectorAll(predicate, out);
    }
    return out;
  }

  find(predicate) {
    return this.querySelectorAll(predicate)[0];
  }
}

function installDom() {
  globalThis.HTMLElement = FakeElement;
  globalThis.document = {
    createElement: (tag) => new FakeElement(tag),
    createElementNS: (_namespace, tag) => new FakeElement(tag),
    createTextNode: (text) => {
      const node = new FakeElement('#text');
      node._text = String(text);
      return node;
    },
  };
}

installDom();
const { CfMotoVehicleCard } = await import('../custom_components/cfmoto/frontend/cfmoto-vehicle-card.js');

const DEVICE = 'dev1';

const STATES = {
  'sensor.450mt_odometer': { state: '5885.8', attributes: { unit_of_measurement: 'km', friendly_name: '450MT Odometer' } },
  'sensor.450mt_range': { state: '134.0', attributes: { unit_of_measurement: 'km' } },
  'sensor.450mt_battery_voltage': { state: '12.6', attributes: { unit_of_measurement: 'V' } },
  'sensor.450mt_fuel_level': { state: '2.0', attributes: {} },
  'sensor.450mt_fuel_level_display': { state: 'Sufficient', attributes: {} },
  'sensor.450mt_ride_mileage_this_month': { state: '382.7', attributes: { unit_of_measurement: 'km' } },
  'sensor.450mt_riding_time_this_month': { state: '49449', attributes: { unit_of_measurement: 's' } },
  'sensor.450mt_average_speed': { state: '27.9', attributes: { unit_of_measurement: 'km/h' } },
  'sensor.450mt_gsm_signal': { state: '30.0', attributes: {} },
  'sensor.450mt_last_update': { state: new Date(Date.now() - 5 * 60000).toISOString(), attributes: {} },
  'binary_sensor.450mt_ignition': { state: 'off', attributes: {} },
  'binary_sensor.450mt_t_box_online': { state: 'on', attributes: {} },
  'device_tracker.450mt': { state: 'home', attributes: {} },
};

const BUTTON_STATES = {
  'button.450mt_power_on': { state: 'unknown', attributes: {} },
  'button.450mt_power_off': { state: 'unknown', attributes: {} },
  'button.450mt_unlock': { state: 'unknown', attributes: {} },
  'button.450mt_lock': { state: 'unknown', attributes: {} },
  'button.450mt_horn': { state: 'unknown', attributes: {} },
};

function makeHass(states = STATES, language = 'de') {
  const entities = Object.fromEntries(Object.keys(states).map((id) => [id, { device_id: DEVICE }]));
  return { states, entities, language };
}

function mount(config = {}) {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer', ...config });
  card.hass = makeHass();
  return card;
}

const byClass = (className) => (node) => (node.className ?? '').split(/\s+/).includes(className);

test('render builds header, tabs, overview, map and details panels', () => {
  const card = mount();
  const root = card.shadowRoot;
  assert.ok(root.find(byClass('header')));
  assert.equal(root.find(byClass('tab')).textContent, 'Übersicht');
  assert.equal(root.querySelectorAll(byClass('tab')).length, 3);
  const panels = root.querySelectorAll(byClass('panel'));
  assert.equal(panels.length, 3);
  // The backdrop was removed from the card; the map lives only in its own tab.
  assert.equal(root.find(byClass('backdrop')), undefined);
  assert.ok(panels[1].find(byClass('map')));
  assert.equal(root.querySelectorAll(byClass('map')).length, 1);
  assert.equal(root.querySelectorAll(byClass('metric')).length, 4);
});

test('overview shows range, fuel chip, status and metrics', () => {
  const card = mount();
  const root = card.shadowRoot;
  const value = root.find(byClass('value'));
  assert.equal(value.textContent, '134km');
  assert.equal(root.find(byClass('chip')).textContent, 'Sufficient');
  assert.equal(root.find(byClass('status')).textContent, 'Bereit');
  const metrics = root.querySelectorAll(byClass('metric')).map((node) => node.textContent);
  assert.deepEqual(metrics, ['5885.8 kmKilometer', '382.7 kmDiesen Monat', '12.6 VBordspannung', '27.9 km/hØ Tempo']);
});

const DETAIL_STATES = {
  'sensor.450mt_speed': { state: '42.4', attributes: { unit_of_measurement: 'km/h' } },
  'binary_sensor.450mt_vehicle_online': { state: 'off', attributes: {} },
  'binary_sensor.450mt_seat_lock': { state: 'on', attributes: {} },
  'binary_sensor.450mt_steering_lock': { state: 'off', attributes: {} },
  'binary_sensor.450mt_fuel_lock': { state: 'off', attributes: {} },
  'binary_sensor.450mt_battery_lock': { state: 'on', attributes: {} },
};

test('details rows format duration, signal, ignition, t-box, age, speed, online and locks', () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer' });
  card.hass = makeHass({ ...STATES, ...DETAIL_STATES });
  card.selectTab('details');
  const nodes = card.shadowRoot.querySelectorAll(byClass('row'));
  const rows = nodes.map((node) => node.textContent);
  assert.equal(rows.length, 12);
  assert.match(rows[0], /^TankSufficient$/);
  assert.match(rows[1], /^Fahrzeit13 Std 44 min$/);
  assert.match(rows[2], /^Signal30$/);
  assert.match(rows[3], /^ZündungAus$/);
  assert.match(rows[4], /^T-BoxOnline$/);
  assert.match(rows[5], /^Letzte Datenvor 5 Min$/);
  assert.match(rows[6], /^Tempo42$/);
  assert.match(rows[7], /^Fahrzeug onlineOffline$/);
  assert.match(rows[8], /^SitzbankAn$/);
  assert.match(rows[9], /^LenkschlossAus$/);
  assert.match(rows[10], /^TankdeckelAus$/);
  assert.match(rows[11], /^BatterieschlossAn$/);
  assert.deepEqual(nodes.map((node) => node.disabled), Array(12).fill(false));
});

test('speed row does not fall back to the average speed sensor', () => {
  const card = mount();
  assert.equal(card.ids.speed, undefined);
  assert.equal(card.ids.avg_speed, 'sensor.450mt_average_speed');
  card.selectTab('details');
  const speed = card.shadowRoot.querySelectorAll(byClass('row')).find((row) => row.textContent.startsWith('Tempo'));
  assert.equal(speed.textContent, 'Tempo—');
  assert.equal(speed.disabled, true);
});

test('tab switching hides the other panels', () => {
  const card = mount();
  const panels = card.shadowRoot.querySelectorAll(byClass('panel'));
  assert.deepEqual(panels.map((panel) => panel.hidden), [false, true, true]);
  card.selectTab('map');
  assert.deepEqual(panels.map((panel) => panel.hidden), [true, false, true]);
  assert.ok(card.shadowRoot.find(byClass('map-note')));
  card.selectTab('details');
  assert.deepEqual(panels.map((panel) => panel.hidden), [true, true, false]);
});

test('state updates refresh values without rebuilding the card', () => {
  const card = mount();
  const root = card.shadowRoot;
  const ui = card.ui;
  const next = makeHass({ ...STATES, 'sensor.450mt_odometer': { state: '6000.0', attributes: { unit_of_measurement: 'km' } } });
  card.hass = next;
  assert.equal(card.shadowRoot, root);
  assert.equal(card.ui, ui);
  assert.equal(root.find(byClass('metric')).textContent, '6000 kmKilometer');
});

test('unavailable entities render as a dash and disable the row', () => {
  const card = mount();
  const states = { ...STATES, 'sensor.450mt_gsm_signal': { state: 'unavailable', attributes: {} } };
  card.hass = makeHass(states);
  card.selectTab('details');
  const rows = card.shadowRoot.querySelectorAll(byClass('row'));
  const signal = rows.find((row) => row.textContent.startsWith('Signal'));
  assert.equal(signal.textContent, 'Signal—');
  assert.equal(signal.disabled, true);
});

test('tabs:false renders a plain overview without tab bar or panels', () => {
  const card = mount({ tabs: false });
  const root = card.shadowRoot;
  assert.equal(root.querySelectorAll(byClass('tab')).length, 0);
  assert.equal(root.querySelectorAll(byClass('panel')).length, 1);
  assert.equal(root.querySelectorAll(byClass('row')).length, 0);
  assert.ok(root.find(byClass('hero')));
});

test('map and details toggles remove their tabs', () => {
  const card = mount({ map: false, details: false });
  const root = card.shadowRoot;
  assert.equal(root.querySelectorAll(byClass('tab')).length, 0);
  assert.equal(root.querySelectorAll(byClass('panel')).length, 1);
  assert.equal(root.querySelectorAll(byClass('row')).length, 0);
});

test('show_background:false drops the backdrop', () => {
  const card = mount({ show_background: false });
  assert.equal(card.shadowRoot.find(byClass('backdrop')), undefined);
});

test('english locale renders english labels', () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer' });
  card.hass = makeHass(STATES, 'en');
  assert.equal(card.shadowRoot.find(byClass('tab')).textContent, 'Overview');
  card.selectTab('details');
  const rows = card.shadowRoot.querySelectorAll(byClass('row')).map((node) => node.textContent);
  assert.match(rows[1], /^Riding time13 h 44 min$/);
  assert.match(rows[5], /^Last data5 min ago$/);
});

test('missing entity renders the no-entity hint', () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card' });
  card.hass = makeHass();
  assert.equal(card.shadowRoot.find(byClass('error')).textContent, 'Keine CFMoto-Entität gefunden');
});

test('image click navigates to the configured path', () => {  const card = mount({ image_navigate: '/lovelace/450mt-details' });
  const events = [];
  globalThis.history = { pushState: (_state, _title, path) => events.push(['push', path]) };
  globalThis.dispatchEvent = (event) => events.push(['event', event.detail?.replace]);
  card.shadowRoot.find(byClass('vehicle')).click();
  assert.deepEqual(events, [['push', '/lovelace/450mt-details'], ['event', false]]);
  delete globalThis.history;
  delete globalThis.dispatchEvent;
});

test('controls stay hidden while the BLE buttons are missing', () => {
  const card = mount();
  assert.equal(card.shadowRoot.find(byClass('controls')), undefined);
});

test('controls render with the BLE buttons and flip the power action', () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer' });
  card.hass = makeHass({ ...STATES, ...BUTTON_STATES });
  const controls = card.shadowRoot.querySelectorAll(byClass('control'));
  assert.equal(controls.length, 4);
  assert.deepEqual(controls.map((node) => node.textContent), ['Zündung an', 'Aufschließen', 'Zusperren', 'Hupe']);

  card.hass = makeHass({ ...STATES, ...BUTTON_STATES, 'binary_sensor.450mt_ignition': { state: 'on', attributes: {} } });
  assert.equal(card.shadowRoot.querySelectorAll(byClass('control'))[0].textContent, 'Zündung aus');
});

test('pressing a control calls button.press on the resolved entity', async () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer' });
  const calls = [];
  const hass = makeHass({ ...STATES, ...BUTTON_STATES, 'binary_sensor.450mt_ignition': { state: 'on', attributes: {} } });
  hass.callService = async (domain, service, data) => calls.push([domain, service, data]);
  card.hass = hass;

  card.shadowRoot.querySelectorAll(byClass('control'))[3].click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(calls, [['button', 'press', { entity_id: 'button.450mt_horn' }]]);

  card.shadowRoot.querySelectorAll(byClass('control'))[0].click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(calls[1], ['button', 'press', { entity_id: 'button.450mt_power_off' }]);
});

test('a failed action shows the error line', async () => {
  const card = new CfMotoVehicleCard();
  card.setConfig({ type: 'custom:cfmoto-vehicle-card', entity: 'sensor.450mt_odometer' });
  const hass = makeHass({ ...STATES, ...BUTTON_STATES });
  hass.callService = async () => { throw new Error('ble offline'); };
  card.hass = hass;

  assert.equal(card.shadowRoot.find(byClass('error')).hidden, true);
  card.shadowRoot.querySelectorAll(byClass('control'))[3].click();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(card.shadowRoot.find(byClass('error')).hidden, false);
});
