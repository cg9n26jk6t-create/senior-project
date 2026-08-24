// Live mechanic-tracking view: polls the request's tracking endpoint every
// few seconds and updates the distance/ETA/progress bar in place, so the
// customer sees the mechanic "getting closer" without reloading the page.
// If the request has a map pin, this also animates a mechanic marker
// moving toward the customer's pin on a small Leaflet map.

(function () {
  "use strict";

  const POLL_INTERVAL_MS = 3000;

  document.addEventListener("DOMContentLoaded", function () {
    const card = document.getElementById("tracking-card");
    if (!card) return;

    const trackingUrl = card.dataset.trackingUrl;
    const distanceEl = document.getElementById("distance-value");
    const etaEl = document.getElementById("eta-value");
    const progressEl = document.getElementById("progress-fill");

    // Remember the starting distance so we can compute a 0-100% progress
    // bar without asking the server to do that math for us.
    const startingDistance = parseFloat(distanceEl.textContent) || 1;

    let mechanicMarker = null;
    const mapEl = document.getElementById("tracking-map");
    if (mapEl && typeof L !== "undefined" && card.dataset.customerLat) {
      const customerPos = [parseFloat(card.dataset.customerLat), parseFloat(card.dataset.customerLng)];
      const mechanicPos = [parseFloat(card.dataset.mechanicLat), parseFloat(card.dataset.mechanicLng)];

      const map = L.map(mapEl).fitBounds([customerPos, mechanicPos], { padding: [30, 30] });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
        maxZoom: 18,
      }).addTo(map);

      L.marker(customerPos).addTo(map).bindPopup("Your location");
      mechanicMarker = L.marker(mechanicPos).addTo(map).bindPopup("Mechanic");
    }

    async function poll() {
      let data;
      try {
        const response = await fetch(trackingUrl, { headers: { Accept: "application/json" } });
        if (!response.ok) return;
        data = await response.json();
      } catch (err) {
        // Network hiccup: just try again on the next tick.
        return;
      }

      if (data.status !== "enroute") {
        // The mechanic arrived (or the request otherwise moved on) --
        // reload so the page renders whatever comes next (e.g. the
        // "in progress" / "pay now" view).
        window.location.reload();
        return;
      }

      distanceEl.textContent = data.distance_km;
      etaEl.textContent = data.eta_minutes;

      const progressPct = Math.min(100, Math.max(0, (1 - data.distance_km / startingDistance) * 100));
      progressEl.style.width = progressPct + "%";

      if (mechanicMarker && data.mechanic_lat !== null && data.mechanic_lng !== null) {
        mechanicMarker.setLatLng([data.mechanic_lat, data.mechanic_lng]);
      }
    }

    const intervalId = setInterval(poll, POLL_INTERVAL_MS);
    window.addEventListener("beforeunload", () => clearInterval(intervalId));
  });
})();
