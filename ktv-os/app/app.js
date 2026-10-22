(function () {
  'use strict';
  var currentRoute = 'inicio';
  var overlay = document.getElementById('dialog-overlay');
  var dialogClose = document.getElementById('dialog-close');
  var video = document.getElementById('video-player');
  var image = document.getElementById('image-player');
  function el(id) { return document.getElementById(id); }
  function clock() {
    el('clock').textContent = new Date().toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
  }
  clock(); setInterval(clock, 20000);
  function dialog(title, body) {
    el('dialog-title').textContent = title;
    el('dialog-message').textContent = body;
    overlay.hidden = false; dialogClose.focus();
  }
  function closeDialog() {
    if (overlay.hidden) return;
    video.pause(); video.removeAttribute('src'); video.load(); video.hidden = true;
    image.removeAttribute('src'); image.hidden = true; overlay.hidden = true;
    var active = document.querySelector('.nav-link.active');
    if (active) active.focus();
  }
  dialogClose.addEventListener('click', closeDialog);
  overlay.addEventListener('click', function (e) { if (e.target === overlay) closeDialog(); });
  function route(name) {
    if (!document.querySelector('[data-screen="' + name + '"]')) return;
    currentRoute = name;
    Array.prototype.forEach.call(document.querySelectorAll('.screen'), function (s) { s.classList.toggle('active', s.getAttribute('data-screen') === name); });
    Array.prototype.forEach.call(document.querySelectorAll('.nav-link'), function (n) { n.classList.toggle('active', n.getAttribute('data-route') === name); });
    var first = document.querySelector('.nav-link.active'); if (first) first.focus();
    if (name === 'usb') loadUSB();
    if (name === 'canais') loadChannels();
  }
  function activate(button) {
    var r = button.getAttribute('data-route'), a = button.getAttribute('data-action');
    if (r) { route(r); return; }
    if (a === 'tv-aberta') {
      dialog('TV aberta', 'A antena continua conectada à Samsung. Pressione SOURCE no controle da TV e selecione TV / Antena.\n\nPara usar canais abertos dentro do KTV OS precisaremos, futuramente, de um sintonizador ISDB-Tb compatível conectado ao computador.');
    } else if (a === 'sources') {
      dialog('Entradas HDMI', 'As portas HDMI pertencem à Samsung. Para alternar, use SOURCE no controle da televisão.\n\nA integração HDMI-CEC poderá ser adicionada quando identificarmos um adaptador e um controle compatíveis.');
    } else if (a === 'fullscreen') {
      var fn = document.documentElement.requestFullscreen;
      if (!document.fullscreenElement && fn) fn.call(document.documentElement).catch(function () { dialog('Tela cheia', 'Pressione F11 no navegador para colocar o KTV OS em tela cheia.'); });
      else if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen();
    }
  }
  document.addEventListener('click', function (e) {
    var button = e.target.closest('[data-action],[data-route]');
    if (button) activate(button);
  });
  function focusables() {
    var root = overlay.hidden ? document : overlay;
    return Array.prototype.filter.call(root.querySelectorAll('button.focusable'), function (b) {
      return b.getClientRects().length && !b.disabled;
    });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' || e.key === 'Backspace') {
      if (!overlay.hidden) { e.preventDefault(); closeDialog(); }
      else if (currentRoute !== 'inicio') { e.preventDefault(); route('inicio'); }
      return;
    }
    if (e.key.toLowerCase() === 'f' && overlay.hidden) {
      e.preventDefault(); activate(document.querySelector('[data-action="fullscreen"]')); return;
    }
    if (['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].indexOf(e.key) === -1) return;
    var all = focusables(); if (!all.length) return;
    var active = document.activeElement;
    if (all.indexOf(active) === -1) { e.preventDefault(); all[0].focus(); return; }
    var ar = active.getBoundingClientRect();
    var ax = (ar.left+ar.right)/2, ay = (ar.top+ar.bottom)/2;
    var horizontal = e.key === 'ArrowLeft' || e.key === 'ArrowRight';
    var sign = e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 1;
    var best=null, score=Infinity;
    all.forEach(function (candidate) {
      if (candidate === active) return;
      var r=candidate.getBoundingClientRect(), dx=(r.left+r.right)/2-ax, dy=(r.top+r.bottom)/2-ay;
      var main = (horizontal?dx:dy)*sign, cross = Math.abs(horizontal?dy:dx);
      if (main <= 5) return;
      var value=main + cross*1.7;
      if (value<score) {best=candidate;score=value;}
    });
    if (best) {e.preventDefault();best.focus();}
  });
  function makeCard(title, description, onClick) {
    var b = document.createElement('button'); b.className='info-card focusable'; b.type='button';
    var icon=document.createElement('span');icon.className='card-icon';icon.textContent='▷';
    var strong=document.createElement('strong');strong.textContent=title;
    var small=document.createElement('small');small.textContent=description;
    b.appendChild(icon);b.appendChild(strong);b.appendChild(small);
    b.addEventListener('click',onClick);return b;
  }
  function message(container, text) {container.textContent=''; var p=document.createElement('div');p.className='empty';p.textContent=text;container.appendChild(p);}
  function get(url,cb) {
    fetch(url,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();}).then(function(data){cb(null,data);}).catch(function(err){cb(err);});
  }
  function playItem(item) {
    if (item.type === 'image') {
      dialog(item.name,'Imagem do computador.');
      image.src='/media/'+encodeURIComponent(item.name);image.hidden=false;
    } else if (item.type === 'video' || item.type === 'audio') {
      dialog(item.name,'Reprodução local do computador.');
      video.src='/media/'+encodeURIComponent(item.name);video.hidden=false;
      video.play().catch(function(){el('dialog-message').textContent='Pressione Play para iniciar o vídeo ou áudio.';});
    }
  }
  function loadUSB() {
    get('/api/devices',function(err,data){
      var box=el('devices');box.textContent='';
      if(err){box.textContent='Falha ao identificar unidades. '+err.message;return;}
      if (!data.devices.length) {box.textContent='Nenhum dispositivo removível identificado automaticamente.';return;}
      data.devices.forEach(function(d){var p=document.createElement('p');p.textContent=d.label;box.appendChild(p);});
    });
    get('/api/media',function(err,data){
      var box=el('media');box.textContent='';
      if(err){message(box,'Não foi possível carregar mídias: '+err.message);return;}
      if(!data.items.length){message(box,'Nenhuma mídia configurada. Inicie o servidor com --media-dir "CAMINHO_DA_PASTA" para exibir fotos, vídeos e áudios aqui.');return;}
      data.items.forEach(function(item){box.appendChild(makeCard(item.name,item.type+' · '+(item.bytes/1048576).toFixed(1)+' MB',function(){playItem(item);}));});
    });
  }
  function loadChannels() {
    get('/api/channels',function(err,data){
      var box=el('channels');box.textContent='';
      if(err){message(box,'Não foi possível abrir os canais: '+err.message);return;}
      if(!data.channels.length){message(box,'Nenhum canal cadastrado. Adicione fontes autorizadas no arquivo .ktv-os/channels.json.');return;}
      data.channels.forEach(function(c){box.appendChild(makeCard(c.name,c.category||'Canal personalizado',function(){
        dialog(c.name,'Fonte cadastrada: '+c.url+'\n\nNesta versão, vídeos MP4 podem funcionar no navegador. HLS (.m3u8) precisará de um player específico no próximo checkpoint; não estamos fingindo que já está funcionando.');
        if (/\.mp4(?:\?|$)/i.test(c.url)) {video.src=c.url;video.hidden=false;video.play().catch(function(){});}
      }));});
    });
  }
  get('/api/status',function(err,data){
    el('connection').textContent=err?'Servidor indisponível':'Sistema local conectado';
    if(!err)el('server-detail').textContent='KTV OS '+data.version+' · '+data.host+' · Acesso somente local.';
  });
  loadChannels(); loadUSB();
  document.querySelector('.nav-link.active').focus();
})();