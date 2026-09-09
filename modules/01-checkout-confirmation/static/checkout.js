const form = document.querySelector("#checkout-form");
const button = document.querySelector("#submit-button");
const errorMessage = document.querySelector("#form-error");
const moduleSelect = document.querySelector("#module-select");
const moduleDescription = document.querySelector("#module-description");
const moduleMenuButton = document.querySelector("#module-menu-button");
const moduleMenuLabel = document.querySelector("#module-menu-label");
const moduleMenu = document.querySelector("#module-menu");

const descriptions = {
  confirmation:
    "The web app schedules one durable Activity directly—no Workflow required.",
  "webhook-retries":
    "The webhook is facing intermittent failures. Temporal retries automatically.",
  "pause-unpause":
    "A downstream bug keeps failing. An operator pauses the Activity, fixes it, and unpauses.",
  reset:
    "A downstream issue is causing delays across Activities. After the fix is deployed, reset running Activities to pick up the changes.",
  "start-delay":
    "We want to delay the confrimation and allow the user to cancel the order within a certain period. Otherwise, Temporal will durably send the confirmation.",
  "update-options":
    "A failing Activity is configured with too many retries, so an operator reduces the maximum attempts.",
  "batch-commands":
    "Generate 10 long-running Standalone Activities, then cancel them together from Temporal UI.",
  "search-attributes":
    "Generate 10 Activities, then use Search Attributes to find the five that remain running.",
  "long-running":
    "One long-running Activity sends confirmations in resumable batches of two.",
  fairness:
    "Send 10 small-merchant and 20 large-merchant confirmations through one fair Task Queue.",
  "workflow-reuse":
    "A Workflow runs fulfillment steps, then reuses the same confirmation Activity shown standalone.",
};

function selectModule(value) {
  const generatorModule = [
    "batch-commands",
    "search-attributes",
    "long-running",
    "fairness",
  ].includes(value);
  moduleSelect.value = value;
  moduleMenuLabel.textContent =
    moduleSelect.options[moduleSelect.selectedIndex].textContent;
  for (const optionButton of moduleMenu.querySelectorAll("[data-module]")) {
    const selected = optionButton.dataset.module === value;
    optionButton.classList.toggle("selected", selected);
    optionButton.setAttribute("aria-selected", String(selected));
  }
  moduleDescription.textContent = descriptions[value];
  document.body.classList.toggle("batch-mode", generatorModule);
  button.querySelector("span").textContent =
    value === "long-running"
      ? "Batch Confirmations"
      : value === "fairness"
        ? "Send Confirmations for Multiple Merchants"
      : generatorModule
        ? "Generate Activities"
        : "Place order";
  button.querySelector("strong").textContent =
    generatorModule ? "" : "$128.00";
  window.localStorage.setItem("standalone-demo-module", value);
}

function closeModuleMenu() {
  moduleMenu.classList.add("hidden");
  moduleMenuButton.setAttribute("aria-expanded", "false");
}

for (const option of moduleSelect.options) {
  const optionButton = document.createElement("button");
  optionButton.type = "button";
  optionButton.dataset.module = option.value;
  optionButton.setAttribute("role", "option");
  optionButton.textContent = option.textContent;
  optionButton.addEventListener("click", () => {
    selectModule(option.value);
    closeModuleMenu();
    moduleMenuButton.focus();
  });
  moduleMenu.append(optionButton);
}

moduleMenuButton.addEventListener("click", () => {
  const opening = moduleMenu.classList.contains("hidden");
  moduleMenu.classList.toggle("hidden", !opening);
  moduleMenuButton.setAttribute("aria-expanded", String(opening));
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".module-dropdown")) closeModuleMenu();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeModuleMenu();
});
selectModule(window.localStorage.getItem("standalone-demo-module") || "confirmation");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  button.disabled = true;
  button.classList.add("loading");
  const generatorModule = [
    "batch-commands",
    "search-attributes",
    "long-running",
    "fairness",
  ].includes(moduleSelect.value);
  button.querySelector("span").textContent =
    moduleSelect.value === "long-running"
      ? "Starting Confirmation Batch…"
      : moduleSelect.value === "fairness"
        ? "Scheduling Merchant Confirmations…"
      : generatorModule
        ? "Generating Activities…"
        : "Scheduling confirmation…";

  const formData = new FormData(form);
  try {
    const response = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name: formData.get("customer_name"),
        email: formData.get("email"),
        module: moduleSelect.value,
      }),
    });

    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "Checkout could not be completed.");
    }

    const result = await response.json();
    window.location.assign(result.confirmation_url);
  } catch (error) {
    errorMessage.textContent = error.message;
    button.disabled = false;
    button.classList.remove("loading");
    button.querySelector("span").textContent =
      moduleSelect.value === "long-running"
        ? "Batch Confirmations"
        : moduleSelect.value === "fairness"
          ? "Send Confirmations for Multiple Merchants"
        : generatorModule
          ? "Generate Activities"
          : "Place order";
  }
});
