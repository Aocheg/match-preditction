(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var state = {
    snapshot: null,
    adminToken: '',
    query: '',
    userPicks: { 1: '', 2: '', 3: '' },
    adminPicks: { 1: '', 2: '', 3: '' }
  };

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

  function buildProgressionFromPicks(picks) {
    var r1 = picks[1];
    var r2 = picks[2];
    var r3 = picks[3];
    if (!r1 || !r2) return null;
    if (r1 === r2) return [r1, r2];
    if (!r3) return null;
    return [r1, r2, r3];
  }

  function formatRoundsText(rounds) {
    return rounds.map(function (t, i) { return 'R' + (i + 1) + ': ' + t; }).join(' → ');
  }

  function seriesScoreText(rounds) {
    var h = rounds.filter(function (t) { return t === 'Fellows'; }).length;
    var a = rounds.filter(function (t) { return t === 'Mentors'; }).length;
    var winner = h > a ? 'Fellows' : 'Mentors';
    return winner + ' wins ' + Math.max(h, a) + '-' + Math.min(h, a);
  }

  function syncRoundPicker(picks, attrName, r3RowId, r3NoteId, previewId, formDisabled) {
    var r1 = picks[1];
    var r2 = picks[2];
    var decidedIn2 = Boolean(r1 && r2 && r1 === r2);
    if (decidedIn2) picks[3] = '';

    var btns = document.querySelectorAll('[' + attrName + ']');
    Array.prototype.forEach.call(btns, function (btn) {
      var round = parseInt(btn.getAttribute(attrName), 10);
      var team = btn.getAttribute('data-team');
      btn.setAttribute('aria-pressed', String(picks[round] === team));
      if (round === 3) {
        btn.disabled = formDisabled || decidedIn2 || !(r1 && r2);
      } else {
        btn.disabled = !!formDisabled;
      }
    });

    var r3Row = $(r3RowId);
    var r3Note = $(r3NoteId);
    if (decidedIn2) {
      r3Row.classList.add('round-disabled');
      r3Note.textContent = 'Decided 2-0 (' + r1 + ' wins)';
    } else if (r1 && r2) {
      r3Row.classList.remove('round-disabled');
      r3Note.textContent = 'Decider required (1-1)';
    } else {
      r3Row.classList.add('round-disabled');
      r3Note.textContent = 'Decider (if 1-1)';
    }

    var preview = $(previewId);
    var prog = buildProgressionFromPicks(picks);
    if (prog) {
      preview.textContent = formatRoundsText(prog) + ' (' + seriesScoreText(prog) + ')';
    } else if (r1 && r2) {
      preview.textContent = 'Rounds 1 & 2 are split 1-1 — select Round 3 decider winner.';
    } else {
      preview.textContent = 'Select Round 1 and Round 2 winners.';
    }
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
    $('kickoff-label').textContent = match.kickoff_label || 'Venue: Leef Center Volleyball Court • 5:00 PM';
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

    if (match.status === 'finished' && match.final_rounds && match.final_rounds.length) {
      $('score-display').textContent = match.final_home_score + ' - ' + match.final_away_score;
      $('score-caption').textContent = formatRoundsText(match.final_rounds);
    } else {
      $('score-display').textContent = 'VS';
      $('score-caption').textContent = match.status === 'open' ? 'Best of 3 rounds' : 'Entry window closed';
    }

    var form = $('prediction-form');
    var closed = match.status !== 'open';
    Array.prototype.forEach.call(form.querySelectorAll('input, button'), function (ctrl) {
      ctrl.disabled = closed;
    });
    syncRoundPicker(state.userPicks, 'data-round', 'round-3-row', 'round-3-note', 'progression-preview', closed);

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

    var resultText = match.final_rounds && match.final_rounds.length
      ? formatRoundsText(match.final_rounds)
      : (match.final_home_score + ' - ' + match.final_away_score);

    var winners = snapshot.winners || [];
    if (!winners.length) {
      $('winners-sub').textContent = 'Official progression: ' + resultText + '. No predictor matched the exact sequence.';
      list.appendChild(el('p', 'muted', 'No winners for this round.'));
      return;
    }

    var suffix = ['1st Place', '2nd Place', '3rd Place'];
    $('winners-sub').textContent = 'Official progression: ' + resultText + ' — ' + snapshot.stats.exact_matches + ' exact prediction(s) found.';
    winners.forEach(function (w) {
      var tile = el('div', 'winner-tile rank-' + w.rank);
      tile.appendChild(el('div', 'winner-rank', suffix[w.rank - 1] + ' • Entry #' + w.order));
      tile.appendChild(el('div', 'winner-name', w.name));
      tile.appendChild(el('div', 'muted', w.contact_masked + ' • ' + formatRoundsText(w.rounds || [])));
      tile.appendChild(el('div', 'winner-prize', formatNaira(w.prize)));
      list.appendChild(tile);
    });
  }

  function renderStats(stats) {
    var total = stats.total || 0;
    $('stats-total').textContent = total + (total === 1 ? ' prediction submitted' : ' predictions submitted');

    var hp = total ? Math.round((stats.home_picks / total) * 100) : 0;
    var ap = total ? Math.max(0, 100 - hp) : 0;

    $('pct-home').textContent = 'Fellows: ' + hp + '%';
    $('pct-away').textContent = 'Mentors: ' + ap + '%';

    if (total === 0) {
      $('bar-home').style.width = '50%';
      $('bar-away').style.width = '50%';
    } else {
      $('bar-home').style.width = hp + '%';
      $('bar-away').style.width = ap + '%';
    }

    var chips = $('top-progressions');
    chips.textContent = '';
    if (!stats.top_progressions || !stats.top_progressions.length) {
      chips.appendChild(el('li', 'muted', 'No predictions yet.'));
      return;
    }
    stats.top_progressions.forEach(function (item) {
      var rounds = item.progression.split('>').map(function (s) { return s.trim(); });
      chips.appendChild(el('li', 'score-chip', formatRoundsText(rounds) + ' (' + item.count + ')'));
    });
  }

  function renderProgressionCell(p) {
    var wrap = el('div', 'round-seq');
    var rounds = p.rounds && p.rounds.length ? p.rounds : [];
    if (!rounds.length) {
      wrap.appendChild(el('span', null, p.home_score + ' - ' + p.away_score));
      return wrap;
    }
    rounds.forEach(function (team, idx) {
      var cls = team === 'Fellows' ? 'r-pill r-home' : 'r-pill r-away';
      wrap.appendChild(el('span', cls, 'R' + (idx + 1) + ' ' + team));
    });
    wrap.appendChild(el('span', 'r-series', '(' + p.home_score + '-' + p.away_score + ')'));
    return wrap;
  }

  function statusBadge(p) {
    if (p.outcome === 'winner') {
      return el('span', 'badge badge-winner', '#' + p.rank + ' Winner (' + formatNaira(p.prize) + ')');
    }
    if (p.outcome === 'exact_late') {
      return el('span', 'badge badge-late', 'Exact Sequence (After Top 3)');
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
      var series = p.home_score + '-' + p.away_score;
      var prog = (p.progression || '').toLowerCase();
      return p.name.toLowerCase().indexOf(q) !== -1 || prog.indexOf(q) !== -1 || series.indexOf(q) !== -1 || String(p.order) === q;
    });

    if (!rows.length) {
      var tr = el('tr');
      var td = el('td', 'empty-cell', predictions.length ? 'No matching predictions.' : 'Be the first to submit a progression!');
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
      var progTd = el('td');
      progTd.appendChild(renderProgressionCell(p));
      tr.appendChild(progTd);
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
    $('final-progression-fields').hidden = snapshot.match.status !== 'finished';

    if (snapshot.match.final_rounds && snapshot.match.final_rounds.length) {
      state.adminPicks = {
        1: snapshot.match.final_rounds[0] || '',
        2: snapshot.match.final_rounds[1] || '',
        3: snapshot.match.final_rounds[2] || ''
      };
    }
    syncRoundPicker(state.adminPicks, 'data-admin-round', 'admin-round-3-row', 'admin-round-3-note', 'admin-progression-preview', false);

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
      var progTd = el('td');
      progTd.appendChild(renderProgressionCell(p));
      tr.appendChild(progTd);
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

  Array.prototype.forEach.call(document.querySelectorAll('[data-round]'), function (btn) {
    btn.addEventListener('click', function () {
      var round = parseInt(btn.getAttribute('data-round'), 10);
      state.userPicks[round] = btn.getAttribute('data-team');
      syncRoundPicker(
        state.userPicks,
        'data-round',
        'round-3-row',
        'round-3-note',
        'progression-preview',
        state.snapshot && state.snapshot.match.status !== 'open'
      );
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-admin-round]'), function (btn) {
    btn.addEventListener('click', function () {
      var round = parseInt(btn.getAttribute('data-admin-round'), 10);
      state.adminPicks[round] = btn.getAttribute('data-team');
      syncRoundPicker(
        state.adminPicks,
        'data-admin-round',
        'admin-round-3-row',
        'admin-round-3-note',
        'admin-progression-preview',
        false
      );
    });
  });

  $('prediction-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    var feedback = $('form-feedback');
    setFeedback(feedback, '', false);

    var progression = buildProgressionFromPicks(state.userPicks);
    if (!progression) {
      setFeedback(feedback, 'Complete the round-by-round winning progression first.', true);
      return;
    }

    var btn = $('submit-btn');
    btn.disabled = true;
    try {
      var payload = {
        name: $('pred-name').value,
        contact: $('pred-contact').value,
        progression: progression
      };
      var res = await api('/api/predictions', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      renderAll(res.snapshot);
      var p = res.prediction;
      $('ticket-box').hidden = false;
      $('ticket-summary').textContent = 'Entry #' + p.order + ': ' + p.name + ' picked ' + formatRoundsText(p.rounds) + ' (' + seriesScoreText(p.rounds) + ')';
      $('ticket-meta').textContent = 'Contact: ' + p.contact_masked + ' • Recorded at ' + formatTime(p.created_at);
      $('prediction-form').reset();
      state.userPicks = { 1: '', 2: '', 3: '' };
      syncRoundPicker(state.userPicks, 'data-round', 'round-3-row', 'round-3-note', 'progression-preview', false);
      setFeedback(feedback, 'Progression submitted! Good luck.', false);
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
    $('final-progression-fields').hidden = e.target.value !== 'finished';
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
        var finalProg = buildProgressionFromPicks(state.adminPicks);
        if (!finalProg) {
          setFeedback(fb, 'Select the complete winning round progression before finishing the match.', true);
          return;
        }
        payload.final_progression = finalProg;
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
      state.adminPicks = { 1: '', 2: '', 3: '' };
      renderAll(res.snapshot);
      setFeedback(fb, 'All predictions cleared and match reopened.', false);
    } catch (err) {
      setFeedback(fb, err.message, true);
    }
  });

  $('export-csv-btn').addEventListener('click', function () {
    if (!state.snapshot) return;
    var lines = [['Order', 'Name', 'Contact', 'Winning Progression', 'Fellows Rounds', 'Mentors Rounds', 'Created At', 'Outcome', 'Prize']];
    state.snapshot.predictions.forEach(function (p) {
      lines.push([p.order, p.name, p.contact || p.contact_masked, p.progression, p.home_score, p.away_score, p.created_at, p.outcome, p.prize]);
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
    a.download = 'fellows-vs-mentors-volleyball-progression.csv';
    a.click();
    URL.revokeObjectURL(url);
  });

  refreshState();
})();
