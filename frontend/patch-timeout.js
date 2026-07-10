// Preload module — patches the Node.js HTTP server to disable timeouts
// for long-running proxy requests (e.g. image generation taking 30-60s).
//
// Loaded via NODE_OPTIONS="--require ./patch-timeout.js"

// eslint-disable-next-line @typescript-eslint/no-require-imports
const http = require("http");

const _createServer = http.createServer;

http.createServer = function (...args) {
  const server = _createServer.apply(this, args);
  // Disable timeouts that can cause "socket hang up" on slow upstreams
  server.timeout = 0; // socket inactivity timeout → disabled
  if ("requestTimeout" in server) server.requestTimeout = 0;
  if ("headersTimeout" in server) server.headersTimeout = 0;
  server.keepAliveTimeout = 120_000;
  return server;
};

// Also disable global agent socket timeout for outgoing proxy requests
http.globalAgent = new http.Agent({
  keepAlive: true,
  keepAliveMsecs: 30_000,
  timeout: 0,
  scheduling: "lifo",
});
