import type { FastifyInstance } from "fastify";
import pg from "pg";

export function chatMemoryRoutes(databaseUrl: string) {
  return async function (app: FastifyInstance): Promise<void> {
    const pool = new pg.Pool({ connectionString: databaseUrl });

    app.addHook("onClose", async () => {
      await pool.end();
    });

    // Admin UI page
    app.get("/admin/chat-memory", async (_request, reply) => {
      reply.type("text/html").send(adminHtml);
    });

    // Find corrupted messages
    app.get("/api/chat-memory/corrupted", async () => {
      const result = await pool.query(`
        WITH session_titles AS (
          SELECT DISTINCT ON (session_id)
            session_id,
            SUBSTRING(message->>'content' FROM 1 FOR 120) AS session_title
          FROM n8n_chat_memory
          WHERE message->>'type' = 'human'
          ORDER BY session_id, id ASC
        )
        SELECT
          m.id,
          m.session_id AS "sessionId",
          m.message->>'type' AS type,
          SUBSTRING(m.message->>'content' FROM 1 FOR 200) AS "contentPreview",
          COALESCE(st.session_title, '(no title)') AS "sessionTitle"
        FROM n8n_chat_memory m
        LEFT JOIN session_titles st ON st.session_id = m.session_id
        WHERE
          (m.message->>'type' = 'tool'
            AND m.message->>'content' ~* 'error|workflow does not exist')
          OR (m.message->>'type' = 'ai'
            AND m.message->>'content' ~* 'encountered an error|sorry.*error|encountered an issue|technical error|Calling recall_memory')
        ORDER BY m.session_id, m.id
      `);

      return { messages: result.rows, total: result.rowCount };
    });

    // Delete messages by ids
    app.delete<{ Body: { ids: number[] } }>(
      "/api/chat-memory/messages",
      async (request, reply) => {
        const { ids } = request.body ?? {};

        if (!Array.isArray(ids) || ids.length === 0) {
          return reply
            .status(400)
            .send({ error: "ids must be a non-empty array of numbers" });
        }

        if (!ids.every((id) => typeof id === "number" && Number.isInteger(id))) {
          return reply
            .status(400)
            .send({ error: "all ids must be integers" });
        }

        const result = await pool.query(
          `DELETE FROM n8n_chat_memory WHERE id = ANY($1::int[])`,
          [ids],
        );

        return { deleted: result.rowCount };
      },
    );

    // List all messages in a session
    app.get<{ Params: { sessionId: string } }>(
      "/api/chat-memory/sessions/:sessionId",
      async (request) => {
        const { sessionId } = request.params;
        const result = await pool.query(
          `SELECT
            id,
            session_id AS "sessionId",
            message->>'type' AS type,
            message->>'content' AS content
          FROM n8n_chat_memory
          WHERE session_id = $1
          ORDER BY id ASC`,
          [sessionId],
        );

        return { messages: result.rows, total: result.rowCount };
      },
    );
  };
}

const adminHtml = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Chat Memory Admin</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f1117; color: #e0e0e0; padding: 1.5rem; line-height: 1.5; }
  h1 { font-size: 1.4rem; margin-bottom: 1rem; color: #fff; }
  .toolbar { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }
  button { padding: 0.4rem 0.9rem; border: 1px solid #333; border-radius: 4px; background: #1a1d27; color: #e0e0e0; cursor: pointer; font-size: 0.85rem; }
  button:hover { background: #252836; }
  button.danger { border-color: #c0392b; color: #e74c3c; }
  button.danger:hover { background: #2a1215; }
  button:disabled { opacity: 0.4; cursor: default; }
  .badge { display: inline-block; padding: 0.1rem 0.45rem; border-radius: 3px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
  .badge-tool { background: #1e3a5f; color: #5dade2; }
  .badge-ai { background: #1a3c2a; color: #58d68d; }
  .badge-human { background: #3c2a1a; color: #e0a458; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { padding: 0.5rem 0.6rem; text-align: left; border-bottom: 1px solid #1e2030; }
  th { background: #161822; color: #999; font-weight: 600; position: sticky; top: 0; }
  tr:hover { background: #1a1d2a; }
  .preview { max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #aaa; }
  .session-title { color: #8899aa; font-style: italic; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .stats { color: #777; font-size: 0.85rem; }
  .empty { text-align: center; padding: 3rem 1rem; color: #555; }
  .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; justify-content: center; align-items: start; padding: 2rem; overflow-y: auto; }
  .modal-overlay.active { display: flex; }
  .modal { background: #161822; border: 1px solid #2a2d3a; border-radius: 8px; width: 100%; max-width: 800px; max-height: 85vh; overflow-y: auto; padding: 1.5rem; }
  .modal h2 { font-size: 1.1rem; margin-bottom: 1rem; }
  .modal .close { float: right; background: none; border: none; color: #888; font-size: 1.3rem; cursor: pointer; }
  .modal .close:hover { color: #fff; }
  .msg { padding: 0.6rem 0; border-bottom: 1px solid #1e2030; }
  .msg .meta { font-size: 0.75rem; color: #666; margin-bottom: 0.2rem; }
  .msg .content { white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; }
  .msg.corrupted { background: #1f1012; border-left: 3px solid #c0392b; padding-left: 0.6rem; }
  .loading { text-align: center; padding: 2rem; color: #555; }
  a { color: #5dade2; text-decoration: none; cursor: pointer; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>Chat Memory Admin</h1>
<div class="toolbar">
  <button id="btn-refresh" onclick="loadCorrupted()">Refresh</button>
  <button id="btn-select-all" onclick="toggleSelectAll()">Select All</button>
  <button id="btn-delete" class="danger" onclick="deleteSelected()" disabled>Delete Selected (0)</button>
  <span class="stats" id="stats"></span>
</div>
<table>
  <thead>
    <tr>
      <th style="width:30px"><input type="checkbox" id="chk-all" onchange="toggleSelectAll()"></th>
      <th>Session</th>
      <th>Type</th>
      <th>Content Preview</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>
<div id="empty-state" class="empty" style="display:none">No corrupted messages found.</div>

<div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <button class="close" onclick="closeModal()">&times;</button>
    <h2 id="modal-title">Session Messages</h2>
    <div id="modal-body"></div>
  </div>
</div>

<script>
let messages = [];
let selected = new Set();
let corruptedIds = new Set();

async function loadCorrupted() {
  document.getElementById('tbody').innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';
  document.getElementById('empty-state').style.display = 'none';
  try {
    const res = await fetch('/api/chat-memory/corrupted');
    const data = await res.json();
    messages = data.messages;
    corruptedIds = new Set(messages.map(m => m.id));
    selected.clear();
    render();
  } catch (err) {
    document.getElementById('tbody').innerHTML = '<tr><td colspan="5" class="loading">Error loading messages: ' + err.message + '</td></tr>';
  }
}

function render() {
  const tbody = document.getElementById('tbody');
  if (messages.length === 0) {
    tbody.innerHTML = '';
    document.getElementById('empty-state').style.display = 'block';
    document.getElementById('stats').textContent = '';
    updateDeleteBtn();
    return;
  }
  document.getElementById('empty-state').style.display = 'none';

  const sessions = new Map();
  for (const m of messages) {
    if (!sessions.has(m.sessionId)) sessions.set(m.sessionId, []);
    sessions.get(m.sessionId).push(m);
  }

  document.getElementById('stats').textContent = messages.length + ' corrupted message' + (messages.length !== 1 ? 's' : '') + ' in ' + sessions.size + ' session' + (sessions.size !== 1 ? 's' : '');

  let html = '';
  for (const [sessionId, msgs] of sessions) {
    for (let i = 0; i < msgs.length; i++) {
      const m = msgs[i];
      const badgeClass = m.type === 'tool' ? 'badge-tool' : m.type === 'ai' ? 'badge-ai' : 'badge-human';
      html += '<tr>' +
        '<td><input type="checkbox" data-id="' + m.id + '" ' + (selected.has(m.id) ? 'checked' : '') + ' onchange="toggleMsg(' + m.id + ')"></td>' +
        '<td class="session-title">' + (i === 0 ? escHtml(m.sessionTitle) : '') + '</td>' +
        '<td><span class="badge ' + badgeClass + '">' + escHtml(m.type) + '</span></td>' +
        '<td class="preview">' + escHtml(m.contentPreview) + '</td>' +
        '<td><a onclick="viewSession(\\'' + escAttr(m.sessionId) + '\\', \\'' + escAttr(m.sessionTitle) + '\\')">view</a></td>' +
        '</tr>';
    }
  }
  tbody.innerHTML = html;
  updateDeleteBtn();
}

function toggleMsg(id) {
  if (selected.has(id)) selected.delete(id); else selected.add(id);
  updateDeleteBtn();
}

function toggleSelectAll() {
  if (selected.size === messages.length) {
    selected.clear();
  } else {
    for (const m of messages) selected.add(m.id);
  }
  render();
}

function updateDeleteBtn() {
  const btn = document.getElementById('btn-delete');
  btn.disabled = selected.size === 0;
  btn.textContent = 'Delete Selected (' + selected.size + ')';
  document.getElementById('chk-all').checked = messages.length > 0 && selected.size === messages.length;
}

async function deleteSelected() {
  if (selected.size === 0) return;
  if (!confirm('Delete ' + selected.size + ' message(s)? This cannot be undone.')) return;
  try {
    const res = await fetch('/api/chat-memory/messages', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids: [...selected] }),
    });
    const data = await res.json();
    alert('Deleted ' + data.deleted + ' message(s).');
    loadCorrupted();
  } catch (err) {
    alert('Error: ' + err.message);
  }
}

async function viewSession(sessionId, title) {
  document.getElementById('modal-title').textContent = 'Session: ' + (title || sessionId);
  document.getElementById('modal-body').innerHTML = '<div class="loading">Loading...</div>';
  document.getElementById('modal').classList.add('active');
  try {
    const res = await fetch('/api/chat-memory/sessions/' + encodeURIComponent(sessionId));
    const data = await res.json();
    let html = '';
    for (const m of data.messages) {
      const isCorrupted = corruptedIds.has(m.id);
      const badgeClass = m.type === 'tool' ? 'badge-tool' : m.type === 'ai' ? 'badge-ai' : 'badge-human';
      html += '<div class="msg' + (isCorrupted ? ' corrupted' : '') + '">' +
        '<div class="meta"><span class="badge ' + badgeClass + '">' + escHtml(m.type) + '</span> #' + m.id + (isCorrupted ? ' <span style="color:#e74c3c">(corrupted)</span>' : '') + '</div>' +
        '<div class="content">' + escHtml(m.content) + '</div>' +
        '</div>';
    }
    document.getElementById('modal-body').innerHTML = html || '<div class="loading">No messages found.</div>';
  } catch (err) {
    document.getElementById('modal-body').innerHTML = '<div class="loading">Error: ' + err.message + '</div>';
  }
}

function closeModal() {
  document.getElementById('modal').classList.remove('active');
}

function escHtml(s) {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escAttr(s) {
  return s.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
loadCorrupted();
</script>
</body>
</html>`;
