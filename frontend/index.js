function showFlash(msg, type) {
  var el = document.getElementById("flash");
  el.innerHTML = '<div class="flash ' + type + '">' + msg + "</div>";
  setTimeout(function () { el.innerHTML = ""; }, 5000);
}

document.getElementById("search-form").addEventListener("submit", function (e) {
  e.preventDefault();
  var btn = document.getElementById("search-btn");
  btn.disabled = true;
  btn.textContent = "Searching...";
  document.getElementById("search-results").style.display = "none";

  fetch(API_URL + "/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      origin: document.getElementById("s-origin").value.toUpperCase(),
      destination: document.getElementById("s-destination").value.toUpperCase(),
      date: document.getElementById("s-date").value,
      adults: parseInt(document.getElementById("s-adults").value),
      seat: document.getElementById("s-seat").value,
    }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      btn.disabled = false;
      btn.textContent = "Search flights";
      if (data.error) { showFlash(data.error, "error"); return; }
      var flights = data.flights || [];
      if (!flights.length) { showFlash("No flights found. Try a different route or date.", "error"); return; }

      var tbody = document.getElementById("results-body");
      tbody.innerHTML = "";
      flights.forEach(function (f) {
        var row = document.createElement("tr");
        row.innerHTML =
          "<td>" + f.airline + (f.is_best ? ' <span class="badge badge-best">Best</span>' : "") + "</td>" +
          "<td>" + (f.departure || "-") + "</td>" +
          "<td>" + (f.arrival || "-") + "</td>" +
          "<td>" + (f.duration || "-") + "</td>" +
          "<td>" + (f.stops === 0 ? "Nonstop" : f.stops + " stop(s)") + "</td>" +
          "<td><strong>$" + (f.price ? f.price.toFixed(2) : "-") + "</strong></td>";
        tbody.appendChild(row);
      });
      document.getElementById("search-results").style.display = "block";
    })
    .catch(function (err) {
      btn.disabled = false;
      btn.textContent = "Search flights";
      showFlash("Search failed: " + err.message, "error");
    });
});

document.getElementById("monitor-form").addEventListener("submit", function (e) {
  e.preventDefault();
  fetch(API_URL + "/monitors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: document.getElementById("m-user-id").value.trim(),
      origin: document.getElementById("m-origin").value.toUpperCase(),
      destination: document.getElementById("m-destination").value.toUpperCase(),
      date: document.getElementById("m-date").value,
      threshold: parseFloat(document.getElementById("m-threshold").value),
      contact: document.getElementById("m-contact").value.trim(),
      seat: document.getElementById("m-seat").value,
      adults: parseInt(document.getElementById("m-adults").value),
    }),
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { showFlash(data.error, "error"); return; }
      showFlash("Monitoring started! View your routes on the My Routes page.", "success");
      document.getElementById("monitor-form").reset();
    })
    .catch(function (err) { showFlash("Failed to create monitor: " + err.message, "error"); });
});
