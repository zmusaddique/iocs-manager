// Shared tag-suggestion machinery: a <ul> popup under an input, fed by
// GET /api/tags. Used by the home page (chip create form) and the IOCs
// page (filter field).
const tagSuggest = (() => {
  let existingTags = [];
  let loaded = false;
  const MAX_SUGGESTIONS = 8;

  async function load() {
    if (loaded) return;
    try {
      const res = await fetch("/api/tags");
      if (res.ok) {
        const data = await res.json();
        existingTags = data.tags || [];
        loaded = true;
      } else {
        console.warn(
          "tag suggestions unavailable: /api/tags returned " + res.status,
        );
      }
    } catch (err) {
      console.warn("tag suggestions unavailable:", err);
    }
  }

  // Re-fetch after server-side tag changes (e.g. an IOC was just created).
  async function refresh() {
    loaded = false;
    await load();
  }

  function hide(listEl) {
    if (!listEl) return;
    listEl.innerHTML = "";
  }

  /**
   * inputEl: text input; listEl: <ul> positioned under it.
   * currentQuery(): the partial tag text currently being typed.
   * excluded(): tag names that must not be suggested.
   * onPick(name): what picking a suggestion does.
   */
  function attach(inputEl, listEl, currentQuery, excluded, onPick) {
    if (!inputEl || !listEl) return;  // markup drift must not break the page
    inputEl.addEventListener("input", () => suggest());
    inputEl.addEventListener("blur", () => hide(listEl));
    inputEl.addEventListener("keydown", (event) => {
      if (event.key === "Escape") hide(listEl);
    });

    function suggest() {
      hide(listEl);
      const query = currentQuery().trim().toLowerCase();
      if (!query) return;  // only suggest while the user is typing

      const taken = excluded();
      const matches = [];
      for (const name of existingTags) {
        if (name.includes(query) && !taken.includes(name)) {
          matches.push(name);
          if (matches.length === MAX_SUGGESTIONS) break;
        }
      }

      for (const name of matches) {
        const li = document.createElement("li");
        // NB: mousedown fires before the input's blur hides the popup
        li.addEventListener("mousedown", (event) => {
          event.preventDefault();
          onPick(name);
          hide(listEl);
        });
        li.textContent = name;
        listEl.appendChild(li);
      }
    }
  }

  return { load, refresh, hide, attach };
})();
