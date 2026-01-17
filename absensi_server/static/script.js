document.addEventListener('DOMContentLoaded', function () {

    // Auto Refresh Logic
    const toggle = document.getElementById('autoRefreshToggle');
    const liveBadge = document.getElementById('liveIndicator');
    let refreshInterval;

    function startRefresh() {
        if (liveBadge) liveBadge.classList.remove('d-none');
        refreshInterval = setInterval(() => {
            window.location.reload();
        }, 5000); // 5 seconds
    }

    function stopRefresh() {
        if (liveBadge) liveBadge.classList.add('d-none');
        clearInterval(refreshInterval);
    }

    if (toggle) {
        // Initial check
        if (toggle.checked) {
            startRefresh();
        }

        toggle.addEventListener('change', function () {
            if (this.checked) {
                startRefresh();
            } else {
                stopRefresh();
            }
        });
    }

});

// Export to CSV Function
function downloadCSV(csv, filename) {
    var csvFile;
    var downloadLink;

    csvFile = new Blob([csv], { type: "text/csv" });
    downloadLink = document.createElement("a");
    downloadLink.download = filename;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = "none";
    document.body.appendChild(downloadLink);
    downloadLink.click();
}

function exportTableToCSV(filename) {
    var csv = [];
    var rows = document.querySelectorAll("table tr");

    for (var i = 0; i < rows.length; i++) {
        var row = [], cols = rows[i].querySelectorAll("td, th");

        for (var j = 0; j < cols.length; j++)
            row.push('"' + cols[j].innerText + '"');

        csv.push(row.join(","));
    }

    downloadCSV(csv.join("\n"), filename);
}
