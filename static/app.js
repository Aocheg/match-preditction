(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var state = { snapshot: null, adminToken: '', query: '' };

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function formatNaira(amount) {
    return '₦' + Number(amount).toLocaleString('en-NG');
  }

  function formatTime(iso) {
    if (!iso) return '';
    return iso.replace('T', ' ').replace('+00:00', ' UTC').replace('Z', ' UTC');
  }

  async function api(url, options) {
    var opts = options || {};
    var headers = Object.assign({}, opts.headers || {});
    if (opts.body && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
    if (state.adminToken) {
      headers['X-Admin-Token'] = state.adminToken;
    }
    var res = await fetch(url, Object.assign({}, opts, { headers: headers }));
    var data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || 'Request failed.');
    }
    return data;
  }

  function setFeedback(box, message, isError) {
    if (!message) {
      box.hidden = true;
      box.textContent = '';
      box.classList.remove('feedback-error');
      return;
    }
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle('feedback-error', !!isError);
  }

  function renderMatch(match) {
    $('kickoff-label').textContent = match.kickoff_label || 'Matchday Prediction';
    var badge = $('status-badge');
    badge.className = 'status-pill';
    if (match.status === 'open') {
      badge.classList.add('status-open');
      badge.textContent = 'Predictions Open';
    } else if (match.status === 'locked') {
      badge.classList.add('status-locked');
      badge.textContent = 'Predictions Locked';
    } else {
      badge.classList.add('status-finished');
      badge.textContent = 'Final Result';
    }

    if (match.status === 'finished' && match.final_home_score !== null && match.final_away_score !== null) {
      $('score-display').textContent = match.final_home_score + ' - ' + match.final_away_score;
      $('score-caption').textContent = 'Official Full-Time Score';
    } else {
      $('score-display').textContent = 'VS';
      $('score-caption').textContent = match.status === 'open' ? 'Predict the full-time score' : 'Entry window closed';
    }

    var form = $('prediction-form');
    var closed = match.status !== 'open';
    Array.prototype.forEach.call(form.querySelectorAll('input, button'), function (ctrl) {
      ctrl.disabled = closed;
    });
    if (closed) {
      setFeedback(
        $('form-feedback'),
        match.status === 'locked'
          ? 'Predictions are locked for this match.'
          : 'This match has finished. See the official winners above.',
        false
      );
    } else {
      var fb = $('form-feedback');
      if (fb.textContent.indexOf('locked') !== -1 || fb.textContent.indexOf('finished') !== -1) {
        setFeedback(fb, '', false);
      }
    }
  }

  function renderWinners(snapshot) {
    var sec = $('winners-section');
    var match = snapshot.match;
    if (match.status !== 'finished') {
      sec.hidden = true;
      return;
    }
    sec.hidden = false;
    var list = $('winners-list');
    list.textContent = '';

    var winners = snapshot.winners || [];
    if (!winners.length) {
      $('winners-sub').textContent = 'Final score ' + match.final_home_score + ' - ' + match.final_away_score + '. No predictor matched the exact score.';
      list.appendChild(el('p', 'muted', 'No winners for this round.'));
      return;
    }

    var suffix = ['1st Place', '2nd Place', '3rd Place'];
    $('winners-sub').textContent = 'Final score ' + match.final_home_score + ' - ' + match.final_away_score + ' — ' + snapshot.stats.exact_matches + ' exact prediction(s) found.';
    winners.forEach(function (w) {
      var tile = el('div', 'winner-tile rank-' + w.rank);
      tile.appendChild(el('div', 'winner-rank', suffix[w.rank - 1] + ' • Entry #' + w.order));
      tile.appendChild(el('div', 'winner-name', w.name));
      tile.appendChild(el('div', 'muted', w.contact_masked + ' • Predicted ' + w.home_score + ' - ' + w.away_score));
      tile.appendChild(el('div', 'winner-prize', formatNaira(w.prize)));
      list.appendChild(tile);
    });
  }

  function renderStats(stats) {
    var total = stats.total || 0;
    $('stats-total').textContent = total + (total === 1 ? ' prediction submitted' : ' predictions submitted');

    var hp = total ? Math.round((stats.home_picks / total) * 100) : 0;
    var dp = total ? Math.round((stats.draw_picks / total) * 100) : 0;
    var ap = total ? Math.max(0, 100 - hp - dp) : 0;

    $('pct-home').textContent = 'Legendary FC: ' + hp + '%';
    $('pct-draw').textContent = 'Draw: ' + dp + '%';
    $('pct-away').textContent = 'Learn2Earn FC: ' + ap + '%';

    if (total === 0) {
      $('bar-home').style.width = '33.3%';
      $('bar-draw').style.width = '33.3%';
      $('bar-away').style.width = '33.4%';
    } else {
      $('bar-home').style.width = hp + '%';
      $('bar-draw').style.width = dp + '%';
      $('bar-away').style.width = ap + '%';
    }

    var chips = $('top-scores');
    chips.textContent = '';
    if (!stats.top_scores || !stats.top_scores.length) {
      chips.appendChild(el('li', 'muted', 'No predictions yet.'));
      return;
    }
    stats.top_scores.forEach(function (item) {
      chips.appendChild(el('li', 'score-chip', item.score + ' (' + item.count + ')'));
    });
  }

  function statusBadge(p) {
    if (p.outcome === 'winner') {
      return el('span', 'badge badge-winner', '#' + p.rank + ' Winner (' + formatNaira(p.prize) + ')');
    }
    if (p.outcome === 'exact_late') {
      return el('span', 'badge badge-late', 'Exact Score (After Top 3)');
    }
    if (p.outcome === 'missed') {
      return el('span', 'badge badge-missed', 'Missed');
    }
    return el('span', 'badge badge-pending', 'Pending');
  }

  function renderTable(predictions) {
    var tbody = $('predictions-body');
    tbody.textContent = '';
    var q = state.query.toLowerCase().trim();
    var rows = predictions.filter(function (p) {
      if (!q) return true;
      var score = p.home_score + '-' + p.away_score;
      return p.name.toLowerCase().indexOf(q) !== -1 || score.indexOf(q) !== -1 || String(p.order) === q;
    });

    if (!rows.length) {
      var tr = el('tr');
      var td = el('td', 'empty-cell', predictions.length ? 'No matching predictions.' : 'Be the first to submit a prediction!');
      td.colSpan = 6;
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }

    rows.forEach(function (p) {
      var tr = el('tr');
      tr.appendChild(el('td', null, '#' + p.order));
      tr.appendChild(el('td', null, p.name));
      tr.appendChild(el('td', null, p.contact_masked));
      tr.appendChild(el('td', null, p.home_score + ' - ' + p.away_score));
      tr.appendChild(el('td', null, formatTime(p.created_at)));
      var statusTd = el('td');
      statusTd.appendChild(statusBadge(p));
      tr.appendChild(statusTd);
      tbody.appendChild(tr);
    });
  }

  function renderAdmin(snapshot) {
    if (!state.adminToken) return;
    $('admin-kickoff').value = snapshot.match.kickoff_label || '';
    $('admin-status').value = snapshot.match.status;
    $('final-score-fields').hidden = snapshot.match.status !== 'finished';
    if (snapshot.match.final_home_score !== null) $('final-home').value = snapshot.match.final_home_score;
    if (snapshot.match.final_away_score !== null) $('final-away').value = snapshot.match.final_away_score;

    var tbody = $('admin-table-body');
    tbody.textContent = '';
    if (!snapshot.predictions.length) {
      var emptyTr = el('tr');
      var emptyTd = el('td', 'empty-cell', 'No predictions submitted yet.');
      emptyTd.colSpan = 5;
      emptyTr.appendChild(emptyTd);
      tbody.appendChild(emptyTr);
      return;
    }
    snapshot.predictions.forEach(function (p) {
      var tr = el('tr');
      tr.appendChild(el('td', null, '#' + p.order));
      tr.appendChild(el('td', null, p.name));
      tr.appendChild(el('td', null, p.contact || p.contact_masked));
      tr.appendChild(el('td', null, p.home_score + ' - ' + p.away_score));
      var resTd = el('td');
      resTd.appendChild(statusBadge(p));
      tr.appendChild(resTd);
      tbody.appendChild(tr);
    });
  }

  function renderAll(snapshot) {
    state.snapshot = snapshot;
    renderMatch(snapshot.match);
    renderWinners(snapshot);
    renderStats(snapshot.stats);
    renderTable(snapshot.predictions);
    renderAdmin(snapshot);
  }

  async function refreshState() {
    try {
      var data = await api('/api/state');
      renderAll(data);
    } catch (err) {
      setFeedback($('form-feedback'), err.message, true);
    }
  }

  Array.prototype.forEach.call(document.querySelectorAll('.step-btn'), function (btn) {
    btn.addEventListener('click', function () {
      var input = $(btn.getAttribute('data-target'));
      var delta = parseInt(btn.getAttribute('data-delta'), 10);
      var cur = parseInt(input.value || '0', 10);
      if (isNaN(cur)) cur = 0;
      input.value = Math.max(0, Math.min(50, cur + delta));
    });
  });

  $('prediction-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var feedback = $('form-feedback');
    setFeedback(feedback, '', false);

    var btn = $('submit-btn');
    btn.disabled = true;
    try {
      var payload = {
        name: $('pred-name').value,
        contact: $('pred-contact').value,
        home_score: parseInt($('home-score').value, 10),
        away_score: parseInt($('away-score').value, 10)
      };
      var res = await api('/api/predictions', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      renderAll(res.snapshot);
      var p = res.prediction;
      $('ticket-box').hidden = false;
      $('ticket-summary').textContent = 'Entry #' + p.order + ': ' + p.name + ' picked Legendary FC ' + p.home_score + ' - ' + p.away_score + ' Learn2Earn FC';
      $('ticket-meta').textContent = 'Contact: ' + p.contact_masked + ' • Recorded at ' + formatTime(p.created_at);
      $('prediction-form').reset();
      $('home-score').value = '0';
      $('away-score').value = '0';
      setFeedback(feedback, 'Prediction submitted! Good luck.', false);
    } catch (err) {
      setFeedback(feedback, err.message, true);
    } finally {
      btn.disabled = state.snapshot && state.snapshot.match.status !== 'open';
    }
  });

  $('search-input').addEventListener('input', function (e) {
    state.query = e.target.value;
    if (state.snapshot) renderTable(state.snapshot.predictions);
  });

  /* Admin modal */
  var dlg = $('admin-dialog');
  function openAdmin() {
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
  }
  function closeAdmin() {
    if (typeof dlg.close === 'function' && dlg.open) dlg.close();
    else dlg.removeAttribute('open');
  }

  $('open-admin-btn').addEventListener('click', openAdmin);
  $('footer-admin-btn').addEventListener('click', openAdmin);
  $('close-admin-btn').addEventListener('click', closeAdmin);

  $('admin-status').addEventListener('change', function (e) {
    $('final-score-fields').hidden = e.target.value !== 'finished';
  });

  $('admin-login-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var errBox = $('admin-login-error');
    setFeedback(errBox, '', false);
    try {
      var res = await api('/api/admin/login', {
        method: 'POST',
        body: JSON.stringify({ pin: $('admin-pin').value })
      });
      state.adminToken = res.token;
      $('admin-login-view').hidden = true;
      $('admin-controls-view').hidden = false;
      $('admin-pin').value = '';
      renderAll(res.snapshot);
    } catch (err) {
      setFeedback(errBox, err.message, true);
    }
  });

  $('admin-match-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var fb = $('admin-feedback');
    setFeedback(fb, '', false);
    try {
      var status = $('admin-status').value;
      var payload = {
        kickoff_label: $('admin-kickoff').value,
        status: status
      };
      if (status === 'finished') {
        payload.final_home_score = parseInt($('final-home').value, 10);
        payload.final_away_score = parseInt($('final-away').value, 10);
      }
      var res = await api('/api/admin/match', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      renderAll(res.snapshot);
      setFeedback(fb, 'Match settings saved.', false);
    } catch (err) {
      setFeedback(fb, err.message, true);
    }
  });

  $('reset-match-btn').addEventListener('click', async function () {
    if (!window.confirm('Delete all predictions and reopen the match?')) return;
    var fb = $('admin-feedback');
    try {
      var res = await api('/api/admin/reset', { method: 'POST', body: '{}' });
      $('ticket-box').hidden = true;
      renderAll(res.snapshot);
      setFeedback(fb, 'All predictions cleared and match reopened.', false);
    } catch (err) {
      setFeedback(fb, err.message, true);
    }
  });

  $('export-csv-btn').addEventListener('click', function () {
    if (!state.snapshot) return;
    var lines = [['Order', 'Name', 'Contact', 'Legendary FC', 'Learn2Earn FC', 'Created At', 'Outcome', 'Prize']];
    state.snapshot.predictions.forEach(function (p) {
      lines.push([p.order, p.name, p.contact || p.contact_masked, p.home_score, p.away_score, p.created_at, p.outcome, p.prize]);
    });
    var csv = lines.map(function (row) {
      return row.map(function (cell) {
        return '"' + String(cell).replace(/"/g, '""') + '"';
      }).join(',');
    }).join('\n');
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'legendary-fc-vs-learn2earn-fc-predictions.csv';
    a.click();
    URL.revokeObjectURL(url);
  });

  refreshState();
})();
