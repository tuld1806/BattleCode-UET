/** Game-specific matches, challenge dispatch, starter downloads and tab navigation. */
document.addEventListener('DOMContentLoaded', () => {
  const portal = document.getElementById('gamePortal');
  if (!portal) return;
  const gameId = Number(portal.dataset.gameId), slug = portal.dataset.slug;
  const body = document.getElementById('gameMatchesBody'), status = document.getElementById('gameMatchesStatus');
  const more = document.getElementById('moreGameMatches'), refresh = document.getElementById('refreshGameMatches');
  let offset = 0, loading = false, count = 0;
  const tabs = [...document.querySelectorAll('.tab-btn')];
  document.querySelector('.tab-nav').setAttribute('role', 'tablist');
  tabs.forEach((button, index) => {
    const id = button.id.replace('btn-', '');
    button.setAttribute('role', 'tab'); button.setAttribute('aria-controls', id);
    button.setAttribute('aria-selected', String(index === 0));
    const panel = document.getElementById(id); panel.setAttribute('role', 'tabpanel'); panel.setAttribute('aria-labelledby', button.id);
    button.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].click(); tabs[next].focus();
    });
  });
  if (location.hash && tabs.some(button => button.id === 'btn-' + location.hash.slice(1))) window.switchTab(location.hash.slice(1));
  tabs.forEach(button => button.addEventListener('click', () => history.replaceState(null, '', '#' + button.id.replace('btn-', ''))));
  function errorText(data, fallback) {
    if (Array.isArray(data.detail)) return data.detail.map(item => item.msg).join('; ');
    return typeof data.detail === 'string' ? data.detail : fallback;
  }
  async function loadMatches(reset) {
    if (loading) return;
    loading = true; more.disabled = true; refresh.disabled = true;
    if (reset) { offset = 0; count = 0; body.replaceChildren(); }
    status.textContent = 'Đang tải trận đấu…';
    try {
      const response = await fetch(`/api/matches?limit=100&offset=${offset}`);
      if (!response.ok) throw new Error('Không thể tải trận đấu. Bấm Làm mới để thử lại.');
      const matches = await response.json();
      matches.filter(match => (match.game_id || 1) === gameId).forEach(match => {
        count++;
        const row = document.createElement('tr');
        const ready = Boolean(match.replay_path), failed = String(match.win_reason || '').startsWith('Execution error:');
        const result = !match.win_reason ? 'Đang chờ / đang chạy' : failed ? 'Lỗi thực thi' : match.winner_id ? `${match.winner_id === match.player1_id ? 'Đỏ' : 'Xanh'} thắng · ${match.win_reason}` : `Hòa · ${match.win_reason}`;
        [`#${match.id}`, match.player1?.username || 'Đội 1', match.player2?.username || 'Đội 2', result, ready ? String(match.total_turns) : '—'].forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.append(cell); });
        const cell = document.createElement('td');
        if (ready) { const link = document.createElement('a'); link.href = `/replay/${match.id}`; link.className = 'btn btn-sm'; link.textContent = 'Xem replay'; cell.append(link); }
        else cell.textContent = failed ? 'Chưa có replay' : 'Bấm Làm mới để cập nhật';
        row.append(cell); body.append(row);
      });
      offset += matches.length; more.hidden = matches.length < 100;
      status.textContent = count ? `${count} trận của bộ môn này. Đã kiểm tra ${offset} trận gần nhất trên hệ thống.` : 'Chưa tìm thấy trận của game trong các trận vừa tải. Có thể tải thêm hoặc gửi thách đấu.';
    } catch (error) { status.textContent = error.message; }
    finally { loading = false; more.disabled = false; refresh.disabled = false; }
  }
  refresh.addEventListener('click', () => loadMatches(true)); more.addEventListener('click', () => loadMatches(false));
  document.getElementById('btn-tab-matches').addEventListener('click', () => { if (offset === 0) loadMatches(true); });
  if (location.hash === '#tab-matches') loadMatches(true);
  const form = document.getElementById('gameChallengeForm');
  if (form) {
    const opponent = document.getElementById('gameOpponent'), feedback = document.getElementById('gameChallengeStatus');
    async function opponents() {
      try {
        const response = await fetch(`/api/games/${encodeURIComponent(slug)}/leaderboard`);
        if (!response.ok) throw new Error('Không tải được danh sách đối thủ. Hãy tải lại trang.');
        const players = await response.json();
        opponent.replaceChildren(new Option('Chọn người chơi có bot active', ''));
        players.filter(player => player.id !== Number(portal.dataset.userId) && player.has_active_bot).forEach(player => opponent.add(new Option(`${player.username} · Elo ${player.elo}`, player.id)));
        if (opponent.options.length === 1) feedback.textContent = 'Chưa có đối thủ có bot active. Mời người chơi khác nộp bot cho game này.';
      } catch (error) { opponent.replaceChildren(new Option('Không tải được đối thủ', '')); feedback.textContent = error.message; }
    }
    opponents();
    form.addEventListener('submit', async event => {
      event.preventDefault(); const button = form.querySelector('button'); button.disabled = true; form.setAttribute('aria-busy', 'true'); feedback.textContent = 'Đang gửi thách đấu…';
      try {
        const response = await fetch('/api/matches/challenge', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({game_id: gameId, opponent_id: Number(opponent.value)})});
        const data = await response.json();
        if (!response.ok) throw new Error(errorText(data, 'Không thể thách đấu. Kiểm tra bot active và giờ mở FFA.'));
        feedback.textContent = `Đã xếp hàng trận #${data.match_id}. Bấm Làm mới để xem kết quả khi trận hoàn tất.`;
        await loadMatches(true);
      } catch (error) { feedback.textContent = error.message; }
      finally { button.disabled = false; form.removeAttribute('aria-busy'); }
    });
  }
  const download = document.getElementById('downloadGameBot');
  if (download) download.addEventListener('click', () => {
    const output = slug === 'cyber-grid' ? '{"commands": []}' : '{"ship_commands": [], "build_commands": []}';
    const source = slug === 'rps-chess' ? '"""Minimal legal-move RPS bot."""\nfrom engine.game import GameState\n\ndef get_move(board, my_player, history):\n    moves = GameState(board=board, turn=my_player).get_valid_moves()\n    return moves[0] if moves else None\n' : `"""Minimal ${slug} bot. Replace the idle action with your strategy."""\n\ndef get_action(state):\n    return ${output}\n`;
    const url = URL.createObjectURL(new Blob([source], {type: 'text/x-python;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `${slug.replaceAll('-', '_')}_bot.py`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
});
