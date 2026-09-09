const form = document.querySelector("#checkout-form");
const button = document.querySelector("#submit-button");
const errorMessage = document.querySelector("#form-error");
const moduleSelect = document.querySelector("#module-select");
const moduleDescription = document.querySelector("#module-description");

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
};

function selectModule(value) {
  const generatorModule = ["batch-commands", "search-attributes"].includes(value);
  moduleSelect.value = value;
  moduleDescription.textContent = descriptions[value];
  document.body.classList.toggle("batch-mode", generatorModule);
  button.querySelector("span").textContent =
    generatorModule ? "Generate Activities" : "Place order";
  button.querySelector("strong").textContent =
    generatorModule ? "" : "$128.00";
  window.localStorage.setItem("standalone-demo-module", value);
}

moduleSelect.addEventListener("change", () => selectModule(moduleSelect.value));
selectModule(window.localStorage.getItem("standalone-demo-module") || "confirmation");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  button.disabled = true;
  button.classList.add("loading");
  const generatorModule = ["batch-commands", "search-attributes"].includes(
    moduleSelect.value,
  );
  button.querySelector("span").textContent = generatorModule
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
    button.querySelector("span").textContent = generatorModule
      ? "Generate Activities"
      : "Place order";
  }
});
