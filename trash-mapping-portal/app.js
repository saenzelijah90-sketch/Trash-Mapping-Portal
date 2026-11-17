(() => {
  const API = (window.APP_CONFIG?.API_BASE_URL || "").replace(/\/$/, "");
  const fileInput = document.getElementById("photo-files");
  const uploadButton = document.getElementById("upload-button");
  const statusBox = document.getElementById("upload-status");
  const resultsBox = document.getElementById("upload-results");

  const rawMap = L.map("raw-map").setView([27.515, -97.881], 8);
  const processedMap = L.map("processed-map").setView([27.515, -97.881], 8);
  const tileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  [rawMap, processedMap].forEach(map => L.tileLayer(tileUrl, { attribution, maxZoom: 19 }).addTo(map));
  const rawLayer = L.layerGroup().addTo(rawMap);
  const processedLayer = L.layerGroup().addTo(processedMap);

  const esc = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[ch]));

  function addMarker(layer, map, report, color) {
    const lat = Number(report.latitude);
    const lng = Number(report.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) return false;

    const marker = L.circleMarker([lat, lng], {
      radius: 8, fillColor: color, color: color === "#df5149" ? "#a82e29" : "#176a3c",
      weight: 1.5, opacity: 1, fillOpacity: .85
    }).addTo(layer);

    const image = report.image_url
      ? `<a href="${esc(report.image_url)}" target="_blank" rel="noopener noreferrer"><img class="popup-photo" src="${esc(report.image_url)}" alt="Submitted report photograph" loading="lazy"></a>`
      : "";
    const popup = `
      <div class="popup-title">${esc(report.filename || "Photo report")}</div>
      <div class="popup-meta">
        <strong>Reported:</strong> ${esc(report.upload_date || "Unknown")}<br>
        <strong>Photo date:</strong> ${esc(report.original_date || "Unknown")}<br>
        <strong>Coordinates:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}<br>
        <strong>Status:</strong> ${esc(report.status || "Unknown")}<br>
        <strong>Camera:</strong> ${esc(report.camera || "Unknown")}
      </div>${image}`;
    marker.bindPopup(popup);
    return [lat, lng];
  }

  function fitOrDefault(map, points) {
    if (points.length) map.fitBounds(points, { padding: [25, 25], maxZoom: 16 });
    else map.setView([27.515, -97.881], 8);
  }

  async function loadMaps() {
    try {
      const [rawResponse, processedResponse] = await Promise.all([
        fetch(`${API}/api/reports/raw`), fetch(`${API}/api/reports/processed`)
      ]);
      if (!rawResponse.ok || !processedResponse.ok) throw new Error("Could not load map records. Check the API service.");
      const raw = await rawResponse.json();
      const processed = await processedResponse.json();

      rawLayer.clearLayers();
      processedLayer.clearLayers();
      const rawBounds = [];
      const processedBounds = [];
      raw.reports.forEach(report => {
        const point = addMarker(rawLayer, rawMap, report, "#df5149");
        if (point) rawBounds.push(point);
      });
      processed.reports.forEach(report => {
        const point = addMarker(processedLayer, processedMap, report, "#29965a");
        if (point) processedBounds.push(point);
      });
      fitOrDefault(rawMap, rawBounds);
      fitOrDefault(processedMap, processedBounds);

      document.getElementById("raw-count").textContent = raw.reports.length;
      document.getElementById("gps-count").textContent = raw.reports.filter(r => r.latitude !== null && r.longitude !== null).length;
      document.getElementById("pending-count").textContent = processed.reports.filter(r => (r.status || "").toLowerCase().includes("pending")).length;
      setTimeout(() => { rawMap.invalidateSize(); processedMap.invalidateSize(); }, 100);
    } catch (error) {
      statusBox.textContent = error.message;
      statusBox.classList.add("error");
    }
  }

  fileInput.addEventListener("change", () => {
    const files = Array.from(fileInput.files || []);
    const total = files.reduce((sum, file) => sum + file.size, 0) / (1024 * 1024);
    document.getElementById("selected-files").textContent = files.length
      ? `${files.length} photo(s) selected · ${total.toFixed(2)} MB total`
      : "No photographs selected.";
  });

  uploadButton.addEventListener("click", async () => {
    const files = Array.from(fileInput.files || []);
    if (!files.length) {
      statusBox.textContent = "Please choose at least one photograph.";
      statusBox.classList.add("error");
      return;
    }
    if (files.length > 20) {
      statusBox.textContent = "Please upload no more than 20 photographs at a time.";
      statusBox.classList.add("error");
      return;
    }

    uploadButton.disabled = true;
    resultsBox.replaceChildren();
    statusBox.classList.remove("error");
    let completed = 0;

    for (const file of files) {
      statusBox.textContent = `Uploading ${completed + 1} of ${files.length}: ${file.name}`;
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch(`${API}/api/upload`, { method: "POST", body: form });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Upload failed");
        const line = document.createElement("div");
        line.className = "result-item";
        line.textContent = result.filename + (result.has_gps
          ? ` — GPS: ${Number(result.latitude).toFixed(6)}, ${Number(result.longitude).toFixed(6)}`
          : " — Saved, but no GPS metadata was found.");
        resultsBox.appendChild(line);
      } catch (error) {
        const line = document.createElement("div");
        line.className = "result-item";
        line.textContent = `${file.name} — ERROR: ${error.message}`;
        resultsBox.appendChild(line);
      }
      completed += 1;
    }

    statusBox.textContent = `Finished: ${completed} photograph(s) attempted. Refreshing maps…`;
    fileInput.value = "";
    document.getElementById("selected-files").textContent = "No photographs selected.";
    await loadMaps();
    uploadButton.disabled = false;
  });

  loadMaps();
})();
