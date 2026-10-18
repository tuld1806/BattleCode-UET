/**
 * BattleCode-UET: Playoff Bracket Administration & Score Export Module
 *
 * Professional Vanilla JS controller for:
 * 1. Password-Protected Bracket Generation Modal
 * 2. Automated BO3 Round-by-Round and Run-All Playoff Execution
 * 3. UTF-8-SIG Excel-Compatible CSV Score Export
 * 4. Micro-Interaction Toast Notifications & Modal Focus Trapping
 */

(function () {
  'use strict';

  // State tracker for active tournament ID (if running in multi-game view)
  let activeTournamentId = null;

  /* =========================================================================
   * 1. TOAST NOTIFICATION ENGINE (Sleek Glassmorphic Micro-Interactions)
   * ========================================================================= */

  function getOrCreateToastContainer() {
    let container = document.getElementById('admin-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'admin-toast-container';
      container.className = 'admin-toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  /**
   * Display a smooth floating toast notification.
   * @param {string} message - Notification text
   * @param {'info'|'success'|'error'|'warning'} [type='info'] - Visual sentiment
   * @param {number} [duration=3500] - Lifespan in ms
   */
  function showToast(message, type = 'info', duration = 3500) {
    const container = getOrCreateToastContainer();
    const toast = document.createElement('div');
    toast.className = `admin-toast admin-toast-${type}`;

    const iconMap = {
      success: '✓',
      error: '✕',
      warning: '⚠',
      info: 'ℹ'
    };

    toast.innerHTML = `
      <div class="toast-icon">${iconMap[type] || '•'}</div>
      <div class="toast-content">${message}</div>
      <button type="button" class="toast-close" aria-label="Close">&times;</button>
      <div class="toast-progress"></div>
    `;

    // Click close
    toast.querySelector('.toast-close').addEventListener('click', () => {
      dismissToast(toast);
    });

    container.appendChild(toast);

    // Entrance animation
    requestAnimationFrame(() => {
      toast.classList.add('toast-visible');
    });

    // Auto dismiss timer
    const timer = setTimeout(() => {
      dismissToast(toast);
    }, duration);

    toast.addEventListener('mouseenter', () => clearTimeout(timer));
  }

  function dismissToast(toast) {
    toast.classList.remove('toast-visible');
    toast.classList.add('toast-hiding');
    toast.addEventListener('transitionend', () => {
      if (toast.parentElement) toast.parentElement.removeChild(toast);
    });
  }

  /* =========================================================================
   * 2. MODAL CONTROLS & FOCUS TRAPPING
   * ========================================================================= */

  /**
   * Open the password confirmation modal before bracket generation.
   * @param {number|null} [tourneyId=null] - Optional tournament ID in multi-game mode
   */
  function openBracketPasswordModal(tourneyId = null) {
    activeTournamentId = tourneyId;
    const modal = document.getElementById('bracketPasswordModal');
    const passwordInput = document.getElementById('adminBracketPassword');
    const errorEl = document.getElementById('bracketPasswordError');

    if (!modal) {
      console.warn('bracketPasswordModal element not found in DOM.');
      return;
    }

    if (errorEl) {
      errorEl.style.display = 'none';
      errorEl.textContent = '';
    }

    if (passwordInput) {
      passwordInput.value = '';
      passwordInput.classList.remove('input-error-shake');
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Smooth entrance
    requestAnimationFrame(() => {
      modal.classList.add('modal-active');
      if (passwordInput) passwordInput.focus();
    });
  }

  /**
   * Close the password confirmation modal and clear inputs.
   */
  function closeBracketPasswordModal() {
    const modal = document.getElementById('bracketPasswordModal');
    const passwordInput = document.getElementById('adminBracketPassword');
    const errorEl = document.getElementById('bracketPasswordError');

    if (!modal) return;

    modal.classList.remove('modal-active');
    document.body.style.overflow = '';

    setTimeout(() => {
      modal.style.display = 'none';
      if (passwordInput) passwordInput.value = '';
      if (errorEl) errorEl.style.display = 'none';
    }, 200);
  }

  /**
   * Toggle password visibility between text and password.
   */
  function toggleBracketPasswordVisibility() {
    const input = document.getElementById('adminBracketPassword');
    const toggleBtn = document.getElementById('btnTogglePasswordView');
    if (!input) return;

    if (input.type === 'password') {
      input.type = 'text';
      if (toggleBtn) toggleBtn.textContent = '🔒';
    } else {
      input.type = 'password';
      if (toggleBtn) toggleBtn.textContent = '👁';
    }
  }

  /* =========================================================================
   * 3. API DISPATCHERS (Bracket Generation, BO3 Match Execution, Score Export)
   * ========================================================================= */

  /**
   * Submit bracket generation request with admin password verification.
   * @param {number|null} [tourneyId=null] - Tournament ID
   */
  async function submitBracketGeneration(tourneyId = null) {
    const targetTourneyId = tourneyId !== null ? tourneyId : activeTournamentId;
    const passwordInput = document.getElementById('adminBracketPassword');
    const errorEl = document.getElementById('bracketPasswordError');
    const submitBtn = document.getElementById('btnConfirmGenerateBracket');

    if (!passwordInput) return;
    const password = passwordInput.value.trim();

    if (!password) {
      if (errorEl) {
        errorEl.textContent = 'Vui lòng nhập mật khẩu quản trị viên để xác nhận.';
        errorEl.style.display = 'block';
      }
      passwordInput.classList.add('input-error-shake');
      setTimeout(() => passwordInput.classList.remove('input-error-shake'), 450);
      passwordInput.focus();
      return;
    }

    if (errorEl) errorEl.style.display = 'none';

    // UI Busy State
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.dataset.originalHtml = submitBtn.innerHTML;
      submitBtn.innerHTML = '<span class="admin-btn-spinner"></span> Đang xác thực...';
    }

    const endpoint = targetTourneyId
      ? `/api/admin/tournaments/${targetTourneyId}/start-bracket`
      : '/api/admin/bracket/generate';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_password: password })
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const errorMsg = data.detail || 'Mật khẩu quản trị viên không chính xác!';
        if (errorEl) {
          errorEl.textContent = errorMsg;
          errorEl.style.display = 'block';
        }
        passwordInput.classList.add('input-error-shake');
        setTimeout(() => passwordInput.classList.remove('input-error-shake'), 450);
        passwordInput.select();
        showToast(errorMsg, 'error');
        return;
      }

      // Success
      closeBracketPasswordModal();
      const count = Array.isArray(data) ? data.length : (data.matchups ? data.matchups.length : 'Top');
      showToast(`Đã tạo nhánh đấu thành công với ${count} cặp đấu! Đang làm mới...`, 'success', 2500);

      setTimeout(() => {
        window.location.reload();
      }, 1000);

    } catch (err) {
      if (errorEl) {
        errorEl.textContent = `Lỗi mạng: ${err.message}`;
        errorEl.style.display = 'block';
      }
      showToast(`Lỗi mạng: ${err.message}`, 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        if (submitBtn.dataset.originalHtml) {
          submitBtn.innerHTML = submitBtn.dataset.originalHtml;
        }
      }
    }
  }

  /**
   * Execute current round matches via BO3 automated runner.
   * @param {number|null} [tourneyId=null] - Tournament ID
   */
  async function runBracketRound(tourneyId = null) {
    const targetTourneyId = tourneyId !== null ? tourneyId : activeTournamentId;
    const btn = document.getElementById('btnRunRound');
    const btnAll = document.getElementById('btnRunAll');

    if (btn) {
      btn.disabled = true;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="admin-btn-spinner"></span> Đang thi đấu...';
    }
    if (btnAll) btnAll.disabled = true;

    showToast('Đang tiến hành các trận đấu vòng hiện tại (Best-of-3)...', 'info', 3000);

    const endpoint = targetTourneyId
      ? `/api/admin/tournaments/${targetTourneyId}/bracket/run-round`
      : '/api/admin/bracket/run-round';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const errorMsg = data.detail || 'Không thể chạy vòng đấu hiện tại.';
        showToast(errorMsg, 'error', 4500);
        return;
      }

      const matchesRan = data.matches_executed || (data.results ? data.results.length : 0);
      showToast(data.message || `Đã hoàn thành ${matchesRan} trận đấu vòng hiện tại! Đang tải lại...`, 'success', 3000);

      setTimeout(() => {
        window.location.reload();
      }, 1200);

    } catch (err) {
      showToast(`Lỗi khi chạy vòng đấu: ${err.message}`, 'error', 4500);
    } finally {
      if (btn) {
        btn.disabled = false;
        if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      }
      if (btnAll) btnAll.disabled = false;
    }
  }

  /**
   * Sequentially execute all rounds until Finals conclude and champion is crowned.
   * @param {number|null} [tourneyId=null] - Tournament ID
   */
  async function runAllBracketRounds(tourneyId = null) {
    const targetTourneyId = tourneyId !== null ? tourneyId : activeTournamentId;
    const btn = document.getElementById('btnRunAll');
    const btnRound = document.getElementById('btnRunRound');

    if (!confirm('Hệ thống sẽ chạy liên tục tất cả các trận đấu BO3 từ vòng này đến trận Chung kết. Bạn có chắc chắn muốn chạy tự động toàn bộ?')) {
      return;
    }

    if (btn) {
      btn.disabled = true;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="admin-btn-spinner"></span> Đang chạy toàn bộ...';
    }
    if (btnRound) btnRound.disabled = true;

    showToast('Đang mô phỏng toàn bộ các vòng đấu Playoff đến trận Chung kết...', 'info', 5000);

    const endpoint = targetTourneyId
      ? `/api/admin/tournaments/${targetTourneyId}/bracket/run-all`
      : '/api/admin/bracket/run-all';

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const errorMsg = data.detail || 'Không thể chạy tự động toàn bộ giải đấu.';
        showToast(errorMsg, 'error', 4500);
        return;
      }

      const champ = data.champion ? ` Quán quân: ${data.champion}!` : '';
      showToast(data.message || `Giải đấu đã kết thúc thành công!${champ} Đang tải lại...`, 'success', 3500);

      setTimeout(() => {
        window.location.reload();
      }, 1500);

    } catch (err) {
      showToast(`Lỗi khi chạy toàn bộ giải đấu: ${err.message}`, 'error', 4500);
    } finally {
      if (btn) {
        btn.disabled = false;
        if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      }
      if (btnRound) btnRound.disabled = false;
    }
  }

  /**
   * Download Excel-compatible CSV file (UTF-8-SIG with BOM \ufeff).
   * @param {number|null} [tourneyId=null] - Tournament ID
   */
  async function exportBracketScoresCsv(tourneyId = null) {
    const targetTourneyId = tourneyId !== null ? tourneyId : activeTournamentId;
    const btns = document.querySelectorAll('.btn-export-csv');

    btns.forEach(btn => {
      btn.disabled = true;
      btn.dataset.originalHtml = btn.innerHTML;
      btn.innerHTML = '<span class="admin-btn-spinner"></span> Đang xuất...';
    });

    const endpoint = targetTourneyId
      ? `/api/admin/tournaments/${targetTourneyId}/export-scores`
      : '/api/admin/bracket/export-scores';

    try {
      const res = await fetch(endpoint, { method: 'GET' });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const msg = errData.detail || 'Không thể xuất bảng điểm (Giải đấu có thể chưa khởi tạo hoặc chưa có kết quả).';
        showToast(msg, 'warning', 4500);
        return;
      }

      // Extract filename from Content-Disposition header if available
      let filename = 'battlecode_final_scores.csv';
      const disposition = res.headers.get('Content-Disposition');
      if (disposition && disposition.includes('filename=')) {
        const matches = disposition.match(/filename="?([^"]+)"?/);
        if (matches && matches[1]) {
          filename = matches[1];
        }
      }

      // Stream Blob with preserved UTF-8 BOM
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      showToast(`Tải file "${filename}" thành công! Mở tốt trên Excel & Google Sheets.`, 'success', 3500);

    } catch (err) {
      showToast(`Lỗi khi tải bảng điểm CSV: ${err.message}`, 'error', 4500);
    } finally {
      btns.forEach(btn => {
        btn.disabled = false;
        if (btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      });
    }
  }

  /* =========================================================================
   * 4. GLOBAL BINDINGS & KEYBOARD LISTENERS
   * ========================================================================= */

  // Global ESC key listener to dismiss active modal
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const modal = document.getElementById('bracketPasswordModal');
      if (modal && modal.style.display !== 'none') {
        closeBracketPasswordModal();
      }
    }
  });

  // Backdrop click listener
  document.addEventListener('click', (e) => {
    const modal = document.getElementById('bracketPasswordModal');
    if (modal && e.target === modal) {
      closeBracketPasswordModal();
    }
  });

  // Export functions to global window namespace for Jinja template inline handlers
  window.openBracketPasswordModal = openBracketPasswordModal;
  window.closeBracketPasswordModal = closeBracketPasswordModal;
  window.toggleBracketPasswordVisibility = toggleBracketPasswordVisibility;
  window.submitBracketGeneration = submitBracketGeneration;
  window.runBracketRound = runBracketRound;
  window.runAllBracketRounds = runAllBracketRounds;
  window.exportBracketScoresCsv = exportBracketScoresCsv;
  window.showAdminToast = showToast;

})();
