document.addEventListener("DOMContentLoaded", function () {
  var el = document.getElementById("stats-chart-data");
  if (!el) return;
  var data = JSON.parse(el.textContent);

  // ── 每日阅读趋势 ──
  var dailyCtx = document.getElementById("dailyTrendChart");
  if (dailyCtx && data.dailyTrend) {
    var labels = data.dailyTrend.map(function (d) { return d.date.slice(5); });
    var values = data.dailyTrend.map(function (d) { return d.minutes; });
    var movingAvg = values.map(function (v, i) {
      if (i < 6) return null;
      var sum = 0;
      for (var j = i - 6; j <= i; j++) sum += values[j];
      return +(sum / 7).toFixed(1);
    });
    new Chart(dailyCtx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          { label: "每日阅读(分钟)", data: values, backgroundColor: "rgba(192,57,43,0.5)", borderRadius: 3 },
          { label: "7日平均", data: movingAvg, type: "line", borderColor: "#2C3E50", borderWidth: 2, pointRadius: 0, fill: false }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  // ── 分类分布饼图 ──
  var catCtx = document.getElementById("categoryChart");
  if (catCtx && data.categories && data.categories.length) {
    var catLabels = data.categories.map(function (c) { return c.categoryTitle || "其他"; });
    var catValues = data.categories.map(function (c) { return c.readingCount || c.val || 1; });
    var catColors = ["#C0392B", "#E67E22", "#F1C40F", "#2ECC71", "#3498DB", "#9B59B6", "#1ABC9C", "#E91E63"];
    new Chart(catCtx, {
      type: "doughnut",
      data: { labels: catLabels, datasets: [{ data: catValues, backgroundColor: catColors.slice(0, catLabels.length) }] },
      options: { responsive: true, plugins: { legend: { position: "right", labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
  }

  // ── 月度趋势 ──
  var monthCtx = document.getElementById("monthlyTrendChart");
  if (monthCtx && data.monthlyTrend) {
    new Chart(monthCtx, {
      type: "bar",
      data: {
        labels: data.monthlyTrend.map(function (d) { return d.month; }),
        datasets: [{ label: "阅读时长(分钟)", data: data.monthlyTrend.map(function (d) { return d.minutes; }), backgroundColor: "rgba(52,152,219,0.6)", borderRadius: 3 }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }

  // ── 阅读时段雷达图 ──
  var timeCtx = document.getElementById("timeRadarChart");
  if (timeCtx && data.preferTime && data.preferTime.length) {
    var timeLabels = ["6-8点", "8-10点", "10-12点", "12-14点", "14-16点", "16-18点", "18-20点", "20-22点", "22-0点", "0-2点", "2-4点", "4-6点"];
    var timeValues = data.preferTime;
    if (timeValues.length === 24) {
      var grouped = [];
      for (var i = 0; i < 24; i += 2) {
        grouped.push(timeValues[i] + (timeValues[i + 1] || 0));
      }
      new Chart(timeCtx, {
        type: "radar",
        data: { labels: timeLabels, datasets: [{ label: "阅读时长(秒)", data: grouped, backgroundColor: "rgba(192,57,43,0.2)", borderColor: "#C0392B" }] },
        options: { responsive: true, scales: { r: { beginAtZero: true, ticks: { font: { size: 9 } } } }, plugins: { legend: { display: false } } }
      });
    }
  }

  // ── 年度阅读日历热力图 ──
  var heatEl = document.getElementById("heatmap-calendar");
  if (heatEl && data.calendar) {
    var year = new Date().getFullYear();
    var startDate = new Date(year, 0, 1);
    var endDate = new Date(year, 11, 31);
    var startDay = startDate.getDay();

    var wrapper = document.createElement("div");
    wrapper.style.cssText = "overflow-x:auto;padding:4px 0";

    var monthRow = document.createElement("div");
    monthRow.style.cssText = "display:flex;gap:3px;margin-bottom:4px;font-size:11px;color:#666;padding-left:32px";
    ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"].forEach(function (m) {
      var s = document.createElement("span");
      s.textContent = m;
      s.style.flex = "1";
      monthRow.appendChild(s);
    });
    wrapper.appendChild(monthRow);

    var gridWrap = document.createElement("div");
    gridWrap.style.cssText = "display:flex;gap:3px;align-items:stretch";

    var dayCol = document.createElement("div");
    dayCol.style.cssText = "display:grid;grid-template-rows:repeat(7,14px);gap:3px;font-size:10px;color:#999;text-align:right;padding-right:4px;padding-top:0";
    ["一","三","五"].forEach(function (d) {
      var s = document.createElement("span");
      s.textContent = d;
      s.style.lineHeight = "14px";
      dayCol.appendChild(s);
    });
    gridWrap.appendChild(dayCol);

    var grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-rows:repeat(7,14px);grid-auto-flow:column;gap:3px";

    var emptyStart = startDay === 0 ? 6 : startDay - 1;
    for (var i = 0; i < emptyStart; i++) {
      var e = document.createElement("div");
      e.style.width = "14px";
      e.style.height = "14px";
      grid.appendChild(e);
    }

    function formatDate(d) {
      var mm = String(d.getMonth() + 1).padStart(2, "0");
      var dd = String(d.getDate()).padStart(2, "0");
      return d.getFullYear() + "-" + mm + "-" + dd;
    }

    for (var d = new Date(startDate); d <= endDate; d.setDate(d.getDate() + 1)) {
      var iso = formatDate(d);
      var secs = data.calendar[iso] || 0;
      var cell = document.createElement("div");
      cell.style.cssText = "width:14px;height:14px;border-radius:2px;cursor:pointer;position:relative";
      if (secs === 0) cell.style.backgroundColor = "#ebedf0";
      else if (secs < 1800) cell.style.backgroundColor = "#9be9a8";
      else if (secs < 3600) cell.style.backgroundColor = "#40c463";
      else if (secs < 7200) cell.style.backgroundColor = "#30a14e";
      else cell.style.backgroundColor = "#216e39";
      cell.title = iso + ": " + Math.round(secs / 60) + "分钟";
      cell.addEventListener("click", (function (d, s) {
        return function () { alert("\ud83d\udcc5 " + d + "\n\u23f1 " + Math.round(s / 60) + "\u5206\u949f"); };
      })(iso, secs));
      grid.appendChild(cell);
    }

    gridWrap.appendChild(grid);
    wrapper.appendChild(gridWrap);
    heatEl.appendChild(wrapper);

    var style = document.createElement("style");
    style.textContent = ".heatmap-container { overflow-x: auto; }";
    document.head.appendChild(style);
  }

  // ── 阅读目标表单提交 ──
  var goalForm = document.getElementById("goalForm");
  if (goalForm) {
    goalForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var fd = new FormData();
      fd.append("year", new Date().getFullYear());
      fd.append("target_read_time", parseInt(document.getElementById("goal-year-input").value) * 3600);
      fd.append("month", new Date().getMonth() + 1);
      fd.append("target_read_time", parseInt(document.getElementById("goal-month-input").value) * 3600);
      fetch("/stats/goal/edit", { method: "POST", body: fd })
        .then(function (r) { return r.json(); })
        .then(function () { location.reload(); });
    });
  }
});
