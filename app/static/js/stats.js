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
    var CELL = 14, GAP = 3, COL_W = CELL + GAP;

    var daysInMonth = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if ((year % 4 === 0 && year % 100 !== 0) || year % 400 === 0) daysInMonth[1] = 29;

    var startDate = new Date(year, 0, 1);
    var startDay = startDate.getDay();
    var emptyStart = startDay === 0 ? 6 : startDay - 1;
    var totalDays = 365 + (daysInMonth[1] === 29 ? 1 : 0);
    var totalWeeks = Math.ceil((emptyStart + totalDays) / 7);

    function fmtDate(d) {
      var mm = String(d.getMonth() + 1).padStart(2, "0");
      var dd = String(d.getDate()).padStart(2, "0");
      return d.getFullYear() + "-" + mm + "-" + dd;
    }

    var wrapper = document.createElement("div");
    wrapper.style.cssText = "overflow-x:auto;padding:4px 0";

    // ── 月份标签行 ──
    var monthWrap = document.createElement("div");
    monthWrap.style.cssText = "position:relative;height:18px;margin-bottom:2px;font-size:11px;color:#666;margin-left:" + (CELL + GAP) + "px";

    var cumDays = 0;
    for (var mi = 0; mi < 12; mi++) {
      var firstWeek = Math.floor((emptyStart + cumDays) / 7);
      var lbl = document.createElement("span");
      lbl.textContent = (mi + 1) + "月";
      lbl.style.cssText = "position:absolute;left:" + (firstWeek * COL_W) + "px;top:0;white-space:nowrap";
      monthWrap.appendChild(lbl);
      cumDays += daysInMonth[mi];
    }
    wrapper.appendChild(monthWrap);

    // ── 日历网格（星期列 + 日期方块在同一个 grid 中） ──
    var grid = document.createElement("div");
    grid.style.cssText = "display:grid;grid-template-columns:" + CELL + "px repeat(" + totalWeeks + ", " + CELL + "px);gap:" + GAP + "px";

    var wdNames = ["一","二","三","四","五","六","日"];
    for (var row = 0; row < 7; row++) {
      var wdCell = document.createElement("div");
      wdCell.style.cssText = "width:" + CELL + "px;height:" + CELL + "px;font-size:10px;color:#999;display:flex;align-items:center;justify-content:flex-end";
      wdCell.textContent = wdNames[row];
      grid.appendChild(wdCell);

      // 第 1 ~ totalWeeks 列 = 日期方块
      for (var col = 0; col < totalWeeks; col++) {
        var cellIndex = col * 7 + row;
        if (cellIndex < emptyStart || cellIndex >= emptyStart + totalDays) {
          var empty = document.createElement("div");
          empty.style.cssText = "width:" + CELL + "px;height:" + CELL + "px";
          grid.appendChild(empty);
        } else {
          var d = new Date(startDate);
          d.setDate(d.getDate() + (cellIndex - emptyStart));
          var iso = fmtDate(d);
          var secs = data.calendar[iso] || 0;
          var cell = document.createElement("div");
          cell.style.cssText = "width:" + CELL + "px;height:" + CELL + "px;border-radius:2px;cursor:pointer";
          if (secs === 0) cell.style.backgroundColor = "#ebedf0";
          else if (secs < 1800) cell.style.backgroundColor = "#9be9a8";
          else if (secs < 3600) cell.style.backgroundColor = "#40c463";
          else if (secs < 7200) cell.style.backgroundColor = "#30a14e";
          else cell.style.backgroundColor = "#216e39";
          cell.title = iso + ": " + Math.round(secs / 60) + "分钟";
          cell.addEventListener("click", (function (di, si) {
            return function () { alert("\ud83d\udcc5 " + di + "\n\u23f1 " + Math.round(si / 60) + "\u5206\u949f"); };
          })(iso, secs));
          grid.appendChild(cell);
        }
      }
    }

    wrapper.appendChild(grid);
    heatEl.appendChild(wrapper);
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
