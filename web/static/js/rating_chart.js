/**
 * Battlecode Rating History Visualizer
 * Pure Vanilla JavaScript and SVG multi-line chart engine.
 * Zero npm/Node.js dependencies.
 */

(function () {
  'use strict';

  var PALETTE = [
    '#2dd4bf',
    '#38bdf8',
    '#fbbf24',
    '#c084fc',
    '#f43f5e',
    '#a78bfa',
    '#34d399',
    '#f97316',
    '#60a5fa',
    '#e879f9'
  ];

  /**
   * Escape HTML special characters to prevent XSS.
   *
   * @param {string|number} value
   * @returns {string} Escaped string
   */
  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Normalize input data into a consistent array of user trajectories.
   *
   * @param {*} data Input data payload
   * @returns {Array<Object>} Normalized array of user objects
   */
  function normalizeData(data) {
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.users)) return data.users;
    if (data.points && Array.isArray(data.points)) return [data];
    if (data.username || data.id) return [data];
    return [];
  }

  /**
   * Main render function for the Rating Chart.
   *
   * @param {string|HTMLElement} containerId Mount container or element ID
   * @param {Object|Array} data Rating history payload
   * @param {Object} [options] Optional configuration options
   */
  function render(containerId, data, options) {
    options = options || {};

    var container = typeof containerId === 'string'
      ? document.getElementById(containerId)
      : containerId;

    if (!container) {
      console.warn('RatingChart.render: target container not found:', containerId);
      return;
    }

    container.innerHTML = '';

    var users = normalizeData(data);

    // Filter valid users with points array
    var validUsers = users.filter(function (u) {
      return u && Array.isArray(u.points) && u.points.length > 0;
    });

    var maxPoints = validUsers.reduce(function (max, u) {
      return Math.max(max, u.points.length);
    }, 0);

    // Check for insufficient match trajectory data
    if (validUsers.length === 0 || maxPoints < 2) {
      var emptyDiv = document.createElement('div');
      emptyDiv.className = 'chart-empty-state';
      emptyDiv.textContent = 'Chưa có đủ dữ liệu trận đấu để dựng biểu đồ. Hãy thi đấu thêm để biểu đồ xuất hiện!';
      container.appendChild(emptyDiv);
      return;
    }

    // Assign fallback colors from curated palette
    validUsers.forEach(function (user, idx) {
      if (!user.color) {
        user.color = PALETTE[idx % PALETTE.length];
      }
    });

    // Optional header title
    if (options.title) {
      var headerDiv = document.createElement('div');
      headerDiv.className = 'chart-header';
      var titleEl = document.createElement('h3');
      titleEl.className = 'chart-title';
      titleEl.textContent = options.title;
      headerDiv.appendChild(titleEl);
      container.appendChild(headerDiv);
    }

    // Chart dimensions
    var svgWidth = 800;
    var svgHeight = options.height || 360;
    var padding = { top: 30, right: 30, bottom: 42, left: 62 };
    var plotWidth = svgWidth - padding.left - padding.right;
    var plotHeight = svgHeight - padding.top - padding.bottom;

    // Collect all Elo rating values across users
    var allElos = [];
    validUsers.forEach(function (user) {
      user.points.forEach(function (pt) {
        if (typeof pt.elo === 'number' && !isNaN(pt.elo)) {
          allElos.push(pt.elo);
        }
      });
    });

    if (allElos.length === 0) allElos = [1200];
    var minEloRaw = Math.min.apply(null, allElos);
    var maxEloRaw = Math.max.apply(null, allElos);

    // Bounds calculations
    var minElo = Math.floor((minEloRaw - 40) / 50) * 50;
    var maxElo = Math.ceil((maxEloRaw + 40) / 50) * 50;

    // Minimum Y span of at least 200 Elo
    if (maxElo - minElo < 200) {
      var spanDiff = 200 - (maxElo - minElo);
      var padDown = Math.floor(spanDiff / 2 / 50) * 50;
      var padUp = spanDiff - padDown;
      minElo -= padDown;
      maxElo += padUp;
    }

    // Choose grid step
    var eloSpan = maxElo - minElo;
    var step = 50;
    if (eloSpan > 800) {
      step = 200;
    } else if (eloSpan > 300) {
      step = 100;
    }

    minElo = Math.floor(minElo / step) * step;
    maxElo = Math.ceil(maxElo / step) * step;

    function getY(elo) {
      var clamped = Math.max(minElo, Math.min(maxElo, elo));
      return padding.top + plotHeight - ((clamped - minElo) / (maxElo - minElo)) * plotHeight;
    }

    function getX(pointIndex) {
      var denominator = Math.max(1, maxPoints - 1);
      return padding.left + (pointIndex / denominator) * plotWidth;
    }

    // Build SVG components
    var svgParts = [];
    svgParts.push('<svg class="chart-svg" viewBox="0 0 ' + svgWidth + ' ' + svgHeight + '" preserveAspectRatio="xMidYMid meet">');

    // Horizontal grid lines and Y-axis text labels
    for (var eloVal = minElo; eloVal <= maxElo; eloVal += step) {
      var gridY = getY(eloVal).toFixed(1);
      svgParts.push(
        '<line class="chart-grid-line" x1="' + padding.left + '" y1="' + gridY +
        '" x2="' + (svgWidth - padding.right) + '" y2="' + gridY + '" />'
      );
      svgParts.push(
        '<text class="chart-axis-text" x="' + (padding.left - 10) + '" y="' + (parseFloat(gridY) + 4).toFixed(1) +
        '" text-anchor="end">' + eloVal + '</text>'
      );
    }

    // Bottom axis baseline
    var baseY = (padding.top + plotHeight).toFixed(1);
    svgParts.push(
      '<line class="chart-grid-line" x1="' + padding.left + '" y1="' + baseY +
      '" x2="' + (svgWidth - padding.right) + '" y2="' + baseY + '" stroke="#30363d" />'
    );

    // X-axis ticks and labels
    var xTicksCount = Math.min(maxPoints, 8);
    var xStep = Math.max(1, Math.floor((maxPoints - 1) / (xTicksCount - 1)));
    for (var ti = 0; ti < maxPoints; ti += xStep) {
      var tickX = getX(ti).toFixed(1);
      var labelText = ti === 0 ? 'Khởi đầu' : ('#' + ti);
      svgParts.push(
        '<text class="chart-axis-text" x="' + tickX + '" y="' + (parseFloat(baseY) + 18).toFixed(1) +
        '" text-anchor="middle">' + labelText + '</text>'
      );
    }
    // Ensure final point label is shown if not already included
    if ((maxPoints - 1) % xStep !== 0) {
      var lastTickX = getX(maxPoints - 1).toFixed(1);
      svgParts.push(
        '<text class="chart-axis-text" x="' + lastTickX + '" y="' + (parseFloat(baseY) + 18).toFixed(1) +
        '" text-anchor="middle">#' + (maxPoints - 1) + '</text>'
      );
    }

    // Trajectory paths
    validUsers.forEach(function (user) {
      var pathD = '';
      user.points.forEach(function (pt, pIdx) {
        var px = getX(pIdx).toFixed(1);
        var py = getY(pt.elo).toFixed(1);
        if (pIdx === 0) {
          pathD += 'M ' + px + ' ' + py;
        } else {
          pathD += ' L ' + px + ' ' + py;
        }
      });

      svgParts.push(
        '<path class="chart-line" d="' + pathD + '" stroke="' + user.color +
        '" data-user-id="' + escapeHtml(user.id) + '" />'
      );
    });

    // Trajectory interactive point circles
    validUsers.forEach(function (user) {
      user.points.forEach(function (pt, pIdx) {
        var px = getX(pIdx).toFixed(1);
        var py = getY(pt.elo).toFixed(1);
        var matchId = pt.match_id !== undefined && pt.match_id !== null ? pt.match_id : '';
        var delta = pt.delta !== undefined && pt.delta !== null ? pt.delta : 0;
        var opponent = pt.opponent || '';

        svgParts.push(
          '<circle class="chart-point" cx="' + px + '" cy="' + py + '" r="3.5"' +
          ' fill="' + user.color + '" stroke="#0d1117" stroke-width="2"' +
          ' data-user-id="' + escapeHtml(user.id) + '"' +
          ' data-username="' + escapeHtml(user.username || 'Người chơi') + '"' +
          ' data-match-id="' + escapeHtml(matchId) + '"' +
          ' data-elo="' + escapeHtml(pt.elo) + '"' +
          ' data-delta="' + escapeHtml(delta) + '"' +
          ' data-opponent="' + escapeHtml(opponent) + '" />'
        );
      });
    });

    svgParts.push('</svg>');

    // Create DOM wrapper
    var wrapper = document.createElement('div');
    wrapper.className = 'chart-wrapper';
    wrapper.innerHTML = svgParts.join('');

    var tooltip = document.createElement('div');
    tooltip.className = 'chart-tooltip';
    tooltip.style.display = 'none';
    tooltip.style.opacity = '0';
    wrapper.appendChild(tooltip);

    container.appendChild(wrapper);

    // Build Legend
    var showLegend = options.showLegend !== false;
    var legendContainer = null;
    if (showLegend && validUsers.length > 0) {
      legendContainer = document.createElement('div');
      legendContainer.className = 'chart-legend';

      validUsers.forEach(function (user) {
        var item = document.createElement('div');
        item.className = 'legend-item';
        item.setAttribute('data-user-id', String(user.id));

        var colorDot = document.createElement('span');
        colorDot.className = 'legend-color';
        colorDot.style.backgroundColor = user.color;
        item.appendChild(colorDot);

        var label = document.createElement('span');
        label.className = 'legend-label';
        label.textContent = user.username || ('User #' + user.id);
        item.appendChild(label);

        legendContainer.appendChild(item);
      });

      container.appendChild(legendContainer);
    }

    // Interactivity: Highlighting user lines and points
    var selectedUserId = null;

    function applyHighlight(userId) {
      var allLines = wrapper.querySelectorAll('.chart-line');
      var allPoints = wrapper.querySelectorAll('.chart-point');
      var allLegendItems = legendContainer ? legendContainer.querySelectorAll('.legend-item') : [];

      if (!userId) {
        allLines.forEach(function (line) {
          line.style.opacity = '1';
          line.style.strokeWidth = '';
        });
        allPoints.forEach(function (point) {
          point.style.opacity = '1';
        });
        allLegendItems.forEach(function (item) {
          item.classList.remove('active', 'dimmed');
          item.style.opacity = '1';
        });
        return;
      }

      var targetIdStr = String(userId);

      allLines.forEach(function (line) {
        if (line.getAttribute('data-user-id') === targetIdStr) {
          line.style.opacity = '1';
          line.style.strokeWidth = '3px';
        } else {
          line.style.opacity = '0.15';
          line.style.strokeWidth = '1.5px';
        }
      });

      allPoints.forEach(function (point) {
        if (point.getAttribute('data-user-id') === targetIdStr) {
          point.style.opacity = '1';
        } else {
          point.style.opacity = '0.15';
        }
      });

      allLegendItems.forEach(function (item) {
        if (item.getAttribute('data-user-id') === targetIdStr) {
          item.classList.add('active');
          item.classList.remove('dimmed');
          item.style.opacity = '1';
        } else {
          item.classList.remove('active');
          item.classList.add('dimmed');
          item.style.opacity = '0.4';
        }
      });
    }

    // Legend Event Listeners
    if (legendContainer) {
      legendContainer.addEventListener('mouseover', function (e) {
        var item = e.target.closest('.legend-item');
        if (!item) return;
        var userId = item.getAttribute('data-user-id');
        applyHighlight(userId);
      });

      legendContainer.addEventListener('mouseout', function (e) {
        var item = e.target.closest('.legend-item');
        if (!item) return;
        if (selectedUserId) {
          applyHighlight(selectedUserId);
        } else {
          applyHighlight(null);
        }
      });

      legendContainer.addEventListener('click', function (e) {
        var item = e.target.closest('.legend-item');
        if (!item) return;
        var userId = item.getAttribute('data-user-id');
        if (selectedUserId === userId) {
          selectedUserId = null;
          applyHighlight(null);
        } else {
          selectedUserId = userId;
          applyHighlight(userId);
        }
      });
    }

    // Line Mouse Hover
    wrapper.addEventListener('mouseover', function (e) {
      var line = e.target.closest('.chart-line');
      if (line && !selectedUserId) {
        var userId = line.getAttribute('data-user-id');
        applyHighlight(userId);
      }
    });

    wrapper.addEventListener('mouseout', function (e) {
      var line = e.target.closest('.chart-line');
      if (line && !selectedUserId) {
        applyHighlight(null);
      }
    });

    // Tooltip Interaction
    wrapper.addEventListener('mouseover', function (e) {
      var pointEl = e.target.closest('.chart-point');
      if (!pointEl) return;

      var username = pointEl.getAttribute('data-username') || 'Người chơi';
      var matchId = pointEl.getAttribute('data-match-id');
      var elo = pointEl.getAttribute('data-elo');
      var rawDelta = pointEl.getAttribute('data-delta');
      var opponent = pointEl.getAttribute('data-opponent');

      var deltaNum = parseInt(rawDelta, 10);
      var deltaStr = isNaN(deltaNum) ? '+0' : (deltaNum > 0 ? '+' + deltaNum : String(deltaNum));

      var matchPart = matchId ? ('Trận #' + matchId) : 'Khởi đầu';
      var oppPart = opponent ? ('Đối thủ: ' + opponent) : 'Đối thủ: Start';

      // Tooltip content: [Username] • Trận #[match_id] • Elo: [elo] ([+delta]) • Đối thủ: [opponent]
      tooltip.innerHTML =
        '<strong>' + escapeHtml(username) + '</strong> &bull; ' +
        escapeHtml(matchPart) + ' &bull; Elo: <strong>' +
        escapeHtml(elo) + '</strong> (' + escapeHtml(deltaStr) + ') &bull; ' +
        escapeHtml(oppPart);

      tooltip.style.display = 'block';
      tooltip.style.opacity = '1';

      var pointRect = pointEl.getBoundingClientRect();
      var wrapperRect = wrapper.getBoundingClientRect();
      var left = pointRect.left - wrapperRect.left + pointRect.width / 2;
      var top = pointRect.top - wrapperRect.top;

      var tipWidth = tooltip.offsetWidth;
      var tipHeight = tooltip.offsetHeight;
      var tipLeft = left - tipWidth / 2;

      if (tipLeft < 8) tipLeft = 8;
      if (tipLeft + tipWidth > wrapperRect.width - 8) {
        tipLeft = wrapperRect.width - tipWidth - 8;
      }

      var tipTop = top - tipHeight - 10;
      if (tipTop < 0) {
        tipTop = top + pointRect.height + 10;
      }

      tooltip.style.left = tipLeft + 'px';
      tooltip.style.top = tipTop + 'px';
    });

    wrapper.addEventListener('mouseout', function (e) {
      var pointEl = e.target.closest('.chart-point');
      if (pointEl) {
        tooltip.style.opacity = '0';
        tooltip.style.display = 'none';
      }
    });
  }

  // Global namespace export
  window.RatingChart = {
    render: render,
    PALETTE: PALETTE
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.RatingChart;
  }
})();
