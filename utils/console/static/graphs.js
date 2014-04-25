var hitCount = [], hitSize = [], missCount = [], missSize = [];
var dataset;
var totalPoints = 100;
var updateInterval = 5000;
var now = new Date().getTime();

var options = {
    series: {
        lines: {
            lineWidth: 1.2
        },
        bars: {
            align: "center",
            fillColor: { colors: [{ opacity: 1 }, { opacity: 1}] },
            barWidth: 500,
            lineWidth: 1
        }
    },
    xaxis: {
        mode: "time",
        tickSize: [60, "second"],
        tickFormatter: function (v, axis) {
            var date = new Date(v);

            if (date.getSeconds() % 20 == 0) {
                var hours = date.getHours() < 10 ? "0" + date.getHours() : date.getHours();
                var minutes = date.getMinutes() < 10 ? "0" + date.getMinutes() : date.getMinutes();
                var seconds = date.getSeconds() < 10 ? "0" + date.getSeconds() : date.getSeconds();

                return hours + ":" + minutes;
            } else {
                return "";
            }
        },
        axisLabel: "Time",
        axisLabelUseCanvas: true,
        axisLabelFontSizePixels: 12,
        axisLabelPadding: 10
    },
    yaxis: {
            axisLabelUseCanvas: true,
            axisLabelFontSizePixels: 12,
            axisLabelPadding: 6
    },
    legend: {
        noColumns: 0,
        position:"nw"
    },
    grid: {
        backgroundColor: { colors: ["#ffffff", "#EDF5FF"] }
    }
};

function initData() {
    for (var i = 0; i < totalPoints; i++) {
        var temp = [now += updateInterval, 0];

        hitCount.push(temp);
        hitSize.push(temp);
        missCount.push(temp);
        missSize.push(temp);
    }
}

function GetData() {
    $.ajaxSetup({ cache: false });
    $.ajax({
        url: req_url,
        dataType: 'json',
        success: update,
        error: function () {
            setTimeout(GetData, updateInterval);
        }
    });
}

var req_url = "data";
var temp;

function update(_data) {
    hitCount.shift();
    hitSize.shift();
    missCount.shift();
    missSize.shift();

    now += updateInterval

    temp = [now, _data.total_cache_hit];
    hitCount.push(temp);

    temp = [now, _data.total_cache_hit_size/1024];
    hitSize.push(temp);

    temp = [now, _data.total_cache_miss];
    missCount.push(temp);

    temp = [now, _data.total_cache_miss_size/1024];
    missSize.push(temp);

    datasetCount = [
        { label: "Hit Count: " + _data.total_cache_hit, data: hitCount, lines: { lineWidth: 1.2 }, color: "#00FF00" },
        { label: "Miss Count: " + _data.total_cache_miss, data: missCount, lines: { lineWidth: 1.2}, color: "#0044FF"}
    ];

    $.plot($("#placeholder-count"), datasetCount, options);

    datasetSize = [
        { label: "Hit Size: " + (_data.total_cache_hit_size/1024).toFixed(2) + "KB", data: hitSize, lines: { lineWidth: 1.2 }, color: "#FFFF00"},
        { label: "Miss Size: " + (_data.total_cache_miss_size/1024).toFixed(2) + "KB", data: missSize, lines: { lineWidth: 1.2}, color: "#FF0000" }
    ];

    $.plot($("#placeholder-size"), datasetSize, options);

    setTimeout(GetData, updateInterval);
}


$(document).ready(function () {
    initData();

    datasetCount = [
        { label: "Hit Count: ", data: hitCount, lines: { lineWidth: 1.2 }, color: "#00FF00" },
        { label: "Miss Count: ", data: missCount, lines: { lineWidth: 1.2 }, color: "#0044FF" },
    ];

    $.plot($("#placeholder-count"), datasetCount, options);

    datasetSize = [
        { label: "Hit Size: ", data: hitSize, lines: { lineWidth: 1.2 }, color: "#FFFF00" },
        { label: "Miss Size: ", data: missSize, lines: { lineWidth: 1.2 }, color: "#FF0000" },
    ];

    $.plot($("#placeholder-size"), datasetSize, options);

    setTimeout(GetData, updateInterval);
});



