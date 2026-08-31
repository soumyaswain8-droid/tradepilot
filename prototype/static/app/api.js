"use strict";

/* The only place fetch appears. Every screen takes a payload and renders it,
   which keeps the rendering inspectable from a console with a fixture. */

(function () {
  function json(url, opts) {
    return fetch(url, opts || {}).then(function (r) {
      if (r.status === 401) return Promise.reject({ status: 401 });
      if (!r.ok) return Promise.reject({ status: r.status });
      return r.json();
    });
  }

  function post(url, body) {
    return json(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  }

  window.TPApi = {
    calls: function (limit) {
      return json("/api/app/calls?limit=" + (limit || 50));
    },
    call: function (id) {
      return json("/api/app/calls/" + encodeURIComponent(id));
    },
    record: function () {
      return json("/api/app/record");
    },
    positions: function () {
      return json("/api/app/positions");
    },
    addPosition: function (body) {
      return post("/api/app/positions", body);
    },
    removePosition: function (id) {
      return fetch("/api/app/positions/" + encodeURIComponent(id),
                   { method: "DELETE" }).then(function (r) {
        if (r.status === 401) return Promise.reject({ status: 401 });
        if (!r.ok && r.status !== 204) return Promise.reject({ status: r.status });
        return true;
      });
    }
  };
})();
