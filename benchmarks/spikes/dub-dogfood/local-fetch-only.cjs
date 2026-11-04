// Network boundary for this disposable dogfood, not an application mock.
const original = globalThis.fetch;
globalThis.fetch = async function(input, init) {
  const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url);
  const local = ['localhost','127.0.0.1','[::1]'].includes(url.hostname);
  if (!local) throw new Error(`DOGFOOD_EXTERNAL_FETCH_BLOCKED ${url.origin}${url.pathname}`);
  try { return await original.call(this, input, init); }
  catch (error) { console.error('DOGFOOD_FETCH_FAILED', url.origin, url.pathname, error.cause?.code || error.message); throw error; }
};
