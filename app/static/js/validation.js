// Lightweight client-side validation.
//
// This is purely a UX nicety: every field validated here is re-validated
// server-side by Flask-WTF (see app/auth/forms.py and friends), so nothing
// here can be trusted or relied on for security.

(function () {
  "use strict";

  const LEBANON_PHONE_PATTERN = /^\+961\s?\d{1,2}\s?\d{3}\s?\d{3,4}$/;

  function showError(field, message) {
    clearError(field);
    const p = document.createElement("p");
    p.className = "field-error client-error";
    p.textContent = message;
    field.insertAdjacentElement("afterend", p);
  }

  function clearError(field) {
    const next = field.nextElementSibling;
    if (next && next.classList.contains("client-error")) {
      next.remove();
    }
  }

  function validatePhoneField(field) {
    if (!field.value) return true; // let "required" handle emptiness
    if (!LEBANON_PHONE_PATTERN.test(field.value.trim())) {
      showError(field, "Use the format +961 71 234 567.");
      return false;
    }
    clearError(field);
    return true;
  }

  function validatePasswordMatch(passwordField, confirmField) {
    if (!confirmField.value) return true;
    if (passwordField.value !== confirmField.value) {
      showError(confirmField, "Passwords must match.");
      return false;
    }
    clearError(confirmField);
    return true;
  }

  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("register-form");
    if (!form) return;

    const phoneField = form.querySelector('input[name="phone"]');
    const passwordField = form.querySelector('input[name="password"]');
    const confirmField = form.querySelector('input[name="confirm_password"]');

    if (phoneField) {
      phoneField.addEventListener("blur", () => validatePhoneField(phoneField));
    }
    if (passwordField && confirmField) {
      confirmField.addEventListener("blur", () => validatePasswordMatch(passwordField, confirmField));
    }

    form.addEventListener("submit", function (event) {
      let valid = true;
      if (phoneField && !validatePhoneField(phoneField)) valid = false;
      if (passwordField && confirmField && !validatePasswordMatch(passwordField, confirmField)) valid = false;
      if (!valid) event.preventDefault();
    });
  });
})();
