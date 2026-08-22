#!/usr/bin/env node

import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const clientDir = fileURLToPath(new URL("..", import.meta.url));
const buildDir = path.resolve(clientDir, process.env["ORION_BUILD_DIR"] || "build");
const port = Number(process.env["ORION_SERVE_PORT"] || 4300);
const host = process.env["ORION_SERVE_HOST"] || "127.0.0.1";

if (!fs.existsSync(path.join(buildDir, "index.html"))) {
    console.error(`No Angular build found in ${buildDir}; run "npm run build:instrumented" first.`);
    process.exit(1);
}

const proxyConfig = JSON.parse(fs.readFileSync(path.resolve(clientDir, "proxy.conf.json"), "utf8"));
const proxyRoutes = Object.entries(proxyConfig).map(([prefix, options]) => ({ prefix, target: new URL(options.target) }));

const contentTypes = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/x-icon",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff2": "font/woff2",
};

const matchProxy = (pathname) => proxyRoutes.find((route) => pathname === route.prefix || pathname.startsWith(`${route.prefix}/`));

const forward = (request, response, route) => {
    const upstream = http.request(
        {
            host: route.target.hostname,
            port: route.target.port || 80,
            path: request.url,
            method: request.method,
            headers: { ...request.headers, host: route.target.host },
        },
        (upstreamResponse) => {
            response.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
            upstreamResponse.pipe(response);
        },
    );
    upstream.on("error", (error) => {
        response.writeHead(502, { "content-type": "text/plain; charset=utf-8" });
        response.end(`Upstream ${route.target.origin} unreachable: ${error.message}\n`);
    });
    request.pipe(upstream);
};

const sendFile = (response, filePath) => {
    response.writeHead(200, {
        "content-type": contentTypes[path.extname(filePath)] || "application/octet-stream",
        "cache-control": "no-store",
    });
    fs.createReadStream(filePath).pipe(response);
};

http.createServer((request, response) => {
    const pathname = decodeURIComponent(new URL(request.url, `http://${host}:${port}`).pathname);
    const route = matchProxy(pathname);
    if (route) {
        forward(request, response, route);
        return;
    }

    const candidate = path.resolve(buildDir, `.${pathname}`);
    if (candidate.startsWith(buildDir) && fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
        sendFile(response, candidate);
        return;
    }

    sendFile(response, path.join(buildDir, "index.html"));
}).listen(port, host, () => {
    console.log(`Serving ${path.relative(clientDir, buildDir) || "."} on http://${host}:${port} (API proxied to ${proxyRoutes[0]?.target.origin})`);
});
