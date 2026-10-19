/* KTV Legacy MVP — deliberadamente ES5, sem APIs Tizen. */
var KTV = (function () {
  var cfg = window.KTV_CONFIG || {server: '', pollMs: 4000};
  var state = {version: -1, items: [], index: 0, playing: true};
  var imageTimer = null, pollTimer = null, controlsVisible = true, broken = false, legacyActive = false;
  var hlsGranted = '', videoGranted = ''; // nada de inicializar player nativo durante o boot
  function $(id) {return document.getElementById(id);}
  function text(id, value) { if ($(id)) {$(id).innerHTML = ''; $(id).appendChild(document.createTextNode(String(value)));} }
  function showError(message) { broken = true; text('error-banner', message); $('error-banner').className = ''; }
  function clearError() { broken = false; $('error-banner').className = 'hidden'; }
  function setStatus(message) {text('network-status', message);}
  function setWelcome(title, detail) {text('welcome-title', title); text('welcome-detail', detail);}
  function report(event) {
    // Mesmo transporte XMLHttpRequest usado pela API no navegador Legacy.
    xhr('GET', '/api/event?client=' + encodeURIComponent(cfg.client || 'preview') +
      '&event=' + encodeURIComponent(event) + '&ts=' + (new Date()).getTime(), function () {});
  }
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
  function ensureVideo() {
    var video = $('video-player');
    if (!video) {
      video = document.createElement('video');
      video.id = 'video-player';
      video.setAttribute('preload', 'none');
      $('frame').appendChild(video);
    }
    return video;
  }
  function ensureLegacy() {
    var legacy = $('legacy-player');
    if (!legacy) {
      legacy = document.createElement('object');
      legacy.id = 'legacy-player';
      legacy.setAttribute('classid', 'clsid:SAMSUNG-INFOLINK-PLAYER');
      legacy.style.position = 'absolute';
      legacy.style.left = '0'; legacy.style.top = '0';
      legacy.style.width = '1280px'; legacy.style.height = '720px';
      $('frame').appendChild(legacy);
    }
    return legacy;
  }
  function stopMedia() {
    if (imageTimer) {clearTimeout(imageTimer); imageTimer = null;}
    var legacy = $('legacy-player');
    if (legacyActive) {
      try {legacy.Stop();} catch (e) {}
      legacyActive = false;
    }
    if (legacy) {legacy.style.display = 'none';}
    var v = $('video-player');
    if (v) {v.onerror = null; v.onplaying = null; v.onloadeddata = null; v.onended = null;}
    var oldImage = $('image-player'); oldImage.onerror = null; oldImage.onload = null;
    if (v) {
      try {v.pause(); v.removeAttribute('src'); v.load();} catch(e) {}
      v.style.display = 'none';
    }
    $('image-player').style.display = 'none';
  }
  function advance(step) {
    if (!state.items.length) {return;}
    state.index = (state.index + step + state.items.length) % state.items.length;
    hlsGranted = ''; videoGranted = '';
    render();
  }
  function render() {
    stopMedia(); clearError();
    if (!state.items.length) {
      $('welcome').style.display = 'block';
      text('media-name', 'Playlist vazia');
      setWelcome('Conectado - aguardando midias', 'Abra o painel KTV no computador, envie uma imagem e salve a playlist.');
      return;
    }
    var item = state.items[state.index];
    if (!item) {return;}
    $('welcome').style.display = 'none';
    text('media-name', (state.index + 1) + '/' + state.items.length + '  ' + item.name);
    if (item.type === 'image') {
      var img = $('image-player');
      img.onerror = function () {report('image-error'); showError('Erro ao carregar imagem. Confira a rede e o arquivo.');};
      img.onload = function () {report('image-loaded'); clearError();};
      img.style.display = 'block'; img.src = item.url;
      if (state.playing) {imageTimer = setTimeout(function () {advance(1);}, item.duration * 1000 || 10000);}
    } else if (item.type === 'hls') {
      if (hlsGranted !== item.url) {
        $('welcome').style.display = 'block';
        setWelcome('Canal pronto para testar', 'Pressione ENTER para iniciar o HLS. O plugin Samsung permanece desligado ate la.');
        setStatus('HLS AGUARDANDO ENTER');
        report('hls-deferred');
        return;
      }
      if (cfg.client === 'orsay') {
        var legacy = ensureLegacy();
        if (!legacy || typeof legacy.Play !== 'function') {
          report('hls-unavailable');
          showError('Player HLS Legacy nao disponivel neste firmware.');
          return;
        }
        legacy.OnBufferingStart = function () {report('hls-buffering'); setStatus('BUFFER HLS');};
        legacy.OnBufferingComplete = function () {report('hls-buffer-complete'); setStatus('HLS PRONTO');};
        legacy.OnConnectionFailed = function () {report('hls-error'); showError('Conexao do fluxo HLS falhou.');};
        legacy.OnRenderError = function () {report('hls-error'); showError('Erro ao renderizar o fluxo HLS.');};
        legacy.OnRenderingComplete = function () {advance(1);};
        legacy.style.display = 'block';
        try {
          if (typeof legacy.SetDisplayArea === 'function') {legacy.SetDisplayArea(0, 0, 1280, 720);}
          report('hls-start-requested');
          var result = legacy.Play(item.url + '|COMPONENT=HLS');
          if (result === false || (typeof result === 'number' && result < 0)) {
            throw new Error('plugin rejeitou o fluxo');
          }
          legacyActive = true;
        } catch (e) {report('hls-error'); showError('O plugin Samsung nao conseguiu iniciar o HLS.');}
      } else {
        // Preview web: suporte HLS HTML5 varia por navegador. Nao inclui hls.js no firmware antigo.
        var hv = ensureVideo();
        hv.onerror = function () {report('hls-error'); showError('Este navegador nao reproduz HLS nativamente. Teste no app Orsay.');};
        hv.onplaying = function () {report('video-playing');};
        hv.style.display = 'block'; hv.src = item.url;
        try {var promise = hv.play(); if (promise && promise.catch) {promise.catch(function () {report('hls-error');});}} catch(e) {report('hls-error');}
      }
    } else if (item.type === 'video') {
      if (videoGranted !== item.url) {
        $('welcome').style.display = 'block';
        setWelcome('Video pronto para testar', 'Pressione ENTER para iniciar o video.');
        setStatus('VIDEO AGUARDANDO ENTER');
        report('video-deferred');
        return;
      }
      var vid = ensureVideo();
      vid.onerror = function () {report('video-error'); showError('Video nao suportado ou indisponivel. Teste MP4 H.264/AAC; o player Legacy pode exigir API propria.');};
      vid.onloadeddata = function () {report('video-ready');};
      vid.onplaying = function () {report('video-playing');};
      vid.onended = function () {advance(1);};
      vid.style.display = 'block'; vid.src = item.url;
      if (state.playing) {
        try {
          var promise = vid.play();
          if (promise && typeof promise.catch === 'function') {
            promise.catch(function () {report('video-play-rejected'); showError('O navegador impediu a reproducao do video.');});
          }
        } catch (e) {report('video-play-rejected'); showError('Player HTML5 nao conseguiu iniciar.');}
      }
    } else {showError('Tipo de conteudo desconhecido');}
  }
  function refresh() {
    xhr('GET', '/api/state?client=' + encodeURIComponent(cfg.client || 'preview') + '&ts=' + (new Date()).getTime(), function (status, payload) {
      if (status !== 200) {
        setStatus('SEM CONEXAO (HTTP ' + status + ')');
        if (!state.items.length) {setWelcome('Servidor indisponivel', 'Verifique se o servidor Python continua aberto e confira o IP.');}
        return;
      }
      var next;
      try {next = JSON.parse(payload);} catch(e) {
        setStatus('JSON INVALIDO');
        if (!state.items.length) {setWelcome('Resposta invalida', 'O servidor respondeu, mas a TV nao conseguiu interpretar os dados.');}
        return;
      }
      if (!next || typeof next.version !== 'number' || !next.items || typeof next.items.length !== 'number') {
        setStatus('RESPOSTA INCOMPATIVEL');
        if (!state.items.length) {setWelcome('Resposta incompativel', 'Confira os registros do servidor KTV no computador.');}
        return;
      }
      setStatus('CONECTADO');
      if (state.version !== next.version) {
        state.version = next.version;
        hlsGranted = ''; videoGranted = '';
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
      var current = state.items.length ? state.items[state.index] : null;
      if (current && current.type === 'hls' && hlsGranted !== current.url) {
        hlsGranted = current.url;
        state.playing = true;
        render();
      } else if (current && current.type === 'video' && videoGranted !== current.url) {
        videoGranted = current.url;
        state.playing = true;
        render();
      } else {
      state.playing = !state.playing;
      if (state.items.length && state.items[state.index].type === 'hls' && legacyActive) {
        try {if (state.playing) {$('legacy-player').Resume();} else {$('legacy-player').Pause();}} catch(e) {report('hls-error');}
      } else if (state.items.length && state.items[state.index].type === 'video') {
        try {if (state.playing) {$('video-player').play();} else {$('video-player').pause();}} catch(e) {}
      } else {render();}
      }
    } else if (code === 40) {refresh();}
    else if (code === 10009 || code === 27) {
      try {if (window.widgetAPI && window.widgetAPI.sendExitEvent) {window.widgetAPI.sendExitEvent();}} catch(e) {}
    } else {return;}
    if (event.preventDefault) {event.preventDefault();}
    event.returnValue = false;
  }
  function start() {
    // Sinal de prontidao deve vir ANTES de qualquer consulta HTTP.
    try {
      if (window.Common && window.Common.API && window.Common.API.Widget) {
        window.widgetAPI = new window.Common.API.Widget();
        window.widgetAPI.sendReadyEvent();
      }
    } catch (readyError) {}
    text('server-url', cfg.server + '  |  APP 0.4.2');
    window.onerror = function () {
      try {report('js-error'); setStatus('ERRO DE SCRIPT'); showError('Falha no player KTV. Veja o painel de diagnostico.');} catch (ignore) {}
      return true;
    };
    document.onkeydown = key;
    report('app-start');
    refresh();
    pollTimer = setInterval(refresh, cfg.pollMs || 4000);
  }
  function safeStart() {
    try {start();} catch (e) {
      try {showError('Erro ao iniciar o KTV. Reinstale o widget e veja os logs.'); report('js-error');} catch (ignore) {}
    }
  }
  return {start:safeStart, refresh:refresh};
}());
