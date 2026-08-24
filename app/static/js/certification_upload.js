// Drag-and-drop wrapper around the certification file <input>.
//
// The native file input is left visible in the HTML (so the form still
// works with JavaScript disabled) -- this script only hides it and swaps
// in the styled drop zone once it has actually run, and forwards both
// dropped files and the zone's clicks back onto that same input.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const dropzone = document.getElementById("cert-dropzone");
    const fileInput = document.getElementById("cert-file-input");
    const dropzoneText = document.getElementById("dropzone-text");

    if (!dropzone || !fileInput) return;

    fileInput.classList.add("visually-hidden");
    dropzone.classList.add("dropzone-active");

    function showSelectedFile(file) {
      dropzoneText.textContent = file ? file.name : "Drag and drop a file here, or click to choose one";
    }

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput.click();
      }
    });

    fileInput.addEventListener("change", () => showSelectedFile(fileInput.files[0]));

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropzone.classList.add("dragover");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, function (event) {
        event.preventDefault();
        dropzone.classList.remove("dragover");
      });
    });

    dropzone.addEventListener("drop", function (event) {
      const files = event.dataTransfer.files;
      if (files.length > 0) {
        fileInput.files = files;
        showSelectedFile(files[0]);
      }
    });
  });
})();
