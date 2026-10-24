import test from 'node:test';
import assert from 'node:assert/strict';
import { loadTs } from './load-ts.mjs';
const { buildCitationMap, processCitations } = await loadTs('lib/citations.ts');
const { subscribeJobEvents } = await loadTs('lib/agentStream.ts');

const article = 'Second [web_2]. First [web_1]. Repeat [web_2].\n\n## References\n\n' +
  '- [web_1] [First](https://first.example)\n- [web_2] [Second](https://second.example)\n';
test('citations join by source ID, with appearance-based numbering', () => {
  const map = buildCitationMap(article);
  assert.equal(map.get('web_2').url, 'https://second.example');
  assert.equal(map.get('web_2').number, 1);
  assert.equal(map.get('web_1').url, 'https://first.example');
  const result = processCitations(article);
  assert.equal(result.citations.length, 2);
  assert.match(result.content, /id="ref-web_2"><strong>1\.<\/strong> <a href="https:\/\/second.example">Second/);
});
test('historical sorted references remain readable', () => {
  const old = article.replace('- [web_1] ', '- ').replace('- [web_2] ', '- ');
  assert.equal(buildCitationMap(old).get('web_2').url, 'https://second.example');
});
test('unresolved citations are not attached to unrelated references', () => {
  assert.equal(buildCitationMap('Unknown [web_999].\n\n## References\n- [web_1] [First](https://first.example)').size, 0);
});
test('titles are escaped and unsafe URLs are never emitted as HTML links', () => {
  const result = processCitations('[web_1]\n\n## References\n- [web_1] ["><img src=x>](javascript:alert(1))');
  assert.ok(!result.content.includes('<img'));
  assert.ok(!result.content.includes('href="javascript:'));
});
test('code and ordinary Markdown link labels are not rewritten', () => {
  const result = processCitations('`[web_2]` [web_2](https://other.example)\n\n' + article);
  assert.ok(result.content.includes('`[web_2]` [web_2](https://other.example)'));
});

const tick = () => new Promise(resolve => setImmediate(resolve));
function streamFixture(fetcher) {
  globalThis.localStorage = { getItem: () => 'test-token' };
  const document = new EventTarget();
  document.hidden = false;
  globalThis.document = document;
  globalThis.window = { clearTimeout, setTimeout, fetch: fetcher };
  const events = [];
  const ids = [];
  let authenticationRequired = false;
  const controller = new AbortController();
  const callbacks = { onEvent: event => events.push(event), onThreadId: id => ids.push(id),
    onAuthenticationRequired: () => { authenticationRequired = true; } };
  return { document, events, ids, controller, callbacks, authRequired: () => authenticationRequired };
}
function response(text) {
  return new Response(text, { headers: { 'content-type': 'text/event-stream' } });
}

test('job subscriptions use a GET and survive hide/show without creating runs', async () => {
  const requests = [];
  let output;
  const fixture = streamFixture(async (url, options) => {
    requests.push({ url, options });
    return response(new ReadableStream({ start(controller) { output = controller; } }));
  });
  const messages = [];
  const pending = subscribeJobEvents('job-id', 42, fixture.controller.signal, (...args) => messages.push(args), () => {});
  await tick();
  fixture.document.hidden = true; fixture.document.dispatchEvent(new Event('visibilitychange'));
  fixture.document.hidden = false; fixture.document.dispatchEvent(new Event('visibilitychange'));
  await tick();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].options.method, 'GET');
  assert.equal(requests[0].url, 'https://api.example.test/api/v1/jobs/job-id/events?after=42');
  output.enqueue(new TextEncoder().encode('id: 43\nevent: status\ndata: {"status":"running"}\n\n'));
  output.close(); await pending;
  assert.equal(messages[0][0], 43);
});

test('subscription errors are surfaced to the reconnecting hook', async () => {
  const fixture = streamFixture(async () => new Response('', { status: 503 }));
  await assert.rejects(subscribeJobEvents('job', 0, fixture.controller.signal, () => {}, () => {}), /503/);
});

test('closing a page aborts only its subscription', async () => {
  let requests = 0;
  const fixture = streamFixture(async (url, options) => {
    requests++;
    return response(new ReadableStream({ start(controller) { options.signal.addEventListener('abort', () => controller.error(new Error('aborted'))); } }));
  });
  const pending = subscribeJobEvents('job', 0, fixture.controller.signal, () => {}, () => {});
  await tick(); fixture.controller.abort(); await pending;
  assert.equal(requests, 1);
});

test('restored login waits for validation before protected-route navigation', async () => {
  delete globalThis.window;
  delete globalThis.document;
  const React = await import('react');
  const { renderToString } = await import('react-dom/server');
  const { MemoryRouter } = await import('react-router-dom');
  globalThis.localStorage = { getItem: () => 'stored-token' };
  const { AuthProvider } = await loadTs('context/AuthContext.tsx');
  const { ProtectedRoute } = await loadTs('components/custom/ProtectedRoute.tsx');
  const html = renderToString(React.createElement(AuthProvider, null,
    React.createElement(MemoryRouter, null, React.createElement(ProtectedRoute))));
  assert.ok(html.includes('Restoring your session'));
  assert.ok(html.includes('role="status"'));
});

test('escaped brackets in source titles preserve their URL', () => {
  const map = buildCitationMap('[web_1]\n\n## References\n- [web_1] [Study \\[2026\\]](https://study.example)');
  assert.equal(map.get('web_1').title, 'Study [2026]');
  assert.equal(map.get('web_1').url, 'https://study.example');
});


test('local draft recovery preserves text and version, and rejects corrupted data', async () => {
  const values = new Map();
  globalThis.sessionStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  const { readRecovery, storeRecovery, clearRecovery, sameText, acknowledgeRecovery } = await loadTs('lib/draftRecovery.ts');
  const text = { title: 'Draft', content: 'Unsaved text', base_version: 3 };
  storeRecovery('a', text);
  assert.deepEqual(readRecovery('a'), text);
  assert.equal(sameText(text, { title: 'Draft', content: 'Newer server text' }), false);
  const newer = { ...text, content: 'New editor buffer' }; storeRecovery('a', newer);
  acknowledgeRecovery('a', text, text); assert.deepEqual(readRecovery('a'), newer);
  values.set('blog-gen:draft:a', '{broken'); assert.equal(readRecovery('a'), null);
  clearRecovery('a'); assert.equal(values.size, 0);
});

test('lost job-creation responses reuse the same idempotency key', async () => {
  delete globalThis.window; delete globalThis.document;
  const values = new Map();
  globalThis.sessionStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  globalThis.localStorage = { getItem: () => null };
  const { api } = await loadTs('lib/api.ts');
  const { createJobOnce } = await loadTs('lib/workspaceApi.ts');
  const requests = [];
  api.defaults.adapter = async config => {
    requests.push(JSON.parse(config.data));
    if (requests.length === 1) throw new Error('Lost response');
    return { data: { id: 'saved-job' }, status: 201, statusText: 'Created', headers: {}, config };
  };
  await assert.rejects(createJobOnce({ topic: 'Test' }));
  const result = await createJobOnce({ topic: 'Test' });
  assert.equal(result.id, 'saved-job');
  assert.equal(requests[0].idempotency_key, requests[1].idempotency_key);
  assert.equal(values.size, 0);
});

test('draft preview sanitizes active HTML while preserving citation targets', async () => {
  delete globalThis.window; delete globalThis.document;
  const React = await import('react');
  const { renderToStaticMarkup } = await import('react-dom/server');
  const { default: Markdown } = await loadTs('components/custom/MarkdownWithCitations.tsx');
  const html = renderToStaticMarkup(React.createElement(Markdown, { content: '<iframe src="https://example.invalid"></iframe><script>alert(1)</script>\n\n' + article }));
  assert.ok(!html.includes('<iframe'));
  assert.ok(!html.includes('<script'));
  assert.ok(html.includes('id="user-content-ref-web_2"'));
  assert.ok(html.includes('href="#ref-web_2"'));
});


test('an already-aborted subscription never opens a network request', async () => {
  let requests = 0;
  const fixture = streamFixture(async () => { requests++; return response(''); });
  fixture.controller.abort();
  await subscribeJobEvents('job', 0, fixture.controller.signal, () => {}, () => {});
  assert.equal(requests, 0);
});

test('server-normalized titles clear a matching recovery buffer', async () => {
  const values = new Map();
  globalThis.sessionStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  const { storeRecovery, readRecovery, acknowledgeRecovery } = await loadTs('lib/draftRecovery.ts');
  const raw = { title: ' Draft ', content: 'Text', base_version: 1 };
  const normalized = { ...raw, title: 'Draft', base_version: 2 };
  storeRecovery('a', raw); acknowledgeRecovery('a', normalized, raw, normalized);
  assert.equal(readRecovery('a'), null);
});
