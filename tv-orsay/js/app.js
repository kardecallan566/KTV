/* KTV Legacy MVP — deliberadamente ES5, sem APIs Tizen. */
var KTV = (function () {
  var cfg = window.KTV_CONFIG || {server: '', pollMs: 4000};
  var state = {version: -1, items: [], index: 0, playing: true};
  var imageTimer = null, pollTimer = null, lastVideo = '', controlsVisible = true, broken = false;
  function $(id) {return document.getElementById(id);}
  function text(id, value) { if ($(id)) {$(id).innerHTML = ''; $(id).appendChild(document.createTextNode(String(value)));} }
  function showError(message) { broken = true; text('error-banner', message); $('error-banner').className = ''; }
  function clearError() { broken = false; $('error-banner').className = 'hidden'; }
  function setStatus(message) {text('network-status', message);}
  function xhr(method, path, callback, body) {
    try {
      var request = new XMLHttpRequest();
      request.open(method, cfg.server + path, true);
      request.onreadystatechange = function () {
        if (request.readyState === 4) { callback(request.status, request.responseText); }
      };
      request.onerror = function () {callback(0, '');};
      request.send(body || null);
    } catch (e) {callback(0, '');}
  }
  function stopMedia() {
    if (imageTimer) {clearTimeout(imageTimer); imageTimer = null;}
    var v = $('video-player');
    try {v.pause(); v.removeAttribute('src'); v.load();} catch(e) {}
    v.style.display = 'none'; $('image-player').style.display = 'none';
  }
  function advance(step) {
    if (!state.items.length) {return;}
    state.index = (state.index + step + state.items.length) % state.items.length;
    render();
  }
  function render() {
    stopMedia(); clearError();
    if (!state.items.length) {
      $('welcome').style.display = 'block';
      text('media-name', 'Aguardando midias no painel');
      return;
    }
    var item = state.items[state.index];
    if (!item) {return;}
    $('welcome').style.display = 'none';
    text('media-name', (state.index + 1) + '/' + state.items.length + '  ' + item.name);
    if (item.type === 'image') {
      var img = $('image-player');
      img.onerror = function () {showError('Erro ao carregar imagem. Confira a rede e o arquivo.');};
      img.onload = function () {clearError();};
      img.style.display = 'block'; img.src = item.url;
      if (state.playing) {imageTimer = setTimeout(function () {advance(1);}, item.duration * 1000 || 10000);}
    } else if (item.type === 'video') {
      var vid = $('video-player');
      vid.onerror = function () {showError('Video nao suportado ou indisponivel. Teste MP4 H.264/AAC; o player Legacy pode exigir API propria.');};
      vid.onended = function () {advance(1);};
      vid.style.display = 'block'; vid.src = item.url;
      if (state.playing) {
        try {vid.play();} catch (e) {showError('Player HTML5 nao conseguiu iniciar.');}
      }
    } else {showError('Tipo de conteudo desconhecido');}
  }
  function refresh() {
    xhr('GET', '/api/state?ts=' + (new Date()).getTime(), function (status, payload) {
      if (status !== 200) {setStatus('SEM CONEXAO'); return;}
      var next;
      try {next = JSON.parse(payload);} catch(e) {setStatus('JSON INVALIDO');return;}
      setStatus('CONECTADO');
      if (typeof next.version !== 'number' || !next.items) {return;}
      if (state.version !== next.version) {
        state.version = next.version;
        state.items = next.items;
        state.index = next.index || 0;
        state.playing = next.playing !== false;
        render();
      }
    });
  }
  function key(event) {
    event = event || window.event;
    var code = event.keyCode || event.which;
    if (code === 37) {advance(-1);} // esquerda
    else if (code === 39) {advance(1);} // direita
    else if (code === 38) {controlsVisible = !controlsVisible; $('frame').className = controlsVisible ? '' : 'hide-chrome';}
    else if (code === 13) {
      state.playing = !state.playing;
      if (state.items.length && state.items[state.index].type === 'video') {
        try {if (state.playing) {$('video-player').play();} else {$('video-player').pause();}} catch(e) {}
      } else {render();}
    } else if (code === 40) {refresh();}
    else if (code === 10009 || code === 27) {
      try {if (window.widgetAPI && window.widgetAPI.sendExitEvent) {window.widgetAPI.sendExitEvent();}} catch(e) {}
    } else {return;}
    if (event.preventDefault) {event.preventDefault();}
    event.returnValue = false;
  }
  function start() {
    text('server-url', cfg.server);
    document.onkeydown = key;
    refresh();
    pollTimer = setInterval(refresh, cfg.pollMs || 4000);
    // Samsung Legacy widgetAPI é opcional; inicializacao nao pode depender dela.
    try {
      if (window.Common && window.Common.API && window.Common.API.Widget) {
        window.widgetAPI = new window.Common.API.Widget();
        window.widgetAPI.sendReadyEvent();
      }
    } catch(e) {}
  }
  return {start:start, refresh:refresh};
}());
