const form = document.getElementById("ioc-form");
const valueInput = document.getElementById("value");
const tagInput = document.getElementById("tag-input");
const addTagBtn = document.getElementById("add-tag-btn");
const suggestions = document.getElementById("tag-suggestions");
const chipsList = document.getElementById("tag-chips");
const message = document.getElementById("message");

const tags = new Set();

function showMessage(text, isError) {
  message.textContent = text;
  message.style.color = isError ? "red" : "green";
}

function renderChips() {
  chipsList.innerHTML = "";
  for (const tag of tags) {
    const li = document.createElement("li");
    const chip = document.createElement("span");
    chip.textContent = tag + " ";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "x";
    remove.addEventListener("click", () => {
      tags.delete(tag);
      renderChips();
    });
    chip.appendChild(remove);
    li.appendChild(chip);
    chipsList.appendChild(li);
  }
}

function addTag() {
  const name = tagInput.value.trim().toLowerCase();
  if (!name) return;
  tags.add(name);
  tagInput.value = "";
  tagSuggest.hide(suggestions);
  renderChips();
}

addTagBtn.addEventListener("click", addTag);
tagInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addTag();
  }
});

// existing-tag suggestions while typing; picking one adds the chip directly
tagSuggest.attach(
  tagInput,
  suggestions,
  () => tagInput.value,   // the whole input is the tag being typed
  () => [...tags],        // never suggest a chip that is already added
  (name) => {
    tags.add(name);
    tagInput.value = "";
    renderChips();
  },
);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = valueInput.value;
  try {
    const res = await fetch("/api/iocs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, tags: [...tags] }),
    });
    const data = await res.json();
    if (res.status === 201) {
      showMessage(
        `Created IOC #${data.id} [${data.type}]: ${data.value} tags=[${data.tags.map((t) => t.name).join(", ")}]`,
        false,
      );
      form.reset();
      tags.clear();
      tagSuggest.hide(suggestions);
      renderChips();
      // tags on the created IOC now exist server-side; refresh the cache
      tagSuggest.refresh();
    } else {
      showMessage(data.detail || `Error ${res.status}`, true);
    }
  } catch (err) {
    showMessage(`Request failed: ${err}`, true);
  }
});

tagSuggest.load();
