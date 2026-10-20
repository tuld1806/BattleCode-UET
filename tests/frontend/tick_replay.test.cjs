/** Native Node regression tests for the renderer's fog and replay contract. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {ReplayModel} = require('../../web/static/js/tick_replay.js');

function replay() {
  return {replay_version: 2, game_slug: 'cyber-grid', frames: [{tick: 0, map_size: 32, units: [
    {id: 1, type: 'WORKER', team: 1, x: 1, y: 1, hp: 50},
    {id: 2, type: 'PAWN', team: 2, x: 3, y: 1, hp: 120},
    {id: 3, type: 'CORE', team: 2, x: 30, y: 30, hp: 1000}
  ], events: [{type: 'attack', source: 1, target: 2}, {type: 'attack', source: 1, target: 3}]}]};
}
test('spectator and team perspectives expose different entity sets', () => {
  const model = new ReplayModel(replay()), frame = model.frames[0];
  assert.equal(model.shown(frame, 0).length, 3);
  assert.deepEqual(model.shown(frame, 1).map(e => e.id), [1, 2]);
  assert.equal(model.visible(frame, 1).has('30,30'), false);
});
test('hidden targets cannot leak through event text', () => {
  const model = new ReplayModel(replay()), frame = model.frames[0];
  assert.equal(model.events(frame, 0).length, 2);
  assert.deepEqual(model.events(frame, 1), [{type: 'attack', source: 1, target: 2}]);
});
test('switching to an eliminated team does not show spectator entities', () => {
  const data = replay(); data.frames[0].units = data.frames[0].units.filter(e => e.team === 2);
  const model = new ReplayModel(data);
  assert.equal(model.shown(model.frames[0], 1).length, 0);
});
test('reject unsupported, empty and discontinuous replay payloads', () => {
  assert.throws(() => new ReplayModel({replay_version: 3}));
  assert.throws(() => new ReplayModel({...replay(), frames: []}));
  const data = replay(); data.frames[0].tick = 9;
  assert.throws(() => new ReplayModel(data));
});
test('reject invalid entity coordinates', () => {
  const data = replay(); data.frames[0].units[0].x = NaN;
  assert.throws(() => new ReplayModel(data));
});
test('stellar snapshots preserve continuous coordinates and entity types', () => {
  const data = {replay_version: 2, game_slug: 'stellar-armada', frames: [{tick: 0, ships: [{id: 'F-1', type: 'FIGHTER', hp: 100, team: 1, x: 250.4, y: 500.1, vx: 1.2, vy: -.5}]}]};
  const model = new ReplayModel(data);
  assert.equal(model.world, 1000);
  assert.equal(model.shown(model.frames[0], 1)[0].x, 250.4);
});

test('combat connects recorded attacks and aggregates actual HP lost', () => {
  const data = replay();
  data.frames.push({...structuredClone(data.frames[0]), tick: 1, events: [
    {type: 'attack', source: 1, target: 2, damage: 20},
    {type: 'collision', unit_id: 2}
  ]});
  data.frames[1].units[1].hp = 90;
  const effects = new ReplayModel(data).combat(1, 0);
  assert.equal(effects.filter(e => e.kind === 'beam').length, 1);
  assert.equal(effects.filter(e => e.kind === 'collision').length, 1);
  assert.deepEqual(effects.filter(e => e.kind === 'damage').map(e => e.damage), [30]);
});

test('hidden attacks and hidden damage do not appear as combat effects', () => {
  const data = replay();
  data.frames.push({...structuredClone(data.frames[0]), tick: 1, events: [{type: 'attack', source: 1, target: 3, damage: 35}]});
  data.frames[1].units[2].hp -= 35;
  assert.deepEqual(new ReplayModel(data).combat(1, 1), []);
});

test('fatal hits retain the last known target position and cap displayed HP loss', () => {
  const data = replay();
  data.frames.push({...structuredClone(data.frames[0]), tick: 1, events: [{type: 'attack', source: 1, target: 2, damage: 150}]});
  data.frames[1].units.splice(1, 1);
  const effects = new ReplayModel(data).combat(1, 0);
  assert.equal(effects.find(e => e.kind === 'beam').target.id, 2);
  assert.equal(effects.find(e => e.kind === 'damage').damage, 120);
  assert.equal(effects.find(e => e.kind === 'damage').destroyed, true);
});

test('collision damage never invents a projectile or shooter', () => {
  const data = replay();
  data.frames.push({...structuredClone(data.frames[0]), tick: 1, events: [{type: 'collision', unit_id: 1}]});
  data.frames[1].units[0].hp -= 10;
  const effects = new ReplayModel(data).combat(1, 0);
  assert.deepEqual(effects.map(e => e.kind), ['collision', 'damage']);
});

test('stellar torpedo hits show an impact and damage without inventing a laser beam', () => {
  const ship = {id: 'F-1', type: 'FIGHTER', hp: 100, team: 1, x: 250, y: 500};
  const model = new ReplayModel({replay_version: 2, game_slug: 'stellar-armada', frames: [
    {tick: 0, ships: [ship], torpedoes: [{id: 'T-1', team: 2, x: 240, y: 500, angle: 0}]},
    {tick: 1, ships: [{...ship, hp: 20}], torpedoes: [], events: [{type: 'torpedo_hit', target: 'F-1', damage: 80}]}
  ]});
  assert.deepEqual(model.combat(1, 0).map(e => e.kind), ['explosion', 'damage']);
  assert.equal(model.combat(1, 0)[1].damage, 80);
});
