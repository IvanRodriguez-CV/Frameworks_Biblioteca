let accessToken = "";

export function setAccessToken(token) {
  accessToken = token;
}

export async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = Object.values(data).flat().find((value) => typeof value === "string");
    throw new Error(message || `La solicitud no se pudo completar (${response.status}).`);
  }
  return data;
}

export async function apiRequest(path, options = {}) {
  const headers = { Authorization: `Bearer ${accessToken}` };
  if (options.body) headers["Content-Type"] = "application/json";
  return fetch(path, { ...options, headers: { ...headers, ...options.headers } }).then(readJson);
}

export async function fetchAll(path) {
  const records = [];
  let next = path;
  while (next) {
    const page = await apiRequest(next);
    records.push(...(page.results || page));
    next = page.next;
  }
  return records;
}
