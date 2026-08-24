// Progressive enhancement for the "request assistance" form:
// - shows/requires the appointment fields only when "book an appointment"
//   is selected
// - hints that the free-text details field is required when the issue
//   type is "Other"
//
// None of this is load-bearing: the server re-validates both rules
// independently (see customer/routes.py new_request), so a customer with
// JavaScript disabled still gets a correct, if less immediate, error
// message after submitting.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const serviceModeSelect = document.getElementById("service-mode-select");
    const appointmentFields = document.getElementById("appointment-fields");
    const issueTypeSelect = document.getElementById("issue-type-select");
    const detailsHint = document.getElementById("details-hint");
    const detailsTextarea = document.getElementById("details-textarea");

    if (serviceModeSelect && appointmentFields) {
      const appointmentInputs = appointmentFields.querySelectorAll("select, input");

      function syncAppointmentFields() {
        const isAppointment = serviceModeSelect.value === "appointment";
        appointmentFields.style.display = isAppointment ? "block" : "none";
        appointmentInputs.forEach((el) => {
          el.required = isAppointment;
        });
      }

      serviceModeSelect.addEventListener("change", syncAppointmentFields);
      syncAppointmentFields();
    }

    if (issueTypeSelect && detailsHint && detailsTextarea) {
      function syncDetailsRequirement() {
        const isOther = issueTypeSelect.value === "other";
        detailsTextarea.required = isOther;
        detailsHint.textContent = isOther
          ? "Please describe what happened -- this helps the mechanic prepare."
          : "Required when you choose \"Other\", optional otherwise.";
      }

      issueTypeSelect.addEventListener("change", syncDetailsRequirement);
      syncDetailsRequirement();
    }
  });
})();
