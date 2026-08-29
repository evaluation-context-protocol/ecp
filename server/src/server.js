import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { createReadStream, existsSync, promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CLIENT_ROOT = path.join(REPO_ROOT, "client");
const EXAMPLES_ROOT = path.join(REPO_ROOT, "examples");
const PORT = Number(process.env.ECP_INSPECTOR_PORT || 6274);
const HOST = process.env.ECP_INSPECTOR_HOST || "127.0.0.1";

const jobs = new Map();
const sessions = new Map();

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
};

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url || "/", `http://${req.headers.host || `${HOST}:${PORT}`}`);

    if (url.pathname.startsWith("/api/")) {
      await handleApi(req, res, url);
      return;
    }

    await serveStatic(res, url.pathname);
  } catch (error) {
    sendJson(res, 500, {
      error: {
        code: "internal_error",
        message: error instanceof Error ? error.message : String(error),
      },
    });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`ECP Inspector listening on http://${HOST}:${PORT}`);
});

async function handleApi(req, res, url) {
  if (req.method === "GET" && url.pathname === "/api/health") {
    sendJson(res, 200, { ok: true, name: "ecp-inspector" });
    return;
  }

  if (req.method === "GET" && url.pathname === "/api/evaluations") {
    sendJson(res, 200, { evaluations: await listEvaluations() });
    return;
  }

  const evaluationMatch = url.pathname.match(/^\/api\/evaluations\/([^/]+)$/);
  if (req.method === "GET" && evaluationMatch) {
    const evaluation = await getEvaluation(decodeURIComponent(evaluationMatch[1]));
    if (!evaluation) {
      sendJson(res, 404, { error: { code: "not_found", message: "Evaluation not found" } });
      return;
    }
    sendJson(res, 200, evaluation);
    return;
  }

  const runMatch = url.pathname.match(/^\/api\/evaluations\/([^/]+)\/run$/);
  if (req.method === "POST" && runMatch) {
    const evaluation = await getEvaluation(decodeURIComponent(runMatch[1]));
    if (!evaluation) {
      sendJson(res, 404, { error: { code: "not_found", message: "Evaluation not found" } });
      return;
    }
    const job = runEvaluation(evaluation);
    sendJson(res, 202, {
      job_id: job.id,
      status: job.status,
      message: "Evaluation started",
    });
    return;
  }

  const jobMatch = url.pathname.match(/^\/api\/jobs\/([^/]+)$/);
  if (req.method === "GET" && jobMatch) {
    const job = jobs.get(decodeURIComponent(jobMatch[1]));
    if (!job) {
      sendJson(res, 404, { error: { code: "not_found", message: "Job not found" } });
      return;
    }
    sendJson(res, 200, serializeJob(job));
    return;
  }

  if (req.method === "POST" && url.pathname === "/api/sessions") {
    const body = await readJson(req);
    const target = String(body.target || "").trim();
    if (!target) {
      sendJson(res, 400, { error: { code: "invalid_target", message: "Target is required" } });
      return;
    }
    const session = await createSession(target);
    sendJson(res, 201, serializeSession(session));
    return;
  }

  const sessionRpcMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)\/rpc$/);
  if (req.method === "POST" && sessionRpcMatch) {
    const session = sessions.get(decodeURIComponent(sessionRpcMatch[1]));
    if (!session) {
      sendJson(res, 404, { error: { code: "not_found", message: "Session not found" } });
      return;
    }
    const body = await readJson(req);
    const response = await session.sendRpc(body.method, body.params || {});
    session.logs.push({
      time: new Date().toISOString(),
      level: response.error ? "error" : "info",
      message: `${body.method} ${response.error ? "failed" : "completed"}`,
      payload: response,
    });
    sendJson(res, 200, response);
    return;
  }

  const sessionMatch = url.pathname.match(/^\/api\/sessions\/([^/]+)$/);
  if (req.method === "DELETE" && sessionMatch) {
    const session = sessions.get(decodeURIComponent(sessionMatch[1]));
    if (session) {
      session.close();
      sessions.delete(session.id);
    }
    sendJson(res, 200, { ok: true });
    return;
  }

  sendJson(res, 404, { error: { code: "not_found", message: "Unknown API route" } });
}

async function listEvaluations() {
  const manifests = await findManifestFiles(EXAMPLES_ROOT);
  const evaluations = await Promise.all(manifests.map(readEvaluation));
  return evaluations
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name))
    .map(({ scenarios, raw, ...summary }) => summary);
}

async function getEvaluation(id) {
  const manifests = await findManifestFiles(EXAMPLES_ROOT);
  for (const manifestPath of manifests) {
    const evaluation = await readEvaluation(manifestPath);
    if (evaluation?.id === id) {
      return evaluation;
    }
  }
  return null;
}

async function findManifestFiles(root) {
  if (!existsSync(root)) return [];
  const entries = await fs.readdir(root, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await findManifestFiles(fullPath)));
    } else if (entry.name === "manifest.yaml" || entry.name === "manifest.yml") {
      files.push(fullPath);
    }
  }
  return files;
}

async function readEvaluation(manifestPath) {
  const raw = await fs.readFile(manifestPath, "utf-8");
  const parsed = parseManifest(raw);
  const relativePath = path.relative(REPO_ROOT, manifestPath).replaceAll(path.sep, "/");
  const stat = await fs.stat(manifestPath);
  const id = relativePath.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-|-$/g, "");
  const target = parsed.target || "";
  const scenarios = parsed.scenarios || [];
  const ready = parsed.name && target && scenarios.length > 0;

  return {
    id,
    name: parsed.name || path.basename(path.dirname(manifestPath)),
    description: `${scenarios.length} scenario${scenarios.length === 1 ? "" : "s"} in ${relativePath}`,
    status: ready ? "ready" : "not_ready",
    target,
    transport: isHttpUrl(target) ? "streamable-http" : "stdio",
    path: relativePath,
    absolute_path: manifestPath,
    scenarios,
    raw,
    created_at: stat.birthtime.toISOString(),
    updated_at: stat.mtime.toISOString(),
  };
}

function runEvaluation(evaluation) {
  const id = randomUUID();
  const job = {
    id,
    evaluation_id: evaluation.id,
    manifest: evaluation.absolute_path,
    status: "running",
    progress: 0,
    started_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    stdout: "",
    stderr: "",
    results: null,
  };
  jobs.set(id, job);

  const python = process.env.PYTHON || "python";
  const env = {
    ...process.env,
    PYTHONPATH: joinPythonPath([
      path.join(REPO_ROOT, "runtime", "python", "src"),
      path.join(REPO_ROOT, "sdk", "python", "src"),
      process.env.PYTHONPATH,
    ]),
  };

  const child = spawn(
    python,
    [
      "-m",
      "ecp_runtime.cli",
      "run",
      "--manifest",
      evaluation.absolute_path,
      "--json",
      "--no-fail-on-error",
    ],
    { cwd: REPO_ROOT, env }
  );

  child.stdout.on("data", (chunk) => {
    job.stdout += chunk.toString();
    job.updated_at = new Date().toISOString();
  });
  child.stderr.on("data", (chunk) => {
    job.stderr += chunk.toString();
    job.updated_at = new Date().toISOString();
  });
  child.on("close", (code) => {
    job.status = code === 0 ? "completed" : "failed";
    job.progress = 1;
    job.updated_at = new Date().toISOString();
    job.results = parseRuntimeJson(job.stdout) || {
      failed: code === 0 ? 0 : 1,
      total: 1,
      scenarios: [],
      error: job.stderr || job.stdout || `Runtime exited with code ${code}`,
    };
  });

  return job;
}

async function createSession(target) {
  const id = randomUUID();
  const session = isHttpUrl(target)
    ? new HttpRpcSession(id, target)
    : new StdioRpcSession(id, target);
  sessions.set(id, session);
  await session.start();
  const init = await session.sendRpc("agent/initialize", { config: {} });
  session.initialized = init;
  session.logs.push({
    time: new Date().toISOString(),
    level: init.error ? "error" : "info",
    message: init.error ? "Initialize failed" : "Initialized agent",
    payload: init,
  });
  return session;
}

class HttpRpcSession {
  constructor(id, endpoint) {
    this.id = id;
    this.target = endpoint;
    this.transport = "streamable-http";
    this.logs = [];
    this.initialized = null;
  }

  async start() {}

  async sendRpc(method, params = {}) {
    const payload = {
      jsonrpc: "2.0",
      id: Date.now(),
      method,
      params,
    };
    const response = await fetch(this.target, {
      method: "POST",
      headers: {
        Accept: "application/json, text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`HTTP RPC failed: ${response.status} ${await response.text()}`);
    }
    return response.json();
  }

  close() {}
}

class StdioRpcSession {
  constructor(id, command) {
    this.id = id;
    this.target = command;
    this.transport = "stdio";
    this.logs = [];
    this.initialized = null;
    this.process = null;
    this.pending = [];
    this.buffer = "";
  }

  async start() {
    this.process = spawn(this.target, [], { cwd: REPO_ROOT, shell: true, stdio: ["pipe", "pipe", "pipe"] });
    this.process.stdout.setEncoding("utf-8");
    this.process.stderr.setEncoding("utf-8");
    this.process.stdout.on("data", (chunk) => this.handleStdout(chunk));
    this.process.stderr.on("data", (chunk) => {
      this.logs.push({
        time: new Date().toISOString(),
        level: "stderr",
        message: chunk.toString().trim(),
      });
    });
    this.process.on("close", (code) => {
      this.logs.push({
        time: new Date().toISOString(),
        level: "info",
        message: `Process exited with code ${code}`,
      });
    });
  }

  sendRpc(method, params = {}) {
    if (!this.process?.stdin || this.process.killed) {
      throw new Error("Agent process is not running");
    }
    const id = Date.now();
    const payload = { jsonrpc: "2.0", id, method, params };
    this.process.stdin.write(`${JSON.stringify(payload)}\n`);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        reject(new Error(`Timed out waiting for ${method}`));
      }, 30000);
      this.pending.push({
        id,
        resolve: (value) => {
          clearTimeout(timer);
          resolve(value);
        },
      });
    });
  }

  handleStdout(chunk) {
    this.buffer += chunk;
    let newline = this.buffer.indexOf("\n");
    while (newline !== -1) {
      const line = this.buffer.slice(0, newline).trim();
      this.buffer = this.buffer.slice(newline + 1);
      this.handleLine(line);
      newline = this.buffer.indexOf("\n");
    }
  }

  handleLine(line) {
    if (!line) return;
    try {
      const payload = JSON.parse(line);
      const index = this.pending.findIndex((item) => item.id === payload.id);
      if (index >= 0) {
        const [pending] = this.pending.splice(index, 1);
        pending.resolve(payload);
      }
    } catch {
      this.logs.push({
        time: new Date().toISOString(),
        level: "stdout",
        message: line,
      });
    }
  }

  close() {
    if (this.process && !this.process.killed) {
      this.process.kill();
    }
  }
}

function parseManifest(raw) {
  const manifest = { scenarios: [] };
  const lines = raw.replace(/\r\n/g, "\n").split("\n");
  let currentScenario = null;
  let currentStep = null;
  let currentGrader = null;
  let currentArguments = null;

  for (const rawLine of lines) {
    const line = rawLine.replace(/#.*$/, "");
    if (!line.trim()) continue;
    const indent = line.match(/^\s*/)?.[0].length || 0;
    const text = line.trim();

    if (indent === 0 && text.includes(":")) {
      const [key, ...rest] = text.split(":");
      const value = cleanScalar(rest.join(":").trim());
      if (key === "name") manifest.name = value;
      if (key === "target") manifest.target = value;
      if (key === "manifest_version") manifest.manifest_version = value;
      continue;
    }

    if (text.startsWith("- name:")) {
      currentScenario = { name: cleanScalar(text.slice("- name:".length).trim()), steps: [] };
      manifest.scenarios.push(currentScenario);
      currentStep = null;
      currentGrader = null;
      continue;
    }

    if (text.startsWith("- input:")) {
      currentStep = {
        input: cleanScalar(text.slice("- input:".length).trim()),
        graders: [],
      };
      currentScenario?.steps.push(currentStep);
      currentGrader = null;
      continue;
    }

    if (text.startsWith("- type:")) {
      currentGrader = { type: cleanScalar(text.slice("- type:".length).trim()), arguments: {} };
      currentStep?.graders.push(currentGrader);
      currentArguments = null;
      continue;
    }

    if (currentGrader && text === "arguments:") {
      currentArguments = currentGrader.arguments;
      continue;
    }

    if (text.includes(":")) {
      const [key, ...rest] = text.split(":");
      const value = cleanScalar(rest.join(":").trim());
      if (currentArguments && indent >= 14) {
        currentArguments[key.trim()] = value;
      } else if (currentGrader) {
        currentGrader[key.trim()] = value;
      }
    }
  }

  return manifest;
}

function cleanScalar(value) {
  const trimmed = value.trim();
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

async function readJson(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

async function serveStatic(res, pathname) {
  const requested = pathname === "/" ? "/index.html" : pathname;
  const safePath = path.normalize(requested).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(CLIENT_ROOT, safePath);
  if (!filePath.startsWith(CLIENT_ROOT) || !existsSync(filePath)) {
    sendJson(res, 404, { error: { code: "not_found", message: "File not found" } });
    return;
  }

  const ext = path.extname(filePath);
  res.writeHead(200, {
    "Content-Type": MIME_TYPES[ext] || "application/octet-stream",
  });
  createReadStream(filePath).pipe(res);
}

function sendJson(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(data),
  });
  res.end(data);
}

function serializeJob(job) {
  return {
    job_id: job.id,
    evaluation_id: job.evaluation_id,
    status: job.status,
    progress: job.progress,
    results: job.results,
    stdout: job.stdout,
    stderr: job.stderr,
    started_at: job.started_at,
    updated_at: job.updated_at,
  };
}

function serializeSession(session) {
  return {
    id: session.id,
    target: session.target,
    transport: session.transport,
    initialized: session.initialized,
    logs: session.logs,
  };
}

function parseRuntimeJson(stdout) {
  const start = stdout.indexOf("{");
  const end = stdout.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) return null;
  try {
    return JSON.parse(stdout.slice(start, end + 1));
  } catch {
    return null;
  }
}

function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function joinPythonPath(paths) {
  return paths.filter(Boolean).join(process.platform === "win32" ? ";" : ":");
}
