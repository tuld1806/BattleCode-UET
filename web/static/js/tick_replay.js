/** Replay-v2 model and Canvas viewer. The renderer never simulates gameplay. */
(function (root) {
  'use strict';
  const COLORS = {1: '#f85149', 2: '#58a6ff', 0: '#8b949e'};
  const VISION = {CORE: 5, WORKER: 5, PAWN: 3, BLASTER: 4, TOWER: 4};
  const HP = {CORE: 1000, WORKER: 50, PAWN: 120, BLASTER: 80, TOWER: 300, FLAGSHIP: 2000, FIGHTER: 100, MINER: 150, TORPEDO_FRIGATE: 400};
  const RANGE = {WORKER: 1, PAWN: 1, BLASTER: 3, TOWER: 4, FIGHTER: 80, TORPEDO_FRIGATE: 300};
  const names = {'cyber-grid': 'Cyber-Grid · Neon Dominion', 'stellar-armada': 'Stellar Armada · Vector Protocols'};
  const TYPES = {CORE: ['C', 'Core', 'Căn cứ chính — bảo vệ để tránh thua trận.'], WORKER: ['W', 'Worker', 'Chiếm node để tăng thu nhập Data.'], PAWN: ['P', 'Pawn', 'Quân cận chiến, đánh mục tiêu ở ô kề.'], BLASTER: ['B', 'Blaster', 'Hỏa lực tầm xa, cần được bảo vệ.'], TOWER: ['T', 'Tower', 'Tháp phòng thủ cố định, kiểm soát khu vực.'], FLAGSHIP: ['◆', 'Flagship', 'Soái hạm — bảo vệ để tránh thua trận.'], FIGHTER: ['▲', 'Fighter', 'Tàu chiến cơ động, dùng laser tầm gần.'], MINER: ['■', 'Miner', 'Khai thác Ore từ tiểu hành tinh.'], TORPEDO_FRIGATE: ['⬡', 'Frigate', 'Tàu phóng ngư lôi tầm xa.']};
  const number = value => Number.isFinite(value) ? Number(value.toFixed(2)).toLocaleString('vi-VN') : '—';

  class ReplayModel {
    constructor(data) {
      if (data.replay_version !== 2 || !names[data.game_slug] || !Array.isArray(data.frames) || !data.frames.length) throw new Error('Replay chưa có frame hoặc chưa hỗ trợ phiên bản/game này.');
      this.data = data;
      this.grid = data.game_slug === 'cyber-grid';
      this.frames = data.frames;
      if (!this.frames.every((f, i) => f && f.tick === i && Array.isArray(f[this.grid ? 'units' : 'ships']))) throw new Error('Dữ liệu tick không hợp lệ hoặc không liên tục.');
      if (!this.frames.every(frame => this.entities(frame).every(e => e && [1, 2].includes(e.team) && ['number', 'string'].includes(typeof e.id) && typeof e.type === 'string' && ['x', 'y', 'hp'].every(key => Number.isFinite(e[key]))))) throw new Error('Dữ liệu đơn vị trong replay không hợp lệ.');
      this.initialHealth = new Map(this.entities(this.frames[0]).map(e => [e.id, e.hp]));
      this.world = this.grid ? this.frames[0].map_size : 1000;
      if (!Number.isFinite(this.world) || this.world <= 0) throw new Error('Kích thước bản đồ không hợp lệ.');
    }
    entities(frame) { return frame[this.grid ? 'units' : 'ships']; }
    visible(frame, team) {
      if (!this.grid || !team) return null;
      const cells = new Set();
      this.entities(frame).filter(e => e.team === team).forEach(e => {
        const radius = VISION[e.type] || 0;
        for (let x = Math.max(0, e.x - radius); x <= Math.min(this.world - 1, e.x + radius); x++) {
          for (let y = Math.max(0, e.y - radius); y <= Math.min(this.world - 1, e.y + radius); y++) cells.add(`${x},${y}`);
        }
      });
      return cells;
    }
    shown(frame, team) {
      const cells = this.visible(frame, team);
      return this.entities(frame).filter(e => !cells || cells.has(`${e.x},${e.y}`));
    }
    events(frame, team) {
      const list = Array.isArray(frame.events) ? frame.events : [];
      if (!this.grid || !team) return list;
      const ids = new Set(this.shown(frame, team).map(e => String(e.id)));
      // A removed/hidden target cannot leak its position through the log or inspector.
      return list.filter(event => [event.unit_id, event.source, event.target, ...(event.ships || [])].filter(v => v !== undefined).every(id => ids.has(String(id))));
    }
  }

  // Derive visual effects from recorded events and HP, never simulate damage.
  ReplayModel.prototype.combat = function (index, team) {
    const frame = this.frames[index], previous = this.frames[Math.max(0, index - 1)];
    const current = new Map(this.entities(frame).map(e => [String(e.id), e]));
    const before = new Map(this.entities(previous).map(e => [String(e.id), e]));
    const cells = this.visible(frame, team);
    const locate = id => {
      const entity = current.get(String(id)) || before.get(String(id));
      return entity && (!cells || cells.has(`${entity.x},${entity.y}`)) ? entity : null;
    };
    const effects = [];
    for (const event of frame.events || []) {
      if (['attack', 'laser'].includes(event.type)) {
        const source = locate(event.source), target = locate(event.target);
        if (source && target) effects.push({kind: 'beam', source, target, damage: event.damage});
      }
      if (event.type === 'torpedo_hit') {
        const target = locate(event.target);
        if (target) effects.push({kind: 'explosion', target});
      }
      if (event.type === 'collision') for (const id of event.ships || [event.unit_id]) {
        const target = locate(id);
        if (target) effects.push({kind: 'collision', target});
      }
    }
    // Aggregate simultaneous hits without counting recorded attacks twice.
    if (index > 0) for (const [id, old] of before) {
      const target = locate(id), remaining = current.get(id)?.hp || 0;
      if (target && remaining < old.hp) effects.push({kind: 'damage', target, damage: old.hp - remaining, destroyed: !current.has(id)});
    }
    return effects;
  };

  class TickReplay {
    constructor(data) {
      this.model = new ReplayModel(data);
      this.data = data;
      this.index = 0; this.team = 0; this.selected = ''; this.zoom = 1; this.pan = {x: 0, y: 0};
      this.playing = false; this.speed = 1; this.last = 0; this.raf = null;
      this.el = id => document.getElementById(id);
      this.canvas = this.el('tickCanvas'); this.ctx = this.canvas.getContext('2d');
      if (!this.ctx) throw new Error('Trình duyệt không hỗ trợ Canvas 2D.');
      this.el('tickReplay').hidden = false;
      this.el('tickGameLabel').textContent = names[data.game_slug];
      this.el('tickBack').href = `/games/${data.game_slug}`;
      this.el('tickMatchTitle').textContent = `Trận #${data.match_id} · Replay theo tick`;
      for (const team of [1, 2]) this.el(`tickTeam${team}`).textContent = `${team === 1 ? 'Đỏ' : 'Xanh'} · ${data[`player${team}`]?.username || `Đội ${team}`}`;
      const reasons = {max_ticks: 'Hết giới hạn tick', base_destroyed: 'Căn cứ bị phá hủy', draw: 'Hòa', error: 'Bot gặp lỗi', invalid_move: 'Lệnh không hợp lệ', invalid_bot: 'Bot không đúng giao thức', timeout: 'Hết ngân sách thời gian'};
      this.el('tickResult').textContent = `${data.winner ? `Đội ${data.winner} thắng` : 'Trận hòa'} · ${reasons[data.win_reason] || data.win_reason || 'Chưa có kết quả'} · ${data.total_ticks ?? this.model.frames.length - 1} tick`;
      const errors = [data.bot1_error && `Đội 1: ${data.bot1_error}`, data.bot2_error && `Đội 2: ${data.bot2_error}`].filter(Boolean);
      if (errors.length) this.el('tickResult').textContent += ` · ${errors.join(' · ')}`;
      this.el('tickRules').href = `/games/${data.game_slug}`;
      const guide = this.model.grid ? [
        ['01 · Mục tiêu', 'Phá Core đối thủ và giữ Core của bạn sống sót.'],
        ['02 · Phát triển', 'Worker chiếm node để kiếm Data; dùng Data tạo quân và xây tháp.'],
        ['03 · Giao chiến', 'Pawn đánh gần, Blaster bắn tối đa 3 ô, Tower giữ vị trí. Đòn đánh có hiệu lực ngay trong tick. Cùng đi vào một ô gây va chạm, mất 10 HP; không phải lúc nào mất máu cũng do bị bắn.']
      ] : [
        ['01 · Mục tiêu', 'Phá Flagship đối thủ và bảo vệ soái hạm của bạn.'],
        ['02 · Phát triển', 'Miner khai thác Ore tại tiểu hành tinh để phục vụ hạm đội.'],
        ['03 · Điều khiển', 'Tàu có quán tính: hướng mũi tàu và hướng di chuyển có thể khác nhau. Fighter dùng laser; Frigate phóng ngư lôi.']
      ];
      this.el('tickGuide').replaceChildren(...guide.map(([title, text]) => {
        const card = document.createElement('article'), heading = document.createElement('h3'), body = document.createElement('p');
        heading.textContent = title; body.textContent = text; card.append(heading, body); return card;
      }));
      this.el('tickLegend').replaceChildren(...Object.entries(TYPES).filter(([type]) => this.model.grid ? ['CORE','WORKER','PAWN','BLASTER','TOWER'].includes(type) : ['FLAGSHIP','FIGHTER','MINER','TORPEDO_FRIGATE'].includes(type)).map(([, [icon, name, role]]) => {
        const row = document.createElement('span'), symbol = document.createElement('b'); symbol.textContent = icon; row.append(symbol, document.createTextNode(name)); row.title = role; return row;
      }));
      this.el('tickPerspective').disabled = !this.model.grid;
      this.el('tickVectors').closest('label').hidden = this.model.grid;
      if (!this.model.grid) this.el('tickPerspective').title = 'Stellar sử dụng thông tin toàn bản đồ theo engine hiện tại.';
      for (const id of ['tickTimeline', 'tickNumber']) this.el(id).max = this.model.frames.length - 1;
      this.bind();
      this.observer = new ResizeObserver(() => this.draw()); this.observer.observe(this.canvas);
      document.addEventListener('visibilitychange', () => { if (document.hidden) this.pause(); });
      this.seek(0);
    }
    bind() {
      const click = (id, fn) => this.el(id).addEventListener('click', fn);
      click('tickPlay', () => this.playing ? this.pause() : this.play());
      for (const [id, value] of [['tickFirst', 0], ['tickLast', this.model.frames.length - 1]]) click(id, () => { this.pause(); this.seek(value); });
      click('tickPrev', () => { this.pause(); this.seek(this.index - 1); });
      click('tickNext', () => { this.pause(); this.seek(this.index + 1); });
      click('tickNextCombat', () => {
        this.pause();
        const next = this.model.frames.findIndex((frame, index) => index > this.index && this.model.combat(index, this.team).length);
        if (next >= 0) this.seek(next);
        this.el('tickCombatStatus').textContent = next >= 0 ? `Đang xem giao tranh tại tick ${next}.` : 'Không còn giao tranh trong góc nhìn này. Hãy về đầu để xem lại.';
      });
      for (const id of ['tickTimeline', 'tickNumber']) this.el(id).addEventListener('input', event => { this.pause(); this.seek(Number(event.target.value)); });
      this.el('tickSpeed').addEventListener('change', event => { this.speed = Number(event.target.value); });
      this.el('tickPerspective').addEventListener('change', event => { this.team = Number(event.target.value); this.selected = ''; this.seek(this.index); });
      this.el('tickEntity').addEventListener('change', event => { this.selected = event.target.value; this.inspect(); this.draw(); });
      for (const id of ['tickGrid', 'tickVectors', 'tickRange']) this.el(id).addEventListener('change', () => this.draw());
      click('tickZoomIn', () => this.setZoom(this.zoom * 1.3)); click('tickZoomOut', () => this.setZoom(this.zoom / 1.3));
      click('tickFocus', () => {
        const e = this.model.shown(this.frame(), this.team).find(e => String(e.id) === this.selected);
        if (!e) return;
        this.zoom = this.model.grid ? 3 : 2.5;
        const scale = (Math.min(this.width, this.height) - 32) / this.model.world * this.zoom;
        this.pan = {x: (this.model.world / 2 - e.x - (this.model.grid ? .5 : 0)) * scale, y: (this.model.world / 2 - e.y - (this.model.grid ? .5 : 0)) * scale}; this.draw();
      });
      click('tickFit', () => { this.zoom = 1; this.pan = {x: 0, y: 0}; this.draw(); });
      document.querySelectorAll('[data-pan]').forEach(button => button.addEventListener('click', () => {
        const delta = {left: [40, 0], right: [-40, 0], up: [0, 40], down: [0, -40]}[button.dataset.pan];
        this.pan.x += delta[0]; this.pan.y += delta[1]; this.draw();
      }));
      this.canvas.addEventListener('keydown', event => {
        if (event.key === ' ') { event.preventDefault(); this.playing ? this.pause() : this.play(); }
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); this.pause(); this.seek(this.index + (event.key === 'ArrowLeft' ? -1 : 1)); }
      });
      this.canvas.addEventListener('pointerdown', event => {
        this.drag = {x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY};
        this.canvas.setPointerCapture(event.pointerId);
      });
      this.canvas.addEventListener('pointermove', event => {
        if (!this.drag) return;
        this.pan.x += event.clientX - this.drag.x; this.pan.y += event.clientY - this.drag.y;
        this.drag.x = event.clientX; this.drag.y = event.clientY; this.draw();
      });
      this.canvas.addEventListener('pointerup', event => {
        if (this.drag && Math.hypot(event.clientX - this.drag.startX, event.clientY - this.drag.startY) < 5) {
          const rect = this.canvas.getBoundingClientRect();
          const point = this.worldPoint(event.clientX - rect.left, event.clientY - rect.top);
          const near = this.model.shown(this.frame(), this.team).map(entity => ({entity, distance: Math.hypot(entity.x + (this.model.grid ? .5 : 0) - point.x, entity.y + (this.model.grid ? .5 : 0) - point.y)})).sort((a, b) => a.distance - b.distance)[0];
          this.selected = near && near.distance < (this.model.grid ? 1 : 25) ? String(near.entity.id) : '';
          this.el('tickEntity').value = this.selected; this.inspect(); this.draw();
        }
        this.drag = null;
      });
      this.canvas.addEventListener('pointercancel', () => { this.drag = null; });
    }
    frame() { return this.model.frames[this.index]; }
    setZoom(value) { this.zoom = Math.max(.5, Math.min(8, value)); this.draw(); }
    pause() { this.playing = false; cancelAnimationFrame(this.raf); this.el('tickPlay').textContent = 'Phát'; this.el('tickPlay').setAttribute('aria-pressed', 'false'); }
    play() {
      if (this.model.frames.length < 2) return;
      if (this.index === this.model.frames.length - 1) this.seek(0);
      this.playing = true; this.last = performance.now(); this.el('tickPlay').textContent = 'Dừng'; this.el('tickPlay').setAttribute('aria-pressed', 'true');
      const loop = now => {
        if (!this.playing) return;
        const steps = Math.floor((now - this.last) * this.speed / 100);
        if (steps) { this.seek(this.index + steps); this.last = now; }
        if (this.index >= this.model.frames.length - 1) this.pause();
        else this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    }
    seek(index) {
      this.index = Math.max(0, Math.min(this.model.frames.length - 1, Math.round(Number.isFinite(index) ? index : 0)));
      const frame = this.frame(), shown = this.model.shown(frame, this.team);
      for (const id of ['tickTimeline', 'tickNumber']) this.el(id).value = this.index;
      this.el('tickCount').textContent = `/ ${this.model.frames.length - 1}`;
      this.el('tickEventNumber').textContent = frame.tick;
      this.el('tickMapCaption').textContent = `${this.model.grid ? `${this.model.world} × ${this.model.world} ô · (0,0) trên trái` : 'Không gian 1000 × 1000 · +y xuống'} · zoom ${number(this.zoom)}×`;
      const options = [new Option('Chọn trên bản đồ hoặc danh sách', '')];
      shown.forEach(e => options.push(new Option(`${TYPES[e.type]?.[1] || e.type} #${e.id} · Đội ${e.team}`, String(e.id))));
      this.el('tickEntity').replaceChildren(...options);
      if (!shown.some(e => String(e.id) === this.selected)) this.selected = '';
      this.el('tickEntity').value = this.selected;
      for (const team of [1, 2]) {
        if (this.model.grid && this.team && this.team !== team) { this.el(`tickStats${team}`).textContent = 'Thông tin ngoài góc nhìn được ẩn.'; continue; }
        const units = shown.filter(e => e.team === team), base = units.find(e => e.type === (this.model.grid ? 'CORE' : 'FLAGSHIP'));
        const resources = (this.model.grid ? frame.resources : frame.ore_reserves)?.[team];
        const container = this.el(`tickStats${team}`);
        const baseName = this.model.grid ? 'Core' : 'Flagship';
        const stats = [[`${baseName} · HP`, base ? number(base.hp) : '0'], ['Đơn vị', units.length], [this.model.grid ? 'Data' : 'Ore', number(resources)]];
        if (this.model.grid) { const cells = this.model.visible(frame, this.team); stats.push(['Node đang giữ', (frame.nodes || []).filter(n => n.occupied_by_team === team && (!cells || cells.has(`${n.x},${n.y}`))).length]); }
        container.replaceChildren(...stats.map(([label, value]) => {
          const tile = document.createElement('div'), caption = document.createElement('span'), amount = document.createElement('strong'); caption.textContent = label; amount.textContent = value; tile.append(caption, amount); return tile;
        }));

      }
      this.el('tickVisibilityNote').textContent = this.model.grid && this.team ? `Fog đội ${this.team}: chỉ hiện đơn vị đang thấy. Nhật ký và inspector cũng được lọc.` : 'Góc nhìn spectator. Màu đỏ: đội 1; xanh: đội 2. Chọn đối tượng để xem chỉ số.';
      const cells = this.model.visible(frame, this.team);
      this.el('tickResources').textContent = this.model.grid ? (frame.nodes || []).filter(n => !cells || cells.has(`${n.x},${n.y}`)).map(n => `Node (${n.x},${n.y}): ${n.occupied_by_team ? 'đội ' + n.occupied_by_team : 'trung lập'}`).join(' · ') || 'Không có node trong vùng nhìn.' : (frame.asteroids || []).map(a => `${a.id} (${number(a.x)}, ${number(a.y)}): ${number(a.ore_remaining)} Ore`).join(' · ');
      const events = this.model.events(frame, this.team).slice(0, 100);
      const combat = this.model.combat(this.index, this.team);
      this.el('tickCombatStatus').textContent = combat.length ? `Tick ${this.index}: ${combat.filter(e => e.kind === 'beam').length} đòn đánh · ${combat.filter(e => e.kind === 'collision').length} đơn vị va chạm · ${combat.filter(e => e.kind === 'damage').length} đơn vị mất HP.` : `Tick ${this.index}: không có sát thương hoặc đòn đánh hiển thị.`;
      this.el('tickEvents').replaceChildren(...(events.length ? events : ['Không có sự kiện hiển thị tại tick này.']).map(event => {
        const eventNames = {collision: 'Va chạm', attack: 'Tấn công', damage: 'Nhận sát thương', destroyed: 'Bị phá hủy', spawn: 'Tạo đơn vị', capture: 'Chiếm node', mine: 'Khai thác', deposit: 'Nộp tài nguyên', laser: 'Bắn laser', torpedo: 'Phóng ngư lôi', torpedo_hit: 'Ngư lôi trúng đích', intercept: 'Đánh chặn ngư lôi'};
        const labels = {unit_id: 'Đơn vị', source: 'Nguồn', target: 'Mục tiêu', damage: 'Sát thương', amount: 'Số lượng', team: 'Đội', ships: 'Các tàu'};
        const li = document.createElement('li'); li.textContent = typeof event === 'string' ? event : Object.entries(event).map(([key, value]) => key === 'type' ? (eventNames[value] || value) : `${labels[key] || key}: ${Array.isArray(value) ? value.join(', ') : value}`).join(' · '); return li;
      }));
      this.el('tickCommands').textContent = frame.actions ? JSON.stringify(this.team ? frame.actions[this.team] || {} : frame.actions, null, 2) : 'Tick khởi tạo chưa có lệnh bot.';
      this.inspect(); this.draw();
    }
    inspect() {
      const entity = this.model.shown(this.frame(), this.team).find(e => String(e.id) === this.selected);
      this.el('tickFocus').disabled = !entity;
      this.el('tickRole').textContent = entity ? (TYPES[entity.type]?.[2] || entity.type) : 'Nhấp vào một quân hoặc tàu trên bản đồ để khám phá.';
      const labels = {id: 'ID', type: 'Loại', team: 'Đội', hp: 'HP', x: 'x', y: 'y', vx: 'vx', vy: 'vy', orientation: 'Góc (rad)', omega: 'Vận tốc góc', ore: 'Ore mang theo', weapon_cooldown: 'Cooldown'};
      const children = [];
      Object.entries(entity || {type: 'Chưa chọn đơn vị'}).forEach(([key, value]) => {
        if (!labels[key]) return;
        const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = labels[key]; dd.textContent = key === 'type' ? (TYPES[value]?.[1] || value) : typeof value === 'number' ? number(value) : String(value); children.push(dt, dd);
      });
      this.el('tickDetails').replaceChildren(...children);
    }
    worldPoint(x, y) { return {x: (x - this.width / 2 - this.pan.x) / this.scale + this.model.world / 2, y: (y - this.height / 2 - this.pan.y) / this.scale + this.model.world / 2}; }
    draw() {
      const rect = this.canvas.getBoundingClientRect(); if (!rect.width || !rect.height) return;
      const dpr = window.devicePixelRatio || 1;
      this.width = rect.width; this.height = rect.height;
      if (this.canvas.width !== Math.round(rect.width * dpr) || this.canvas.height !== Math.round(rect.height * dpr)) { this.canvas.width = Math.round(rect.width * dpr); this.canvas.height = Math.round(rect.height * dpr); }
      const ctx = this.ctx, frame = this.frame(), world = this.model.world;
      this.el('tickMapCaption').textContent = `${this.model.grid ? `${world} × ${world} ô · (0,0) trên trái` : 'Không gian 1000 × 1000 · +y xuống'} · zoom ${number(this.zoom)}×`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.fillStyle = '#090e15'; ctx.fillRect(0, 0, rect.width, rect.height);
      this.scale = (Math.min(rect.width, rect.height) - 32) / world * this.zoom;
      ctx.save(); ctx.translate(rect.width / 2 + this.pan.x, rect.height / 2 + this.pan.y); ctx.scale(this.scale, this.scale); ctx.translate(-world / 2, -world / 2);
      ctx.fillStyle = '#111a25'; ctx.fillRect(0, 0, world, world); ctx.strokeStyle = '#495564'; ctx.lineWidth = 1 / this.scale; ctx.strokeRect(0, 0, world, world);
      const visible = this.model.visible(frame, this.team);
      if (this.el('tickGrid').checked) {
        const step = this.model.grid ? 1 : 100; ctx.strokeStyle = '#263342'; ctx.beginPath();
        for (let i = 0; i <= world; i += step) { ctx.moveTo(i, 0); ctx.lineTo(i, world); ctx.moveTo(0, i); ctx.lineTo(world, i); } ctx.stroke();
      }
      if (this.model.grid) {
        (frame.obstacles || []).forEach(([x, y]) => { if (!visible || visible.has(`${x},${y}`)) { ctx.fillStyle = '#536071'; ctx.fillRect(x + .1, y + .1, .8, .8); } });
        (frame.nodes || []).forEach(node => { if (!visible || visible.has(`${node.x},${node.y}`)) { ctx.fillStyle = COLORS[node.occupied_by_team] || COLORS[0]; this.polygon(node.x + .5, node.y + .5, .4, 4, Math.PI / 4); } });
      } else {
        (frame.asteroids || []).forEach(a => { ctx.fillStyle = a.ore_remaining > 0 ? '#8b949e' : '#30363d'; ctx.beginPath(); ctx.arc(a.x, a.y, 12, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#c9d1d9'; ctx.font = `${10 / this.scale}px monospace`; ctx.fillText(`${a.id}: ${a.ore_remaining}`, a.x + 16, a.y); });
        (frame.torpedoes || []).forEach(t => {
          const size = 5 / this.scale, angle = t.angle || 0;
          ctx.save(); ctx.strokeStyle = '#ffd166'; ctx.lineWidth = 3 / this.scale;
          ctx.beginPath(); ctx.moveTo(t.x, t.y); ctx.lineTo(t.x - Math.cos(angle) * size * 4, t.y - Math.sin(angle) * size * 4); ctx.stroke();
          ctx.fillStyle = '#fff2b3'; this.polygon(t.x, t.y, size, 3, angle);
          ctx.font = `${11 / this.scale}px sans-serif`; ctx.fillText('Ngư lôi', t.x + size * 2, t.y - size * 2); ctx.restore();
        });
      }
      this.model.shown(frame, this.team).forEach(e => {
        const grid = this.model.grid, x = e.x + (grid ? .5 : 0), y = e.y + (grid ? .5 : 0), selected = String(e.id) === this.selected;
        const radius = grid ? .39 : Math.max(({FLAGSHIP: 14, FIGHTER: 6, MINER: 8, TORPEDO_FRIGATE: 10}[e.type] || 6), (e.type === 'FLAGSHIP' ? 13 : 8) / this.scale);
        ctx.fillStyle = COLORS[e.team] || COLORS[0]; ctx.strokeStyle = selected ? '#ffffff' : '#090e15'; ctx.lineWidth = (selected ? 2 : 1) / this.scale;
        if (selected && this.el('tickRange').checked && RANGE[e.type]) { ctx.save(); ctx.globalAlpha = .12; const r = RANGE[e.type]; if (grid) ctx.fillRect(x - r - .5, y - r - .5, r * 2 + 1, r * 2 + 1); else { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); } ctx.restore(); }
        if (grid) {
          const sides = {CORE: 6, WORKER: 4, PAWN: 4, BLASTER: 3, TOWER: 8}[e.type] || 4;
          this.polygon(x, y, radius, sides, e.type === 'WORKER' ? 0 : Math.PI / 4, true);
          ctx.fillStyle = '#07111c'; ctx.font = `bold ${.4}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText(e.type[0], x, y + .14); ctx.textAlign = 'start';
        }
        else { this.polygon(x, y, radius, {FLAGSHIP: 4, FIGHTER: 3, MINER: 4, TORPEDO_FRIGATE: 6}[e.type] || 4, (e.orientation || 0) + (e.type === 'MINER' ? Math.PI / 4 : 0), true); }
        if (selected) { ctx.strokeStyle = '#fff'; ctx.lineWidth = 2 / this.scale; ctx.beginPath(); ctx.arc(x, y, radius + 4 / this.scale, 0, Math.PI * 2); ctx.stroke(); }
        if (e.type === 'CORE' || e.type === 'FLAGSHIP') { ctx.fillStyle = '#edf4ff'; ctx.font = `bold ${12 / this.scale}px sans-serif`; ctx.textAlign = 'center'; ctx.fillText(`${TYPES[e.type][1]} · Đ${e.team}`, x, y + radius + 16 / this.scale); ctx.textAlign = 'start'; }
        // HP bars use the first observed health as a fallback for customized game settings.
        const maxHp = this.model.initialHealth.get(e.id) || HP[e.type] || e.hp || 1;
        ctx.fillStyle = '#30363d'; ctx.fillRect(x - radius, y - radius - radius * .6, radius * 2, radius * .22);
        ctx.fillStyle = '#3fb950'; ctx.fillRect(x - radius, y - radius - radius * .6, radius * 2 * Math.max(0, Math.min(1, e.hp / maxHp)), radius * .22);
        if (!grid && this.el('tickVectors').checked) {
          if (selected) {
            ctx.strokeStyle = COLORS[e.team]; ctx.beginPath(); let begun = false;
            this.model.frames.slice(Math.max(0, this.index - 20), this.index + 1).forEach(f => { const past = this.model.entities(f).find(ship => ship.id === e.id); if (past) { begun ? ctx.lineTo(past.x, past.y) : ctx.moveTo(past.x, past.y); begun = true; } }); ctx.stroke();
          }
          ctx.strokeStyle = '#e3b341'; ctx.beginPath(); ctx.moveTo(x, y); const speed = Math.hypot(e.vx || 0, e.vy || 0), vectorScale = speed ? Math.min(15, 60 / this.scale / speed) : 0; ctx.lineTo(x + (e.vx || 0) * vectorScale, y + (e.vy || 0) * vectorScale); ctx.stroke(); ctx.strokeStyle = '#c9d1d9'; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + Math.cos(e.orientation || 0) * 20, y + Math.sin(e.orientation || 0) * 20); ctx.stroke();
        }
      });
      this.drawCombat();
      if (visible) { ctx.fillStyle = '#05080eee'; for (let x = 0; x < world; x++) for (let y = 0; y < world; y++) if (!visible.has(`${x},${y}`)) ctx.fillRect(x, y, 1, 1); }
      ctx.restore();
    }
    drawCombat() {
      const ctx = this.ctx, scale = this.scale, offset = this.model.grid ? .5 : 0;
      const point = e => ({x: e.x + offset, y: e.y + offset});
      ctx.save();
      for (const effect of this.model.combat(this.index, this.team)) {
        const target = point(effect.target);
        if (effect.kind === 'beam') {
          const source = point(effect.source), angle = Math.atan2(target.y - source.y, target.x - source.x);
          ctx.strokeStyle = COLORS[effect.source.team]; ctx.lineWidth = 5 / scale; ctx.globalAlpha = .55;
          ctx.beginPath(); ctx.moveTo(source.x, source.y); ctx.lineTo(target.x, target.y); ctx.stroke();
          ctx.strokeStyle = '#fff6cc'; ctx.lineWidth = 2 / scale; ctx.globalAlpha = 1; ctx.stroke();
          ctx.fillStyle = '#ffe08a'; this.polygon(target.x, target.y, 5 / scale, 3, angle);
        } else if (effect.kind === 'collision' || effect.kind === 'explosion') {
          const radius = (this.model.grid ? .55 : 16 / scale);
          ctx.strokeStyle = '#ffb454'; ctx.lineWidth = 2 / scale;
          ctx.beginPath(); ctx.arc(target.x, target.y, radius, 0, Math.PI * 2); ctx.stroke();
          ctx.beginPath(); ctx.moveTo(target.x - radius * .6, target.y - radius * .6); ctx.lineTo(target.x + radius * .6, target.y + radius * .6); ctx.moveTo(target.x + radius * .6, target.y - radius * .6); ctx.lineTo(target.x - radius * .6, target.y + radius * .6); ctx.stroke();
        } else if (effect.kind === 'damage') {
          const text = `−${number(effect.damage)} HP${effect.destroyed ? ' · Hạ' : ''}`;
          ctx.font = `bold ${13 / scale}px sans-serif`; ctx.textAlign = 'center'; ctx.lineWidth = 4 / scale; ctx.strokeStyle = '#090e15'; ctx.fillStyle = '#ffd166';
          const y = target.y - (this.model.grid ? .75 : 23 / scale);
          ctx.strokeText(text, target.x, y); ctx.fillText(text, target.x, y);
        }
      }
      ctx.restore();
    }
    polygon(x, y, radius, sides, angle, stroke = false) {
      const ctx = this.ctx; ctx.beginPath();
      for (let i = 0; i < sides; i++) { const a = angle + i * Math.PI * 2 / sides; const px = x + radius * Math.cos(a), py = y + radius * Math.sin(a); i ? ctx.lineTo(px, py) : ctx.moveTo(px, py); }
      ctx.closePath(); ctx.fill(); if (stroke) ctx.stroke();
    }
  }
  root.TickReplay = TickReplay; root.TickReplayModel = ReplayModel;
  if (typeof module !== 'undefined') module.exports = {ReplayModel};
})(typeof window !== 'undefined' ? window : globalThis);
