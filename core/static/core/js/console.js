// Generated by CoffeeScript 1.11.1
(function() {
  var scrollConsole, scrolling, setLogs;

  scrolling = true;

  scrollConsole = function() {
    var console, logs;
    if (scrolling) {
      console = $('.console');
      logs = $('.logs');
      return console.animate({
        scrollTop: logs.height()
      }, 1000);
    }
  };

  scrollConsole();

  setLogs = function(logs) {
    var i, len, log, message, results;
    results = [];
    for (i = 0, len = logs.length; i < len; i++) {
      log = logs[i];
      message = log.output || log.message;
      results.push($('.logs').append("<p class='line log-" + log.status + "'>" + log.id + " " + message + "</p>"));
    }
    return results;
  };

  this.getLogs = function(last_id) {
    var url;
    if (task_running) {
      if (!last_id) {
        last_id = last_log_id;
      }
      url = GET_LOGS_URL;
      if (last_id) {
        url = url + "?last_log_id=" + last_id;
      }
      return $.get(url, function(data) {
        scrollConsole();
        if (data.length > 0) {
          last_id = data[data.length - 1].id;
          setLogs(data);
        }
        return setTimeout(getLogs(last_id), 1000);
      });
    }
  };

  getLogs();

}).call(this);
