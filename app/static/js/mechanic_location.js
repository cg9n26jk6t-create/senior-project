// Lets a mechanic drop a pin marking their current position, so incoming
// on-demand requests can be sorted nearest-first (see
// mechanic.incoming_requests in app/mechanic/routes.py). Mirrors the
// customer-facing static/js/location_picker.js, but simpler: no reverse
// geocoding needed, just a lat/lng to submit.

(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    const mapEl = document.getElementById("location-map");
    if (!mapEl || typeof L === "undefined") return;

    const center = window.ROADRESCUE_MECHANIC_PIN || window.ROADRESCUE_MAP_CENTER || [33.8547, 35.8623];
    const zoom = window.ROADRESCUE_MECHANIC_PIN ? 13 : window.ROADRESCUE_MAP_ZOOM || 9;

    const map = L.map(mapEl).setView(center, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 18,
    }).addTo(map);

    const latInput = document.getElementById("location-lat");
    const lngInput = document.getElementById("location-lng");
    const saveButton = document.getElementById("save-location-btn");

    let marker = window.ROADRESCUE_MECHANIC_PIN
      ? L.marker(window.ROADRESCUE_MECHANIC_PIN, { draggable: true }).addTo(map)
      : null;

    if (marker) {
      latInput.value = window.ROADRESCUE_MECHANIC_PIN[0];
      lngInput.value = window.ROADRESCUE_MECHANIC_PIN[1];
      saveButton.disabled = false;
      saveButton.textContent = "Update my location";
      marker.on("dragend", () => setPin(marker.getLatLng().lat, marker.getLatLng().lng));
    }

    function setPin(lat, lng) {
      latInput.value = lat;
      lngInput.value = lng;
      saveButton.disabled = false;
      saveButton.textContent = "Save my location";
      if (marker) {
        marker.setLatLng([lat, lng]);
      } else {
        marker = L.marker([lat, lng], { draggable: true }).addTo(map);
        marker.on("dragend", () => setPin(marker.getLatLng().lat, marker.getLatLng().lng));
      }
    }

    map.on("click", (event) => setPin(event.latlng.lat, event.latlng.lng));
  });
})();
