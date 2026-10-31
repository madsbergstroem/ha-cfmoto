import test from 'node:test';
import assert from 'node:assert/strict';

import {
  formatDuration, labelsFor, normalizeConfig, number, pick, relativeTime, resolveEntities, stubConfig, usable,
} from '../custom_components/cfmoto/frontend/cfmoto-vehicle-card.js';

const DEVICE = 'dev1';

function hass(states, entities = {}) {
  return { states, entities };
}

const STATES = {
  'sensor.450mt_odometer': { state: '5885.8', attributes: { unit_of_measurement: 'km', friendly_name: '450MT Odometer' } },
  'sensor.450mt_range': { state: '134.0', attributes: { unit_of_measurement: 'km' } },
  'sensor.450mt_battery_voltage': { state: '12.6', attributes: { unit_of_measurement: 'V' } },
  'sensor.450mt_fuel_level_display': { state: 'Sufficient', attributes: {} },
  'sensor.450mt_ride_mileage_this_month': { state: '382.7', attributes: { unit_of_measurement: 'km' } },
  'sensor.450mt_riding_time_this_month': { state: '49449', attributes: { unit_of_measurement: 's' } },
  'sensor.450mt_average_speed': { state: '27.9', attributes: { unit_of_measurement: 'km/h' } },
  'sensor.450mt_gsm_signal': { state: '30.0', attributes: {} },
  'sensor.450mt_last_update': { state: '2026-10-30T15:28:24+00:00', attributes: {} },
  'binary_sensor.450mt_ignition': { state: 'off', attributes: {} },
  'binary_sensor.450mt_t_box_online': { state: 'on', attributes: {} },
  'device_tracker.450mt': { state: 'home', attributes: {} },
  'sensor.other_vehicle_odometer': { state: '1', attributes: {} },
};

function entityMap(ids, deviceId = DEVICE) {
  return Object.fromEntries(ids.map((id) => [id, { device_id: deviceId }]));
}

test('labelsFor picks German for de-* and English otherwise', () => {
  assert.equal(labelsFor('de').tab_map, 'Karte');
  assert.equal(labelsFor('de-AT').tab_map, 'Karte');
  assert.equal(labelsFor('en-GB').tab_map, 'Map');
  assert.equal(labelsFor(undefined).tab_map, 'Map');
});

test('normalizeConfig trims strings and drops empty ones', () => {
  const config = normalizeConfig({ entity: ' sensor.450mt_odometer ', name: '  450MT ', image: '', image_navigate: '  ' });
  assert.equal(config.entity, 'sensor.450mt_odometer');
  assert.equal(config.name, '450MT');
  assert.equal('image' in config, false);
  assert.equal('image_navigate' in config, false);
});

test('usable rejects unavailable and unknown states', () => {
  assert.equal(usable({ state: 'on' }), true);
  assert.equal(usable({ state: 'unavailable' }), false);
  assert.equal(usable({ state: 'unknown' }), false);
  assert.equal(usable(undefined), false);
});

test('number parses floats and rejects text', () => {
  assert.equal(number({ state: '12.6' }), 12.6);
  assert.equal(number({ state: 'Sufficient' }), null);
  assert.equal(number(undefined), null);
});

test('pick prefers the shortest matching id', () => {
  const ids = ['sensor.a_t_box_online', 'binary_sensor.a_t_box_online', 'sensor.a_x'];
  assert.equal(pick(ids, '_t_box_online'), 'sensor.a_t_box_online');
});

test('resolveEntities stays inside the configured device', () => {
  const ids = Object.keys(STATES);
  const card = hass(STATES, entityMap(ids));
  const resolved = resolveEntities(card, 'sensor.450mt_odometer');
  assert.equal(resolved.odometer, 'sensor.450mt_odometer');
  assert.equal(resolved.battery, 'sensor.450mt_battery_voltage');
  assert.equal(resolved.fuel_text, 'sensor.450mt_fuel_level_display');
  assert.equal(resolved.riding_time, 'sensor.450mt_riding_time_this_month');
  assert.equal(resolved.gsm, 'sensor.450mt_gsm_signal');
  assert.equal(resolved.ignition, 'binary_sensor.450mt_ignition');
  assert.equal(resolved.tbox, 'binary_sensor.450mt_t_box_online');
  assert.equal(resolved.location, 'device_tracker.450mt');
  assert.equal(resolved.odometer === 'sensor.other_vehicle_odometer', false);
});

test('resolveEntities falls back to every entity without a device id', () => {
  const resolved = resolveEntities(hass(STATES, {}), 'sensor.450mt_odometer');
  assert.equal(resolved.odometer, 'sensor.450mt_odometer');
  assert.equal(resolved.location, 'device_tracker.450mt');
});

test('resolveEntities leaves unknown suffixes empty', () => {
  const resolved = resolveEntities(hass({ 'sensor.450mt_odometer': STATES['sensor.450mt_odometer'] }, {}), 'sensor.450mt_odometer');
  assert.equal(resolved.range, undefined);
  assert.equal(resolved.location, undefined);
});

test('formatDuration renders hours and minutes', () => {
  assert.equal(formatDuration(49449, 'de'), '13 Std 44 min');
  assert.equal(formatDuration(49449, 'en'), '13 h 44 min');
  assert.equal(formatDuration(900, 'de'), '15 min');
  assert.equal(formatDuration(Number.NaN, 'de'), '—');
  assert.equal(formatDuration(-5, 'de'), '—');
});

test('relativeTime uses the language labels', () => {
  const de = labelsFor('de');
  const en = labelsFor('en');
  const now = Date.parse('2026-10-31T12:00:00Z');
  assert.equal(relativeTime('2026-10-31T11:59:45Z', de, now), 'gerade eben');
  assert.equal(relativeTime('2026-10-31T11:35:00Z', de, now), 'vor 25 Min');
  assert.equal(relativeTime('2026-10-31T09:00:00Z', de, now), 'vor 3 Std');
  assert.equal(relativeTime('2026-10-28T12:00:00Z', en, now), '3 d ago');
  assert.equal(relativeTime('not a date', en, now), '—');
});

test('stubConfig picks an odometer sensor', () => {
  const config = stubConfig(hass(STATES, {}));
  assert.equal(config.type, 'custom:cfmoto-vehicle-card');
  assert.match(config.entity, /_odometer$/);
});

test('stubConfig survives an empty state machine', () => {
  assert.deepEqual(stubConfig(hass({}, {})), { type: 'custom:cfmoto-vehicle-card', entity: '' });
});
