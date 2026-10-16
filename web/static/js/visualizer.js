/**
 * Battlecode 9x9 RPS Platform - Interactive Replay Visualizer
 *
 * Provides turn-by-turn playback, slider scrubbing, speed toggles,
 * move highlights, piece counting, and SAN move logging for 9x9 RPS Chess.
 */

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'];
const RANKS = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];
const TYPE_ICONS = { R: '✊', P: '✋', S: '✌' };
const TYPE_NAMES = { R: 'Rock', P: 'Paper', S: 'Scissors' };

/** Helper to format internal row/col to coordinate string (e.g. 0, 0 -> a1) */
function getCoordName(row, col) {
  return FILES[col] + RANKS[row];
}

/** Deep clone a 9x9 board matrix */
function cloneBoard(board) {
  return board.map(row => row.map(cell => (cell ? { ...cell } : null)));
}

class ReplayVisualizer {
  /**
   * Initialize the Replay Visualizer.
   * @param {Object} options Configuration options
   * @param {string|number} options.matchId Unique match ID to fetch replay for
   * @param {Object} [options.replayData] Preloaded replay data (optional)
   * @param {string} [options.containerId='visualizerApp'] Parent container element ID
   */
  constructor(options = {}) {
    this.matchId = options.matchId;
    this.replayData = options.replayData || null;
    this.containerId = options.containerId || 'visualizerApp';

    this.currentTurn = 0;
    this.totalTurns = 0;
    this.isPlaying = false;
    this.speed = 1; // 1x, 2x, 4x
    this.timer = null;

    this.historyStates = []; // Array of board snapshots at each turn index [0..totalTurns]
    this.moves = [];

    // DOM element references
    this.dom = {
      board: document.getElementById('board'),
      ranks: document.getElementById('ranks'),
      files: document.getElementById('files'),
      slider: document.getElementById('turnSlider'),
      turnLabel: document.getElementById('turnCounter'),
      btnPlayPause: document.getElementById('btnPlayPause'),
      btnPrev: document.getElementById('btnPrev'),
      btnNext: document.getElementById('btnNext'),
      btnFirst: document.getElementById('btnFirst'),
      btnLast: document.getElementById('btnLast'),
      p1Counts: document.getElementById('p1counts'),
      p2Counts: document.getElementById('p2counts'),
      logList: document.getElementById('logList'),
      turnBanner: document.getElementById('turnBanner'),
      winnerBanner: document.getElementById('winnerBanner'),
      winnerTitle: document.getElementById('winnerTitle'),
      winnerDesc: document.getElementById('winnerDesc'),
    };

    this.init();
  }

  /** Initialize board DOM and fetch/load replay data */
  async init() {
    this.buildBoardGrid();
    this.bindControls();

    if (this.replayData) {
      this.loadReplay(this.replayData);
    } else if (this.matchId) {
      await this.fetchReplay(this.matchId);
    }
  }

  /** Build 9x9 grid cells with ranks and files */
  buildBoardGrid() {
    if (!this.dom.board) return;

    this.dom.board.innerHTML = '';
    // Render ranks 9 down to 1 (visual row 0 to 8 corresponds to internal row 8 to 0)
    for (let vr = 0; vr < 9; vr++) {
      const row = 8 - vr;
      for (let col = 0; col < 9; col++) {
        const cell = document.createElement('div');
        cell.className = 'cell ' + ((row + col) % 2 === 0 ? 'dark' : 'light');
        cell.dataset.row = row;
        cell.dataset.col = col;

        const coord = document.createElement('span');
        coord.className = 'coord';
        coord.textContent = getCoordName(row, col);
        cell.appendChild(coord);

        // Highlight goal squares: P2 goal is a1 (row 0, col 0); P1 goal is i9 (row 8, col 8)
        if (row === 0 && col === 0) {
          cell.classList.add('goal-p2');
          cell.dataset.goal = 'P2 GOAL';
        } else if (row === 8 && col === 8) {
          cell.classList.add('goal-p1');
          cell.dataset.goal = 'P1 GOAL';
        }

        this.dom.board.appendChild(cell);
      }
    }

    // Build ranks labels (top=9 to bottom=1)
    if (this.dom.ranks) {
      this.dom.ranks.innerHTML = '';
      for (let vr = 0; vr < 9; vr++) {
        const div = document.createElement('div');
        div.textContent = RANKS[8 - vr];
        this.dom.ranks.appendChild(div);
      }
    }

    // Build files labels (left=a to right=i)
    if (this.dom.files) {
      this.dom.files.innerHTML = '';
      for (let c = 0; c < 9; c++) {
        const div = document.createElement('div');
        div.textContent = FILES[c];
        this.dom.files.appendChild(div);
      }
    }
  }

  /** Bind buttons, scrubber slider, and speed toggle event listeners */
  bindControls() {
    if (this.dom.btnPlayPause) {
      this.dom.btnPlayPause.addEventListener('click', () => this.togglePlay());
    }
    if (this.dom.btnPrev) {
      this.dom.btnPrev.addEventListener('click', () => this.stepBackward());
    }
    if (this.dom.btnNext) {
      this.dom.btnNext.addEventListener('click', () => this.stepForward());
    }
    if (this.dom.btnFirst) {
      this.dom.btnFirst.addEventListener('click', () => this.goToTurn(0));
    }
    if (this.dom.btnLast) {
      this.dom.btnLast.addEventListener('click', () => this.goToTurn(this.totalTurns));
    }

    if (this.dom.slider) {
      this.dom.slider.addEventListener('input', (e) => {
        const turn = parseInt(e.target.value, 10);
        this.goToTurn(turn);
      });
    }

    // Speed toggles
    document.querySelectorAll('.speed-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.speed-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.speed = parseFloat(e.target.dataset.speed || 1);
        if (this.isPlaying) {
          this.pause();
          this.play();
        }
      });
    });

    // Keyboard navigation shortcuts
    window.addEventListener('keydown', (e) => {
      if (['ArrowLeft', 'KeyA'].includes(e.code)) {
        this.stepBackward();
      } else if (['ArrowRight', 'KeyD'].includes(e.code)) {
        this.stepForward();
      } else if (e.code === 'Space') {
        e.preventDefault();
        this.togglePlay();
      }
    });
  }

  /** Fetch replay JSON data from server API */
  async fetchReplay(matchId) {
    try {
      const res = await fetch(`/api/matches/${matchId}/replay`);
      if (!res.ok) {
        throw new Error(`Failed to load replay (HTTP ${res.status})`);
      }
      const data = await res.json();
      this.loadReplay(data);
    } catch (err) {
      console.error('Error fetching replay:', err);
      if (this.dom.turnBanner) {
        this.dom.turnBanner.textContent = `Replay Error: ${err.message}`;
      }
    }
  }

  /** Precompute board snapshots across all turns for fast scrubbing */
  loadReplay(data) {
    this.replayData = data;
    this.moves = data.moves || [];
    this.totalTurns = this.moves.length;

    // Create starting board
    const initialBoard = data.initial_board || this.createDefaultInitialBoard();
    this.historyStates = [cloneBoard(initialBoard)];

    // Apply moves incrementally to construct board state at each turn index
    let currentBoard = cloneBoard(initialBoard);
    for (let i = 0; i < this.moves.length; i++) {
      const m = this.moves[i];
      const nextBoard = cloneBoard(currentBoard);
      const piece = nextBoard[m.from[0]][m.from[1]] || m.piece;
      nextBoard[m.from[0]][m.from[1]] = null;
      nextBoard[m.to[0]][m.to[1]] = piece;

      this.historyStates.push(nextBoard);
      currentBoard = nextBoard;
    }

    if (this.dom.slider) {
      this.dom.slider.max = this.totalTurns;
      this.dom.slider.value = 0;
    }

    this.populateMoveLog();
    this.goToTurn(0);
  }

  /** Generate standard default starting board if initial_board is missing */
  createDefaultInitialBoard() {
    const board = Array.from({ length: 9 }, () => Array(9).fill(null));
    const p1Row = ['R', 'R', 'R', 'P', 'P', 'P', 'S', 'S', 'S'];
    const p2Row = ['S', 'S', 'S', 'P', 'P', 'P', 'R', 'R', 'R'];
    for (let c = 0; c < 9; c++) {
      board[0][c] = { type: p1Row[c], player: 1 };
      board[8][c] = { type: p2Row[c], player: 2 };
    }
    return board;
  }

  /** Render the full move log in the right panel */
  populateMoveLog() {
    if (!this.dom.logList) return;
    this.dom.logList.innerHTML = '';

    this.moves.forEach((m, idx) => {
      const li = document.createElement('li');
      li.className = 'log-item';
      li.dataset.turn = idx + 1;

      const playerColor = m.player === 1 ? 'P1' : 'P2';
      const pBadge = `<span class="tag ${m.player === 1 ? 'red' : 'blue'}">${playerColor}</span>`;
      const moveText = `<span><b>${idx + 1}.</b> ${m.san || `${getCoordName(m.from[0], m.from[1])} -> ${getCoordName(m.to[0], m.to[1])}`}</span>`;

      li.innerHTML = `${moveText} ${pBadge}`;
      li.addEventListener('click', () => {
        this.pause();
        this.goToTurn(idx + 1);
      });

      this.dom.logList.appendChild(li);
    });
  }

  /** Toggle playback state between playing and paused */
  togglePlay() {
    if (this.isPlaying) {
      this.pause();
    } else {
      this.play();
    }
  }

  /** Start automated playback */
  play() {
    if (this.isPlaying) return;
    if (this.currentTurn >= this.totalTurns) {
      this.goToTurn(0);
    }
    this.isPlaying = true;
    if (this.dom.btnPlayPause) {
      this.dom.btnPlayPause.textContent = 'Pause';
    }

    const intervalMs = Math.max(100, Math.floor(800 / this.speed));
    this.timer = setInterval(() => {
      if (this.currentTurn < this.totalTurns) {
        this.stepForward();
      } else {
        this.pause();
      }
    }, intervalMs);
  }

  /** Pause automated playback */
  pause() {
    this.isPlaying = false;
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    if (this.dom.btnPlayPause) {
      this.dom.btnPlayPause.textContent = 'Play';
    }
  }

  /** Advance forward by 1 turn */
  stepForward() {
    if (this.currentTurn < this.totalTurns) {
      this.goToTurn(this.currentTurn + 1);
    }
  }

  /** Step backward by 1 turn */
  stepBackward() {
    if (this.currentTurn > 0) {
      this.goToTurn(this.currentTurn - 1);
    }
  }

  /** Jump directly to a target turn number */
  goToTurn(turn) {
    turn = Math.max(0, Math.min(this.totalTurns, turn));
    this.currentTurn = turn;

    if (this.dom.slider) {
      this.dom.slider.value = turn;
    }
    if (this.dom.turnLabel) {
      this.dom.turnLabel.textContent = `${turn} / ${this.totalTurns}`;
    }

    const boardState = this.historyStates[turn] || this.historyStates[0];
    this.renderBoard(boardState, turn);
    this.updateCounts(boardState);
    this.updateLogHighlight(turn);
    this.updateBanners(turn);
  }

  /** Render pieces and highlight coordinates for the active turn */
  renderBoard(boardState, turn) {
    if (!this.dom.board) return;

    // Last move coordinates
    const lastMove = turn > 0 ? this.moves[turn - 1] : null;

    const cells = this.dom.board.querySelectorAll('.cell');
    cells.forEach(cell => {
      const r = parseInt(cell.dataset.row, 10);
      const c = parseInt(cell.dataset.col, 10);

      // Reset highlight classes
      cell.classList.remove('highlight-from', 'highlight-to');
      if (lastMove) {
        if (lastMove.from[0] === r && lastMove.from[1] === c) {
          cell.classList.add('highlight-from');
        } else if (lastMove.to[0] === r && lastMove.to[1] === c) {
          cell.classList.add('highlight-to');
        }
      }

      // Clear existing piece element
      const existingPiece = cell.querySelector('.piece');
      if (existingPiece) {
        existingPiece.remove();
      }

      // Add piece if present
      const p = boardState[r][c];
      if (p) {
        const pieceEl = document.createElement('div');
        pieceEl.className = `piece p${p.player} t-${p.type}`;
        pieceEl.innerHTML = `<span class="icon">${TYPE_ICONS[p.type] || p.type}</span>`;
        pieceEl.title = `Player ${p.player} - ${TYPE_NAMES[p.type] || p.type} (${getCoordName(r, c)})`;
        cell.appendChild(pieceEl);
      }
    });
  }

  /** Update alive piece counts for Player 1 and Player 2 */
  updateCounts(boardState) {
    const counts = {
      1: { R: 0, P: 0, S: 0 },
      2: { R: 0, P: 0, S: 0 },
    };

    for (let r = 0; r < 9; r++) {
      for (let c = 0; c < 9; c++) {
        const p = boardState[r][c];
        if (p && counts[p.player] && counts[p.player][p.type] !== undefined) {
          counts[p.player][p.type]++;
        }
      }
    }

    this.renderPlayerCounts(1, counts[1], this.dom.p1Counts);
    this.renderPlayerCounts(2, counts[2], this.dom.p2Counts);
  }

  /** Render individual piece count chips */
  renderPlayerCounts(player, pCounts, container) {
    if (!container) return;
    container.innerHTML = '';
    ['R', 'P', 'S'].forEach(t => {
      const n = pCounts[t];
      const div = document.createElement('div');
      div.className = 'cnt' + (n === 0 ? ' dead' : '');
      div.innerHTML = `
        <span class="mini p${player}"><span class="icon">${TYPE_ICONS[t]}</span></span>
        <b>${n}</b>
      `;
      container.appendChild(div);
    });
  }

  /** Highlight the active turn entry in the move log list */
  updateLogHighlight(turn) {
    if (!this.dom.logList) return;
    const items = this.dom.logList.querySelectorAll('.log-item');
    items.forEach(item => {
      const itemTurn = parseInt(item.dataset.turn, 10);
      if (itemTurn === turn) {
        item.classList.add('active');
        item.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      } else {
        item.classList.remove('active');
      }
    });
  }

  /** Update active turn banner and display winner notification when finished */
  updateBanners(turn) {
    if (!this.dom.turnBanner) return;

    this.dom.turnBanner.classList.remove('p1', 'p2');
    const isFinished = turn === this.totalTurns && this.replayData;

    if (isFinished) {
      const winner = this.replayData.winner;
      const reason = this.replayData.win_reason || 'finished';
      const winnerText = winner ? `Player ${winner} won!` : 'Match drawn!';

      this.dom.turnBanner.textContent = `Match Ended — ${winnerText} (${reason})`;
      if (winner) {
        this.dom.turnBanner.classList.add(`p${winner}`);
      }

      if (this.dom.winnerBanner) {
        this.dom.winnerBanner.classList.remove('hidden', 'p1', 'p2');
        if (winner) {
          this.dom.winnerBanner.classList.add(`p${winner}`);
        }
        if (this.dom.winnerTitle) {
          this.dom.winnerTitle.textContent = winner ? `Player ${winner} Victorious!` : 'Draw!';
        }
        if (this.dom.winnerDesc) {
          this.dom.winnerDesc.textContent = `Victory condition: ${reason} in ${this.totalTurns} turns.`;
        }
      }
    } else {
      if (this.dom.winnerBanner) {
        this.dom.winnerBanner.classList.add('hidden');
      }

      const nextPlayer = (turn % 2 === 0) ? 1 : 2;
      this.dom.turnBanner.textContent = `Turn ${turn + 1}: Player ${nextPlayer}'s Move`;
      this.dom.turnBanner.classList.add(`p${nextPlayer}`);
    }
  }
}

// Export to window for global access
window.ReplayVisualizer = ReplayVisualizer;
