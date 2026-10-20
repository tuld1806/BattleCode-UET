/** Keep bot upload instructions aligned with the selected game's protocol. */
document.addEventListener('DOMContentLoaded', async () => {
  const select = document.getElementById('botGame'), help = document.getElementById('botGameHelp');
  if (!select || !help) return;
  const instructions = {
    'cyber-grid': 'Cyber-Grid: định nghĩa get_action(state), trả {"commands": [...]}. Nhận Fog theo đội. 50ms CPU/tick + bank 2000ms; tối đa 1000 tick.',
    'stellar-armada': 'Stellar Armada: định nghĩa get_action(state), trả {"ship_commands": [...], "build_commands": [...]}. 50ms CPU/tick + bank 2000ms; tối đa 1200 tick.',
    'rps-chess': 'RPS Chess: định nghĩa get_move(board, my_player, history), trả ((from_row, from_col), (to_row, to_col)). Tối đa 1 giây/lượt và 200 lượt.'
  };
  // The API fallback also supports servers that render an older profile context.
  if (!select.options.length) {
    try {
      const response = await fetch('/api/games');
      if (!response.ok) throw new Error('Không tải được bộ môn. Hãy tải lại trang.');
      for (const game of await response.json()) { const option = new Option(game.display_name, game.id); option.dataset.slug = game.slug; select.add(option); }
    } catch (error) { help.textContent = error.message; return; }
  }
  const wanted = new URLSearchParams(location.search).get('game');
  const option = [...select.options].find(item => item.dataset.slug === wanted); if (option) select.value = option.value;
  function update() { help.textContent = instructions[select.selectedOptions[0]?.dataset.slug] || 'Chọn bộ môn và xem đặc tả Bot API ở trang chi tiết trước khi nộp.'; }
  select.addEventListener('change', update); update();
});
