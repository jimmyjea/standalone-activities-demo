const form = document.querySelector("#checkout-form");
const button = document.querySelector("#submit-button");
const errorMessage = document.querySelector("#form-error");
const moduleSelect = document.querySelector("#module-select");
const moduleDescription = document.querySelector("#module-description");

const descriptions = {
  confirmation:
    "The web app schedules one durable Activity directly—no Workflow required.",
  "webhook-retries":
    "The webhook will fail twice. Temporal retries automatically and succeeds on attempt three.",
};

function selectModule(value) {
  moduleSelect.value = value;
  moduleDescription.textContent = descriptions[value];
  window.localStorage.setItem("standalone-demo-module", value);
}

moduleSelect.addEventListener("change", () => selectModule(moduleSelect.value));
selectModule(window.localStorage.getItem("standalone-demo-module") || "confirmation");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  errorMessage.textContent = "";
  button.disabled = true;
  button.classList.add("loading");
  button.querySelector("span").textContent = "Scheduling confirmation…";

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
    button.querySelector("span").textContent = "Place order";
  }
});
