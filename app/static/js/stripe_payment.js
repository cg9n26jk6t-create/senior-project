// Embedded Stripe card payment for a completed job.
//
// This uses Stripe Elements (stripe.js), which is the standard, PCI-
// compliant way to collect a card on your own page: the card number/
// expiry/CVC are typed into an iframe Stripe itself controls and
// tokenized directly with Stripe from the browser. The raw card number
// never passes through -- or gets seen by -- our own server; our backend
// only ever sees a PaymentIntent id, created in customer.create_payment_intent
// and re-verified with Stripe in customer.confirm_card_payment before the
// request is marked paid.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("card-payment-form");
    if (!form || typeof Stripe === "undefined") return;

    const stripe = Stripe(window.ROADRESCUE_STRIPE_PUBLISHABLE_KEY);
    const elements = stripe.elements();
    const card = elements.create("card", {
      style: {
        base: {
          fontSize: "16px",
          color: "#2d3142",
          fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
          "::placeholder": { color: "#6b7280" },
        },
        invalid: { color: "#c65b5b" },
      },
    });
    card.mount("#card-element");

    const errorBox = document.getElementById("card-errors");
    card.on("change", function (event) {
      errorBox.textContent = event.error ? event.error.message : "";
    });

    const submitButton = document.getElementById("card-submit-btn");
    const submitButtonDefaultText = submitButton.textContent;

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      submitButton.disabled = true;
      submitButton.textContent = "Processing...";
      errorBox.textContent = "";

      try {
        const intentResponse = await fetch(window.ROADRESCUE_CREATE_INTENT_URL, {
          method: "POST",
          headers: { "X-CSRFToken": window.ROADRESCUE_CSRF_TOKEN },
        });
        const intentData = await intentResponse.json();
        if (intentData.error) throw new Error(intentData.error);

        const confirmResult = await stripe.confirmCardPayment(intentData.client_secret, {
          payment_method: { card: card },
        });
        if (confirmResult.error) throw new Error(confirmResult.error.message);

        const verifyResponse = await fetch(window.ROADRESCUE_CONFIRM_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": window.ROADRESCUE_CSRF_TOKEN,
          },
          body: JSON.stringify({ payment_intent_id: confirmResult.paymentIntent.id }),
        });
        const verifyData = await verifyResponse.json();
        if (verifyData.error) throw new Error(verifyData.error);

        window.location.href = verifyData.redirect_url;
      } catch (err) {
        errorBox.textContent = err.message;
        submitButton.disabled = false;
        submitButton.textContent = submitButtonDefaultText;
      }
    });
  });
})();
