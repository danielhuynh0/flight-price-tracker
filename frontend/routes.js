function showFlash(msg, type) {
  var el = document.getElementById("flash");
  el.innerHTML = '<div class="flash ' + type + '">' + msg + "</div>";
  setTimeout(function () { el.innerHTML = ""; }, 5000);
}

function loadRoutes() {
  var userId = document.getElementById("user-id-input").value.trim();
  if (!userId) { showFlash("Please enter your name or ID.", "error"); return; }

  fetch(API_URL + "/monitors/" + encodeURIComponent(userId))
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { showFlash(data.error, "error"); return; }
      var monitors = data.monitors || [];
      document.getElementById("routes-section").style.display = "none";
      document.getElementById("empty-section").style.display = "none";

      if (!monitors.length) {
        document.getElementById("empty-msg").textContent =
          "No active monitoring requests found for " + userId + ".";
        document.getElementById("empty-section").style.display = "block";
        return;
      }

      document.getElementById("routes-subtitle").textContent =
        "Showing active routes for " + userId + ". Alerts fire when the cheapest flight drops below your threshold.";

      var tbody = document.getElementById("routes-body");
      tbody.innerHTML = "";
      monitors.forEach(function (r) {
        var row = document.createElement("tr");
        row.id = "row-" + r.id;
        row.innerHTML =
          "<td><strong>" + r.origin + " → " + r.destination + "</strong></td>" +
          "<td>" + r.travel_date + "</td>" +
          "<td>$" + r.threshold.toFixed(2) + "</td>" +
          '<td><span class="badge badge-' + r.seat + '">' + r.seat + "</span></td>" +
          '<td style="color:#666;font-size:.85rem;">' + r.contact + "</td>" +
          '<td><button class="btn btn-danger btn-sm" onclick="cancelRoute(\'' +
          r.user_id + "','" + r.id + '\')">Cancel</button></td>';
        tbody.appendChild(row);
      });
      document.getElementById("routes-section").style.display = "block";
    })
    .catch(function (err) { showFlash("Failed to load routes: " + err.message, "error"); });
}

function cancelRoute(userId, requestId) {
  if (!confirm("Cancel this monitoring request?")) return;
  fetch(API_URL + "/monitors/" + encodeURIComponent(userId) + "/" + encodeURIComponent(requestId), {
    method: "DELETE",
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { showFlash(data.error, "error"); return; }
      var row = document.getElementById("row-" + requestId);
      if (row) row.remove();
      showFlash("Monitoring request cancelled.", "success");
    })
    .catch(function (err) { showFlash("Failed to cancel: " + err.message, "error"); });
}

var params = new URLSearchParams(window.location.search);
if (params.get("user_id")) {
  document.getElementById("user-id-input").value = params.get("user_id");
  loadRoutes();
}
