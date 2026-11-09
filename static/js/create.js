const form = document.getElementById("ioc-form");
const valueInput = document.getElementById("value");
const tagInput = document.getElementById("tag-input");
const addTagBtn = document.getElementById("add-tag-btn");
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
  renderChips();
}

addTagBtn.addEventListener("click", addTag);
tagInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    addTag();
  }
});

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
      renderChips();
    } else {
      showMessage(data.detail || `Error ${res.status}`, true);
    }
  } catch (err) {
    showMessage(`Request failed: ${err}`, true);
  }
});
