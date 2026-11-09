const rowsBody = document.getElementById("ioc-rows");
const status = document.getElementById("status");
const filterType = document.getElementById("filter-type");
const filterTags = document.getElementById("filter-tags");
const suggestions = document.getElementById("tag-suggestions");

function filterTokens(value) {
  return value.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
}

function partialToken(value) {
  const tokens = value.split(",");
  return tokens.length ? tokens[tokens.length - 1] : "";
}

function replacePartialToken(input, name) {
  const tokens = input.value.split(",");
  tokens[tokens.length - 1] = name;
  input.value = tokens
    .map((t) => t.trim())
    .filter(Boolean)
    .join(", ");
}

async function load() {
  const params = new URLSearchParams();
  if (filterType.value) params.set("type", filterType.value);
  if (filterTags.value.trim()) params.set("tags", filterTags.value.trim());
  const query = params.toString();
  const url = "/api/iocs" + (query ? `?${query}` : "");

  try {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) {
      status.textContent = data.detail || `Error ${res.status}`;
      status.style.color = "red";
      return;
    }
    status.textContent = `${data.total} IOC(s)`;
    status.style.color = "black";

    rowsBody.innerHTML = "";
    for (const ioc of data.items) {
      const tr = document.createElement("tr");

      const id = document.createElement("td");
      id.textContent = ioc.id;
      tr.appendChild(id);

      const value = document.createElement("td");
      value.textContent = ioc.value;
      tr.appendChild(value);

      const type = document.createElement("td");
      type.textContent = ioc.type;
      tr.appendChild(type);

      const tags = document.createElement("td");
      tags.textContent = ioc.tags.map((t) => t.name).join(", ");
      tr.appendChild(tags);

      const created = document.createElement("td");
      created.textContent = ioc.created_at;
      tr.appendChild(created);

      const actions = document.createElement("td");
      const del = document.createElement("button");
      del.textContent = "Delete";
      del.addEventListener("click", () => remove(ioc.id, ioc.value));
      actions.appendChild(del);
      tr.appendChild(actions);

      rowsBody.appendChild(tr);
    }
  } catch (err) {
    status.textContent = `Request failed: ${err}`;
    status.style.color = "red";
  }
}

async function remove(id, value) {
  if (!confirm(`Delete IOC "${value}" (id ${id})?`)) return;
  try {
    const res = await fetch(`/api/iocs/${id}`, { method: "DELETE" });
    if (res.status === 204) {
      status.style.color = "green";
      status.textContent = `Deleted IOC #${id}`;
    } else {
      const data = await res.json();
      status.style.color = "red";
      status.textContent = data.detail || `Error ${res.status}`;
    }
  } catch (err) {
    status.style.color = "red";
    status.textContent = `Request failed: ${err}`;
  }
  load();
}

document.getElementById("filter-form").addEventListener("submit", (e) => {
  e.preventDefault();
  load();
});
document.getElementById("clear-btn").addEventListener("click", () => {
  filterType.value = "";
  filterTags.value = "";
  tagSuggest.hide(suggestions);
  load();
});

// existing-tag suggestions for the comma-separated filter field: the query
// is the token currently being typed; picking one replaces that token
tagSuggest.load().then(() => {
  tagSuggest.attach(
    filterTags,
    suggestions,
    () => partialToken(filterTags.value),          // token being typed
    () => filterTokens(filterTags.value),          // tokens already in filter
    (name) => replacePartialToken(filterTags, name),
  );
});

load();
