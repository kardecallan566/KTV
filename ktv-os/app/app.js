(function () {
  'use strict';
  var currentRoute = 'inicio';
  var overlay = document.getElementById('dialog-overlay');
  var dialogClose = document.getElementById('dialog-close');
  var video = document.getElementById('video-player');
  var image = document.getElementById('image-player');
  var playerStop = document.getElementById('player-stop');
  var compatibleButton = document.getElementById('player-compatible');
  var officialButton = document.getElementById('player-embed');
  var embedFrame = document.getElementById('tv-embed');
  var integratedPlayer = document.getElementById('integrated-player');
  var embedProvider = document.getElementById('embed-provider');
  // Defense in depth: never embed a URL from a M3U playlist or arbitrary site.
  var EMBED_URLS = [
    'https://aovivo.ebc.com.br/embed-tvbrasil.html',
    'https://culturaplay.tvcultura.com.br/channels/14/embed'
  ];
  function clearEmbed(){
    embedFrame.removeAttribute('src');integratedPlayer.hidden=true;
    embedProvider.textContent='';
  }
  var smartNotice = document.getElementById('smart-player-status');
  var noVideoPolls=0;
  var autoCompatibleAttempted=false;
  var lastNativeRequest = null;
  var nativeAvailable = false;
  var nativeActive = false;
  var pendingVideoToken = null;
  el('poweroff-button').addEventListener('click',function(){
    if(!window.confirm('Desligar o computador que está executando o KTV OS? A Samsung continuará ligada. Salve suas alterações antes de prosseguir.'))return;
    fetch('/api/system/poweroff',{method:'POST',headers:{
      'Content-Type':'application/json','X-KTV-System-Action':'confirmed'
    },body:'{}',cache:'no-store'}).then(function(r){return r.json().then(function(data){
      if(!r.ok)throw new Error(data.error||('HTTP '+r.status));return data;
    });}).then(function(){
      dialog('Desligamento solicitado','O Linux recebeu a solicitação de desligamento. Se a tela permanecer ligada, pode haver uma restrição de permissão do sistema. A TV Samsung não será desligada.');
    }).catch(function(e){dialog('Falha ao desligar','Não foi possível solicitar o desligamento: '+e.message);});
  });
  var pendingVideoTimer = null;
  var discoveredDisplays = [];
  function el(id) { return document.getElementById(id); }
  function clock() {
    el('clock').textContent = new Date().toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
  }
  clock(); setInterval(clock, 20000);
  function dialog(title, body) {
    clearEmbed();
    el('dialog-title').textContent = title;
    el('dialog-message').textContent = body;
    overlay.hidden = false;
    playerStop.hidden = !nativeActive;
    compatibleButton.hidden = !lastNativeRequest || lastNativeRequest.decode === 'compatible';
    smartNotice.textContent='';
    updateSmartOptions();
    dialogClose.focus();
  }
  function closeDialog() {
    if (overlay.hidden) return;
    if (pendingVideoToken) cancelVideoPreview();
    video.pause(); video.removeAttribute('src'); video.load(); video.hidden = true;
    image.removeAttribute('src'); image.hidden = true; clearEmbed(); overlay.hidden = true;
    if (nativeActive) stopNative();
    playerStop.hidden = true;
    compatibleButton.hidden = true;
    officialButton.hidden = true;
    lastNativeRequest = null;
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
    if (name === 'rede') refreshNetwork();
    if (name === 'navegador') el('browser-search-input').focus();
    if (name === 'canais') {loadAntenna();loadChannels();loadPublicChannels();loadPlutoFavorites();loadPlutoChannels();loadCommunityChannels();loadOpenTV();loadReidosGuide();}
    if (name === 'config') {loadBackupDevices();loadPersistenceStatus();refreshCEC();}
    if (name === 'hardware') refreshHardware();
  }
  function activate(button) {
    var r = button.getAttribute('data-route'), a = button.getAttribute('data-action');
    if (r) { route(r); return; }
    if (a === 'tv-aberta') {
      route('canais');
      setTimeout(function(){var box=document.querySelector('.tv-aberta-panel');if(box)box.scrollIntoView({behavior:'smooth',block:'start'});},50);
    } else if (a === 'sources') {
      dialog('Entradas HDMI', 'As portas HDMI pertencem à Samsung. Para alternar, use SOURCE no controle da televisão.\n\nO HDMI-CEC experimental recebe botões quando existe um adaptador CEC compatível, mas ainda não alterna as entradas da Samsung.');
    } else if (a === 'refresh-usb') {
      loadUSB();
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
    var typing = e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
    if (typing && e.key !== 'Escape') return;
    if (e.key === 'Escape' || e.key === 'Backspace') {
      if (!overlay.hidden) { e.preventDefault(); closeDialog(); }
      else if (currentRoute !== 'inicio') { e.preventDefault(); route('inicio'); }
      return;
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
  function post(path, payload, done) {
    fetch(path, {method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)}).then(function(resp){return resp.json().then(function(data){
        if(!resp.ok)throw new Error(data.error||('HTTP '+resp.status));
        return data;
      });}).then(function(data){done(null,data);}).catch(function(error){done(error);});
  }
  function stopNative() {
    nativeActive = false;
    stopQualityPolling();
    playerStop.hidden = true;
    post('/api/player/stop', {}, function(){});
    compatibleButton.hidden = true;
  }
  function updateSmartOptions(){
    officialButton.hidden=true;
    var chosen=lastNativeRequest;
    if(!chosen || !chosen.payload || chosen.payload.kind!=='public')return;
    var url='/api/smart-player/options?kind='+encodeURIComponent(chosen.payload.kind)+
            '&id='+encodeURIComponent(chosen.payload.id);
    get(url,function(err,data){
      if(overlay.hidden||lastNativeRequest!==chosen)return;
      if(err||!data||!data.embed_available||EMBED_URLS.indexOf(data.embed_url)<0){
        smartNotice.textContent='Sem player oficial incorporável confirmado para este canal. Tente o mpv normal ou modo compatível.';
        return;
      }
      officialButton.hidden=false;
      officialButton.textContent='▶ Assistir no player integrado';
      smartNotice.textContent='Player fornecido por '+data.embed_provider+'; anúncios e controles do provedor permanecem.';
    });
  }
  function openSmartEmbed(kind,id,title){
    if(kind!=='public')return;
    // Resolve from server by fixed channel ID, never by a passed URL.
    get('/api/smart-player/options?kind='+encodeURIComponent(kind)+'&id='+encodeURIComponent(id),
      function(err,data){
        if(err||!data||!data.embed_available||EMBED_URLS.indexOf(data.embed_url)<0){
          dialog(title,'Não existe player incorporável autorizado para este canal. Use a transmissão direta pelo mpv.');
          return;
        }
        if(nativeActive)stopNative();
        lastNativeRequest=null;
        dialog(title,'Assistindo dentro do KTV OS, com o player publicado pela emissora.');
        integratedPlayer.hidden=false;
        embedProvider.textContent='Fonte: '+data.embed_provider;
        embedFrame.src=data.embed_url;
        officialButton.hidden=true;
        compatibleButton.hidden=true;
        playerStop.hidden=true;
        smartNotice.textContent='A incorporação é permitida pela fonte. Ela pode exigir consentimento e mostrar anúncios da própria emissora.';
      });
  }
  officialButton.addEventListener('click',function(){
    if(!lastNativeRequest)return;
    var chosen=lastNativeRequest;
    openSmartEmbed(chosen.payload.kind,chosen.payload.id,chosen.title);
  });
  playerStop.addEventListener('click', function(){stopNative();el('dialog-message').textContent='Reprodução encerrada. Pressione Voltar.';});
  var qualityTimer = null;
  function refreshQuality(){
    get('/api/player/status',function(err,data){
      var recovery=data&&data.recovery;
      if(!err&&data.player&&data.player.playing&&recovery&&recovery.active){
        nativeActive=true;
        playerStop.hidden=false;
        if(recovery.message && recovery.attempts>0)
          smartNotice.textContent=recovery.message;
      }
      if(!err&&data.player&&!data.player.playing&&recovery&&recovery.active){
        if(recovery.phase==='attention'){
          nativeActive=false;
          playerStop.hidden=false; // Allow manual cancellation of this session.
          el('quality-telemetry').textContent=recovery.message||'Não foi possível recuperar o canal.';
          if(!overlay.hidden)el('dialog-message').textContent=
            'A recuperação automática chegou ao limite. Pressione Assistir para tentar novamente.';
          if(qualityTimer){clearInterval(qualityTimer);qualityTimer=null;}
          return;
        }
        // The server worker survives even when Chromium is fullscreen or suspended.
        nativeActive=true;
        playerStop.hidden=false;
        el('quality-telemetry').textContent='Pluto TV: reconexão automática ativa'+
          (recovery.retry_seconds?' · próxima tentativa em '+recovery.retry_seconds+' s':'')+'.';
        if(!overlay.hidden)el('dialog-message').textContent=
          'O canal foi interrompido; KTV OS está renovando o link e tentando voltar ao ar.';
        return;
      }
      if(err || !data.player || !data.player.playing){
        if(!err && nativeActive && data.player && !data.player.playing){
          nativeActive=false;
          playerStop.hidden=true;
          if(!overlay.hidden)el('dialog-message').textContent='Reprodução encerrada'+(data.player.exit_code?' (código '+data.player.exit_code+')':'')+'. O stream pode ter terminado, travado ou exigido um codec/DRM indisponível. Experimente Tentar modo compatível ou um player integrado disponível.';
          if(lastNativeRequest && lastNativeRequest.decode!=='compatible')compatibleButton.hidden=false;
          if(!overlay.hidden && lastNativeRequest)updateSmartOptions();
        }
        el('quality-telemetry').textContent='Nenhum vídeo em reprodução no mpv.';
        if(qualityTimer){clearInterval(qualityTimer);qualityTimer=null;}
        return;
      }
      var v=data.player.video;
      if(!v){el('quality-telemetry').textContent='Reproduzindo. Diagnóstico de vídeo indisponível neste dispositivo.';return;}
      var parts=[];
      if(v.width && v.height)parts.push(v.width+'×'+v.height);
      if(v.codec)parts.push('Codec: '+v.codec);
      if(v.fps)parts.push('FPS: '+v.fps);
      if(v.dropped_frames!==null && v.dropped_frames!==undefined)parts.push('Quadros perdidos: '+v.dropped_frames);
      if(v.buffer_seconds!==null && v.buffer_seconds!==undefined)parts.push('Buffer: '+v.buffer_seconds+' s');
      if(v.hardware_decoder)parts.push('Decoder: '+v.hardware_decoder);
      if(v.video_track && v.audio_track && v.video_rendered===false)parts.push('Vídeo ainda não renderizado — tente modo compatível se persistir');
      if(v.audio_track && (v.video_rendered===false || v.video_track===false)){
        noVideoPolls++;
        if(noVideoPolls>=3 && !overlay.hidden && lastNativeRequest){
          if(lastNativeRequest.decode!=='compatible')compatibleButton.hidden=false;
          smartNotice.textContent='Áudio identificado sem saída de vídeo confirmada. Tente modo compatível ou o player integrado, se disponível. Isto não prova presença de DRM.';
        }
        if(noVideoPolls>=6 && !autoCompatibleAttempted && nativeActive &&
           v.paused!==true && lastNativeRequest &&
           lastNativeRequest.decode!=='compatible' &&
           ['public','pluto','community'].indexOf(lastNativeRequest.payload.kind)>=0){
          var retry=lastNativeRequest;
          autoCompatibleAttempted=true;
          compatibleButton.hidden=true;
          smartNotice.textContent='Áudio identificado sem vídeo; tentando modo compatível automaticamente.';
          el('quality-telemetry').textContent='Tentando decodificação por software…';
          if(!overlay.hidden)el('dialog-message').textContent=
            'Detectamos áudio sem vídeo por vários segundos. O KTV OS está tentando o modo compatível automaticamente.';
          nativePlay(Object.assign({},retry.payload),retry.title,null,'compatible',true,retry);
          return;
        }
      }else noVideoPolls=0;
      el('quality-telemetry').textContent=parts.length?parts.join(' · '):'Reproduzindo; o mpv ainda não informou métricas.';
    });
  }
  function stopQualityPolling(){
    if(qualityTimer){clearInterval(qualityTimer);qualityTimer=null;}
    el('quality-telemetry').textContent='Nenhum vídeo em reprodução no mpv.';
  }
  function nativePlay(payload,title,fallback,decode,silent,originalRequest) {
    decode=decode||'default';
    if(!silent)autoCompatibleAttempted=decode==='compatible';
    lastNativeRequest={payload:Object.assign({},payload),title:title,decode:decode};
    noVideoPolls=0;
    if (!nativeAvailable) {
      if(fallback){fallback();return;}
      if(silent){
        lastNativeRequest=originalRequest||lastNativeRequest;
        smartNotice.textContent='Não foi possível iniciar o modo compatível automático; tente a opção manual.';
        el('quality-telemetry').textContent='Player mpv indisponível para a tentativa automática.';
        return;
      }
      dialog(title,'Player mpv indisponível. Na imagem Linux KTV OS o mpv já vem instalado. Para testar no Windows, instale o mpv e reinicie o KTV OS.');
      return;
    }
    stopQualityPolling();
    // Only validated references (kind/id/index), never signed Pluto URLs.
    payload.quality=el('quality-profile').value;
    payload.decode=decode;
    // Preliminary metadata check; never promise playback without decoding.
    function doPlay(){
      post('/api/player/play',payload,function(err){
        if(err){
          if(silent){
            lastNativeRequest=originalRequest||lastNativeRequest;
            compatibleButton.hidden=!lastNativeRequest||lastNativeRequest.decode==='compatible';
            smartNotice.textContent='A tentativa automática de modo compatível falhou. Você pode tentar novamente pelo botão.';
            el('quality-telemetry').textContent='Não foi possível ativar a decodificação compatível automaticamente.';
            if(!qualityTimer)qualityTimer=setInterval(refreshQuality,2500);
          }else dialog(title,'Não foi possível iniciar o player: '+err.message+'. Tente atualizar a lista ou usar o modo compatível.');
          return;
        }
        nativeActive=true;
        refreshQuality();
        if(!qualityTimer)qualityTimer=setInterval(refreshQuality,2500);
        if(silent){
          smartNotice.textContent='Modo compatível ativado automaticamente após detectar áudio sem vídeo.';
          el('quality-telemetry').textContent='Modo compatível ativo; verificando saída de vídeo e estabilidade…';
          if(!overlay.hidden)el('dialog-message').textContent=
            'O KTV OS detectou áudio sem vídeo e ativou a decodificação compatível. Este modo pode usar mais CPU.';
        }else{
          dialog(title,'Reproduzindo pelo mpv nativo ('+(decode==='compatible'?'modo compatível — mais CPU':'modo normal')+').\nSe houver áudio sem vídeo, pressione Q para fechar o mpv e selecione Tentar modo compatível.');
        }
      });
    }
    if(silent || ['public','pluto','community'].indexOf(payload.kind)<0){doPlay();return;}
    el('quality-telemetry').textContent='Verificando a disponibilidade do canal…';
    get('/api/channels/check?kind='+encodeURIComponent(payload.kind)+'&id='+encodeURIComponent(payload.id),function(checkError,check){
      if(!checkError&&check.status==='unavailable'){
        dialog(title,'Este canal respondeu como indisponível na verificação prévia. Atualize a lista e tente outro canal.');
        return;
      }
      // HEAD checks can fail on streams that play normally: don't block unknown.
      doPlay();
    });


  }
  compatibleButton.addEventListener('click',function(){
    if(!lastNativeRequest)return;
    var previous=lastNativeRequest;
    nativePlay(Object.assign({},previous.payload),previous.title,null,'compatible');
  });

  el('browser-search-form').addEventListener('submit',function(event){
    event.preventDefault();
    var query=el('browser-search-input').value.trim();
    post('/api/browser/search',{query:query},function(err){
      el('browser-search-result').textContent=err?'Não foi possível abrir: '+err.message:
        'Pesquisa aberta no Chromium. Alt+Tab retorna ao KTV OS; Alt+F4 fecha a janela.';
    });
  });

  el('m3u-import-form').addEventListener('submit',function(event){
    event.preventDefault();
    var content=el('m3u-import-text').value;
    if(!window.confirm('Importar canais da playlist que você possui autorização para assistir?'))return;
    post('/api/channels/import-m3u',{content:content},function(err,data){
      if(err){statusMsg('m3u-import-result','Falha ao importar: '+err.message);return;}
      channelCache=data.channels;
      channelVisible=36;
      renderChannels();
      el('m3u-import-text').value='';
      statusMsg('m3u-import-result',data.added+' canais adicionados; '+data.ignored+' ignorados (duplicados, inválidos ou limite atingido).');
    });
  });

  function webMedia(item,source,device) {
    var src=(source==='usb'?'/media/usb/'+encodeURIComponent(device)+'/':'/media/')+encodeURIComponent(item.name);
    if(item.type==='image') {
      dialog(item.name,'Visualizando imagem local.');
      image.src=src;image.hidden=false;
    } else {
      dialog(item.name,'Reprodução pelo navegador.');
      video.src=src;video.hidden=false;
      video.play().catch(function(){el('dialog-message').textContent='Pressione Play para iniciar esta mídia.';});
    }
  }
  function playItem(item,source,device) {
    if(item.type==='image'){webMedia(item,source,device);return;}
    var payload={kind:source==='usb'?'usb':'media',name:item.name};
    if(source==='usb')payload.device=device;
    nativePlay(payload,item.name,function(){webMedia(item,source,device);});
  }
  function loadMedia(source,device,label) {
    var url='/api/media'+(source==='usb'?'?source=usb&device='+encodeURIComponent(device):'');
    el('media-heading').textContent=label||'Minha biblioteca';
    get(url,function(err,data){
      var box=el('media');box.textContent='';
      if(err){message(box,'Falha ao carregar mídias: '+err.message);return;}
      if(!data.items.length){
        message(box,source==='usb'?'Nenhum vídeo, áudio ou imagem na raiz deste pendrive.':'Nenhum arquivo configurado. No PC, utilize --media-dir "PASTA" para autorizar uma biblioteca local.');
        return;
      }
      data.items.forEach(function(item){
        box.appendChild(makeCard(item.name,item.type+' · '+(item.bytes/1048576).toFixed(1)+' MB',function(){playItem(item,source,device);}));
      });
    });
  }
  function loadUSB() {
    get('/api/devices',function(err,data){
      var box=el('devices');box.textContent='';
      if(err){box.textContent='Falha ao identificar unidades. '+err.message;return;}
      if(!data.devices.length){box.textContent='Nenhum pendrive montado no computador. Conecte-o ao PC e use a seção Atualizar USB.';return;}
      data.devices.forEach(function(d){
        box.appendChild(makeCard(d.label,'Abrir mídias deste dispositivo',function(){loadMedia('usb',d.id,d.label);}));
      });
      box.classList.add('content-grid');
    });
    loadMedia('local',null,'Minha biblioteca');
  }
  var channelCache = [];
  var channelVisible = 36;
  var selectedChannelId = null;
  var channelForm = el('channel-form');
  function statusMsg(id, msg) {
    el(id).textContent = msg;
  }
  function channelEditor(channel) {
    selectedChannelId = channel ? channel.id : null;
    el('channel-editor').hidden = false;
    el('channel-editor-title').textContent = channel ? 'Editar canal' : 'Novo canal';
    el('channel-id').value = channel ? channel.id : '';
    el('channel-name').value = channel ? channel.name : '';
    el('channel-url').value = channel ? channel.url : '';
    el('channel-category').value = channel ? channel.category : '';
    statusMsg('channel-result','');
    el('channel-name').focus();
  }
  function closeEditor() {
    selectedChannelId = null;
    el('channel-editor').hidden = true;
    el('channel-create').focus();
  }
  el('channel-create').addEventListener('click',function(){channelEditor(null);});
  el('channel-cancel').addEventListener('click',closeEditor);
  channelForm.addEventListener('submit',function(event){
    event.preventDefault();
    var payload = {
      action:selectedChannelId?'edit':'add',
      id:selectedChannelId,
      name:el('channel-name').value.trim(),
      url:el('channel-url').value.trim(),
      category:el('channel-category').value.trim()
    };
    post('/api/channels/change',payload,function(err,data){
      if(err){statusMsg('channel-result','Falha: '+err.message);return;}
      closeEditor();
      channelCache=data.channels;
      renderChannels();
      statusMsg('channel-result','Canal salvo com sucesso.');
    });
  });
  function channelAction(action,item){
    if(action==='edit'){channelEditor(item);return;}
    if(action==='delete'&&!window.confirm('Excluir o canal "'+item.name+'"?'))return;
    post('/api/channels/change',{action:action,id:item.id},function(err,data){
      if(err){statusMsg('channel-result','Falha: '+err.message);return;}
      channelCache=data.channels;
      renderChannels();
      statusMsg('channel-result','Lista atualizada.');
    });
  }
  function miniButton(label,handler,isPlay){
    var button=document.createElement('button');
    button.type='button';button.className='focusable'+(isPlay?' play':'');
    button.textContent=label;button.addEventListener('click',handler);return button;
  }
  function playChannel(c,index){
    nativePlay({kind:'channel',index:index},c.name,function(){
      if (/\.(mp4|webm|m4v)(?:\?|$)/i.test(c.url)) {
        dialog(c.name,'Mídia MP4/WebM/M4V pelo navegador; reprodução depende dos codecs.');
        video.src=c.url;video.hidden=false;video.play().catch(function(){});
      } else {
        dialog(c.name,'HLS exige o player mpv, incluído na ISO Linux KTV OS. Não foi iniciado.');
      }
    });
  }
  function renderChannels(){
    var box=el('channels');box.textContent='';
    var favoriteCount=channelCache.filter(function(x){return x.favorite;}).length;
    el('channel-count').textContent=channelCache.length+' canais · '+favoriteCount+' favoritos';
    if(!channelCache.length){message(box,'Nenhum canal cadastrado. Escolha “Adicionar canal” para começar.');return;}
    // Preserve original indexes for player API while displaying favorites first.
    var sorted=channelCache.map(function(c,index){return {item:c,index:index};});
    sorted.sort(function(a,b){return Number(b.item.favorite)-Number(a.item.favorite)||a.index-b.index;});
    sorted.slice(0,channelVisible).forEach(function(entry){
      var item=entry.item;
      var card=document.createElement('div');card.className='info-card channel-card';
      var icon=document.createElement('span');icon.className='card-icon';icon.textContent='▷';
      var title=document.createElement('strong');title.className='channel-title';title.textContent=item.name;
      var category=document.createElement('small');category.className='channel-subtitle';category.textContent=item.category||'Canal personalizado';
      var buttons=document.createElement('div');buttons.className='channel-buttons';
      buttons.appendChild(miniButton('▶ Assistir',function(){playChannel(item,entry.index);},true));
      buttons.appendChild(miniButton(item.favorite?'★ Favorito':'☆ Favoritar',function(){channelAction('favorite',item);}));
      buttons.appendChild(miniButton('Editar',function(){channelAction('edit',item);}));
      buttons.appendChild(miniButton('↑',function(){channelAction('up',item);}));
      buttons.appendChild(miniButton('↓',function(){channelAction('down',item);}));
      buttons.appendChild(miniButton('Excluir',function(){channelAction('delete',item);}));
      card.appendChild(icon);card.appendChild(title);card.appendChild(category);card.appendChild(buttons);box.appendChild(card);
    });
    el('channels-more').hidden=channelVisible>=sorted.length;
  }
  el('channels-more').addEventListener('click',function(){channelVisible+=36;renderChannels();});

  // One XMLTV fetch per source, not one fetch per channel/card.
  var epgData={},epgBusy={};
  function guideKey(text){
    return (text||'').toLocaleLowerCase('pt-BR').normalize('NFKD')
      .replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9]/g,'').slice(0,110);
  }
  function guideText(program,prefix){
    if(!program||!program.title)return prefix+': sem informação';
    var time=new Date(program.start);
    var clock=isNaN(time.getTime())?'':time.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
    return prefix+': '+(clock?clock+' · ':'')+program.title;
  }
  function renderGuides(kind){
    document.querySelectorAll('[data-guide-kind="'+kind+'"]').forEach(function(node){
      var source=epgData[kind],item=source &&
        (source[guideKey(node.getAttribute('data-guide-id'))]||
         source[guideKey(node.getAttribute('data-guide-name'))]);
      node.textContent=item?
        guideText(item.now,'Agora')+' | '+guideText(item.next,'A seguir'):
        'Agora / A seguir: programação não fornecida para este canal.';
    });
  }
  function ensureGuide(kind){
    if(epgBusy[kind]||epgData[kind]){if(epgData[kind])renderGuides(kind);return;}
    epgBusy[kind]=true;
    get('/api/epg/list?kind='+encodeURIComponent(kind),function(err,response){
      epgBusy[kind]=false;
      epgData[kind]=err?{}:(response.programmes||{});
      renderGuides(kind);
    });
  }
  function attachGuide(card,kind,id,name){
    var status=document.createElement('small');
    status.className='channel-epg';status.setAttribute('data-guide-kind',kind);
    status.setAttribute('data-guide-id',id||'');status.setAttribute('data-guide-name',name||'');
    status.textContent='Agora / A seguir: consultando guia…';
    card.appendChild(status);
    ensureGuide(kind);
  }
  // Broadcast TV is received over a local USB tuner, never via a website.
  var antennaTimer=null,antennaBusy=false;
  function renderAntenna(state){
    antennaGuideChannels=(state.channels||[]).slice();
    if(reidosGuide)renderReidosGuide();
    var container=el('antenna-channels');container.textContent='';
    el('antenna-scan-indicator').textContent=state.scan_state==='running'?'Buscando…':
      state.tuner_found?'Receptor conectado':'Sem receptor';
    el('antenna-scan').disabled=state.scan_state==='running'||!state.available;
    var help=state.scan_error||state.message||'Conecte o sintonizador USB ISDB-Tb.';
    if(state.scan_state==='running')help='Buscando emissoras disponíveis pelo sinal de antena. Aguarde; isso pode durar alguns minutos.';
    if(state.scan_state==='ready')help=(state.channels||[]).length+' canais encontrados. Selecione Assistir.';
    el('antenna-message').textContent=help;
    (state.channels||[]).forEach(function(channel){
      var card=document.createElement('div');card.className='info-card channel-card';
      var icon=document.createElement('span');icon.className='card-icon';icon.textContent='📡';
      var name=document.createElement('strong');name.textContent=channel.name;
      var info=document.createElement('small');info.textContent='TV aberta por antena • sem internet';
      var controls=document.createElement('div');controls.className='channel-buttons';
      controls.appendChild(miniButton('▶ Assistir',function(){
        nativePlay({kind:'antenna',index:channel.id},channel.name,null);
      },true));
      card.appendChild(icon);card.appendChild(name);card.appendChild(info);
      card.appendChild(controls);container.appendChild(card);
    });
    if(!(state.channels||[]).length)
      message(container,state.tuner_found?'Nenhum canal salvo. Clique em Buscar canais.':
        'É necessário um sintonizador USB ISDB-Tb suportado pelo Linux para receber o sinal da antena.');
    if(antennaTimer){clearTimeout(antennaTimer);antennaTimer=null;}
    if(state.scan_state==='running'){
      antennaTimer=setTimeout(function(){loadAntenna();},2500);
    }
  }
  function loadAntenna(){
    if(antennaBusy)return;
    antennaBusy=true;
    get('/api/tv/antenna',function(err,data){
      antennaBusy=false;
      if(err){el('antenna-message').textContent='Falha ao consultar receptor: '+err.message;return;}
      renderAntenna(data.antenna);
    });
  }
  el('antenna-scan').addEventListener('click',function(){
    if(!window.confirm('Buscar canais digitais ISDB-Tb na antena conectada ao receptor USB? Pode durar até 12 minutos.'))return;
    post('/api/tv/antenna/scan',{},function(err,data){
      if(err){el('antenna-message').textContent='Não foi possível iniciar a busca: '+err.message;return;}
      renderAntenna(data.antenna);
    });
  });
  el('antenna-refresh').addEventListener('click',loadAntenna);

  function loadOpenTV(){
    get('/api/tv-aberta',function(err,data){
      var container=el('tv-aberta-player-channels');container.textContent='';
      if(err){message(container,'Canais diretos temporariamente indisponíveis.');return;}
      (data.channels||[]).forEach(function(c){
        var card=document.createElement('div');card.className='info-card channel-card';
        var title=document.createElement('strong');title.textContent=c.name;
        var subtitle=document.createElement('small');subtitle.textContent='Reprodução dentro do KTV OS · transmissão pública';
        var controls=document.createElement('div');controls.className='channel-buttons';
        controls.appendChild(miniButton('▶ Assistir no KTV',function(){
          nativePlay({kind:'public',id:c.id},c.name,null);
        },true));
        if(c.embed_available){
          controls.appendChild(miniButton('▣ Player da emissora',function(){
            openSmartEmbed('public',c.id,c.name);
          }));
        }
        card.appendChild(title);card.appendChild(subtitle);card.appendChild(controls);
        attachGuide(card,'br',c.id,c.name);
        container.appendChild(card);
      });
    });
  }


  // Read-only broadcaster schedule from Rei dos Canais. The API's 'embeds'
  // are intentionally discarded by the server; no unreviewed stream executes.
  var reidosGuide=null;
  var antennaGuideChannels=[];
  function guideClock(seconds){
    if(typeFinite(seconds))return new Date(seconds*1000).toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'});
    return '';
  }
  function typeFinite(value){return typeof value==='number'&&isFinite(value);}
  function normalizedAntenna(text){
    return (text||'').toLocaleLowerCase('pt-BR').normalize('NFKD')
      .replace(/[\u0300-\u036f]/g,'').replace(/[^a-z0-9 ]/g,' ')
      .replace(/\s+/g,' ').trim();
  }
  function tunerForGuide(name){
    var aliases={
      'globo':/^(tv )?globo( (hd|sp|rj|df))?$/,
      'band':/^(tv )?band( hd)?$/,
      'record':/^(tv )?record( tv)?( hd)?$/,
      'sbt':/^sbt( hd)?$/,
      'redetv':/^rede ?tv( hd)?$/,
      'tv-brasil':/^tv brasil( hd)?$/,
      'tv-cultura':/^tv cultura( hd)?$/,
      'tv-aparecida':/^tv aparecida( hd)?$/
    };
    var pattern=aliases[name];
    if(!pattern)return null;
    for(var i=0;i<antennaGuideChannels.length;i++){
      if(pattern.test(normalizedAntenna(antennaGuideChannels[i].name)))return antennaGuideChannels[i];
    }
    return null;
  }
  function renderReidosGuide(){
    var box=el('reidos-guide-channels');box.textContent='';
    var rows=(reidosGuide&&reidosGuide.channels)||[];
    el('reidos-count').textContent=rows.length+' emissoras identificadas';
    if(!rows.length){
      message(box,'Nenhuma programação complementar disponível no momento.');
      return;
    }
    rows.forEach(function(c){
      var card=document.createElement('div');card.className='info-card channel-card';
      var title=document.createElement('strong');title.textContent=c.name;
      var details=document.createElement('small');details.className='channel-epg';
      var now=c.now, next=c.next;
      details.textContent=(now?'Agora: '+guideClock(now.start)+' · '+now.title:'Agora: sem dados atuais')+
        ' | '+(next?'A seguir: '+guideClock(next.start)+' · '+next.title:'A seguir: sem dados');
      var controls=document.createElement('div');controls.className='channel-buttons';
      var tuner=tunerForGuide(c.id);
      if(tuner){
        controls.appendChild(miniButton('▶ Assistir pela antena',function(){
          nativePlay({kind:'antenna',index:tuner.id},c.name,null);
        },true));
      }else if(c.play_id==='tv-brasil'||c.play_id==='tv-cultura'){
        controls.appendChild(miniButton('▶ Assistir no KTV',function(){
          nativePlay({kind:'public',id:c.play_id},c.name,null);
        },true));
      }else{
        var notice=document.createElement('small');
        notice.textContent='Reprodução: busque o canal na antena. O site consultado não é fonte de vídeo autorizada.';
        card.appendChild(notice);
      }
      card.appendChild(title);card.appendChild(details);card.appendChild(controls);
      box.appendChild(card);
    });
  }
  function loadReidosGuide(force){
    if(reidosGuide&&!force){renderReidosGuide();return;}
    el('reidos-status').textContent='Consultando programação da TV aberta…';
    get('/api/guide/reidos/aberta',function(err,data){
      if(err){
        el('reidos-status').textContent='API externa indisponível. Canais existentes continuam funcionando.';
        if(!reidosGuide)renderReidosGuide();
        return;
      }
      reidosGuide=data;
      el('reidos-status').textContent='Guia complementar (somente informação). A exibição não confirma direitos de retransmissão nem disponibilidade do vídeo.';
      renderReidosGuide();
    });
  }
  el('reidos-refresh').addEventListener('click',function(){loadReidosGuide(true);});

  // Curated public institutions only; no untrusted third-party IPTV aggregator.
  var publicChannelCache=[];
  function renderPublicChannels(){
    var container=el('public-channels'),filter=el('public-channel-filter').value;
    container.textContent='';
    var selected=publicChannelCache.filter(function(c){
      return filter==='all'||(Array.isArray(c.genres)&&c.genres.indexOf(filter)!==-1);
    });
    if(!selected.length){
      message(container,filter==='Animes'
        ?'Ainda não há um stream direto de anime cuja origem e autorização tenhamos confirmado. Não incluímos IPTV pirata.'
        :'Ainda não temos canais verificados nesta categoria. Os assuntos representam parte da programação, que varia conforme o horário.');
      return;
    }
    selected.forEach(function(c){
      var card=document.createElement('div');card.className='info-card channel-card';
      var icon=document.createElement('span');icon.className='card-icon';icon.textContent='◉';
      var title=document.createElement('strong');title.textContent=c.name;
      var label=document.createElement('small');
      label.textContent=c.provider+' · '+(c.category||'TV pública')+' · link experimental';
      var info=document.createElement('small');
      info.textContent=c.note||'A programação pode variar.';
      var controls=document.createElement('div');controls.className='channel-buttons';
      controls.appendChild(miniButton('▶ Assistir',function(){
        nativePlay({kind:'public',id:c.id},c.name,function(){
          dialog(c.name,'Este canal usa HLS. Instale e utilize o KTV OS Linux Live com mpv para reproduzir. O link pode estar indisponível.');
        });
      },true));
      if(c.id==='tv-brasil'||c.id==='tv-cultura'){
        controls.appendChild(miniButton('▣ Player integrado',function(){
          openSmartEmbed('public',c.id,c.name);
        }));
      }
      controls.appendChild(miniButton('Adicionar aos meus canais',function(){
        post('/api/channels/change',{action:'add',name:c.name,url:c.url,category:c.category},function(fault,response){
          statusMsg('channel-result',fault?'Falha ao adicionar: '+fault.message:'Canal adicionado à sua lista pessoal.');
          if(!fault){channelCache=response.channels;renderChannels();}
        });
      }));
      card.appendChild(icon);card.appendChild(title);card.appendChild(label);card.appendChild(info);card.appendChild(controls);
      attachGuide(card,'br',c.id,c.name);container.appendChild(card);
    });
  }
  function loadPublicChannels(){
    get('/api/public-channels',function(err,data){
      if(err){message(el('public-channels'),'Catálogo indisponível: '+err.message);return;}
      publicChannelCache=(data.channels||[]);
      renderPublicChannels();
    });
  }
  el('public-channel-filter').addEventListener('change',renderPublicChannels);

  // User-supplied Pluto TV catalog is fetched only on demand. Never expose signed URLs.
  // Additional public GitHub indexes, strictly checked by server allowlist.
  var communityChannels=[],communityLoaded=false,communityBusy=false,communityVisible=36;
  function renderCommunityChannels(){
    var filter=el('community-category').value;
    var query=el('community-search').value.toLocaleLowerCase('pt-BR').trim();
    var results=communityChannels.filter(function(c){
      return (filter==='all'||c.category===filter) &&
        (!query||(c.name+' '+c.category+' '+c.provider).toLocaleLowerCase('pt-BR').indexOf(query)!==-1);
    });
    el('community-count').textContent=results.length+' de '+communityChannels.length+' canais';
    var container=el('community-channels');container.textContent='';
    if(!results.length)message(container,communityLoaded?'Nenhum canal encontrado.':'Carregue o catálogo para explorar.');
    results.slice(0,communityVisible).forEach(function(c){
      var card=document.createElement('div');card.className='info-card channel-card';
      var icon=document.createElement('span');icon.className='card-icon';icon.textContent='◎';
      var name=document.createElement('strong');name.textContent=c.name;
      var subtitle=document.createElement('small');subtitle.textContent=c.category+' · '+c.provider;
      var controls=document.createElement('div');controls.className='channel-buttons';
      controls.appendChild(miniButton('▶ Assistir',function(){
        nativePlay({kind:'community',id:c.id},c.name,function(){
          dialog(c.name,'O player nativo mpv é necessário para esta transmissão HLS.');
        });
      },true));
      card.appendChild(icon);card.appendChild(name);card.appendChild(subtitle);
      card.appendChild(controls);attachGuide(card,'br',c.id,c.name);container.appendChild(card);
    });
    el('community-more').hidden=communityVisible>=results.length;
  }
  function loadCommunityChannels(force){
    if(communityBusy||(communityLoaded&&!force))return;
    communityBusy=true;
    el('community-status').textContent='Atualizando listas públicas do GitHub...';
    get('/api/community/channels',function(err,data){
      communityBusy=false;
      if(err){el('community-status').textContent='Listas temporariamente indisponíveis. Verifique a internet ou tente novamente.';return;}
      communityChannels=data.channels||[];
      communityLoaded=true;
      communityVisible=36;
      var options=el('community-category'),prior=options.value,categories=[];
      options.textContent='';
      var all=document.createElement('option');all.value='all';all.textContent='Todas';options.appendChild(all);
      communityChannels.forEach(function(c){if(categories.indexOf(c.category)===-1)categories.push(c.category);});
      categories.sort(function(a,b){return a.localeCompare(b,'pt-BR');});
      categories.forEach(function(cat){var option=document.createElement('option');option.value=cat;option.textContent=cat;options.appendChild(option);});
      if(categories.indexOf(prior)!==-1)options.value=prior;
      el('community-status').textContent=(data.partial?'Fonte parcialmente disponível. ':'')+
        communityChannels.length+' canais aprovados pelo filtro técnico de origem; disponibilidade não garantida.';
      renderCommunityChannels();
    });
  }
  el('community-category').addEventListener('change',function(){communityVisible=36;renderCommunityChannels();});
  el('community-search').addEventListener('input',function(){communityVisible=36;renderCommunityChannels();});
  el('community-refresh').addEventListener('click',function(){loadCommunityChannels(true);});
  el('community-more').addEventListener('click',function(){communityVisible+=36;renderCommunityChannels();});

  el('browser-open-green').addEventListener('click',function(){
    post('/api/browser/home',{},function(err){
      el('browser-search-result').textContent=err?'Falha: '+err.message:
        'Navegador KTV Verde aberto. Use Alt+Tab para alternar entre as janelas.';
    });
  });
  el('browser-system-keyboard').addEventListener('click',function(){
    post('/api/input/virtual-toggle',{},function(err,data){
      el('browser-keyboard-status').textContent=err?'Não foi possível abrir: '+err.message:
        (data.input.virtual_open?'Teclado de sistema aberto.':'Teclado de sistema fechado.');
    });
  });

  var plutoChannels = [];
  var plutoFavorites = [];
  function loadPlutoFavorites(){
    get('/api/pluto/favorites',function(err,data){
      if(err)return;
      plutoFavorites=Array.isArray(data.ids)?data.ids:[];
      if(plutoLoaded)renderPlutoChannels();
    });
  }
  var plutoLoaded = false;
  var plutoPageSize = 36;
  var plutoVisible = plutoPageSize;
  var plutoPending = false;
  function renderPlutoChannels(){
    var filter = el('pluto-category').value;
    var query = el('pluto-search').value.toLocaleLowerCase('pt-BR').trim();
    var selected = plutoChannels.filter(function(c){
      return (filter==='all'||(filter==='favorites'&&plutoFavorites.indexOf(c.id)!==-1)||c.category===filter) &&
        (!query || (c.name+' '+c.category).toLocaleLowerCase('pt-BR').indexOf(query)!==-1);
    });
    selected.sort(function(a,b){return Number(plutoFavorites.indexOf(b.id)!==-1)-Number(plutoFavorites.indexOf(a.id)!==-1);});
    var container=el('pluto-channels');
    container.textContent='';
    el('pluto-count').textContent=selected.length+' de '+plutoChannels.length+' canais · '+plutoFavorites.length+' favoritos';
    if(!selected.length){
      message(container,plutoLoaded?'Nenhum canal corresponde aos filtros.':'Catálogo ainda não carregado.');
    }
    selected.slice(0,plutoVisible).forEach(function(c){
      var card=document.createElement('div');card.className='info-card channel-card';
      var icon=document.createElement('span');icon.className='card-icon';icon.textContent='▶';
      var name=document.createElement('strong');name.textContent=c.name;
      var category=document.createElement('small');category.textContent=c.category+' · Pluto TV (lista comunitária)';
      var controls=document.createElement('div');controls.className='channel-buttons';
      controls.appendChild(miniButton('▶ Assistir',function(){
        nativePlay({kind:'pluto',id:c.id},c.name,function(){
          dialog(c.name,'Estes canais HLS exigem o mpv nativo. O endereço temporário também pode expirar.');
        });
      },true));

      var favored=plutoFavorites.indexOf(c.id)!==-1;
      controls.appendChild(miniButton(favored?'★ Favorito':'☆ Favoritar',function(){
        post('/api/pluto/favorites/toggle',{id:c.id},function(err,data){
          if(err){el('pluto-status').textContent='Não foi possível salvar favorito: '+err.message;return;}
          plutoFavorites=data.ids||[];
          renderPlutoChannels();
          if(data.persistence && data.persistence.pending)el('pluto-status').textContent='Favorito salvo na sessão. Reconecte o pendrive de persistência para sincronizar.';
        });
      }));
      card.appendChild(icon);card.appendChild(name);card.appendChild(category);
      card.appendChild(controls);attachGuide(card,'pluto',c.id,c.name);container.appendChild(card);
    });
    el('pluto-more').hidden=plutoVisible>=selected.length;
  }
  function loadPlutoChannels(force){
    if(plutoPending || (plutoLoaded && !force))return;
    plutoPending=true;
    el('pluto-status').textContent='Carregando catálogo remoto da Pluto TV…';
    get('/api/pluto/channels',function(err,data){
      plutoPending=false;
      if(err){
        el('pluto-status').textContent='Não foi possível atualizar a playlist agora. Confira a conexão com a internet e tente novamente.';
        if(!plutoLoaded)message(el('pluto-channels'),'Catálogo indisponível.');
        return;
      }
      plutoChannels=(data.channels||[]);
      plutoLoaded=true;
      plutoVisible=plutoPageSize;
      var filterEl=el('pluto-category'), before=filterEl.value;
      var categories=[];
      plutoChannels.forEach(function(c){if(categories.indexOf(c.category)===-1)categories.push(c.category);});
      categories.sort(function(a,b){return a.localeCompare(b,'pt-BR');});
      filterEl.textContent='';
      var all=document.createElement('option');all.value='all';all.textContent='Todas as categorias';filterEl.appendChild(all);
      var favoritesOption=document.createElement('option');favoritesOption.value='favorites';favoritesOption.textContent='★ Meus favoritos';filterEl.appendChild(favoritesOption);
      categories.forEach(function(c){var option=document.createElement('option');option.value=c;option.textContent=c;filterEl.appendChild(option);});
      if(before==='favorites'||categories.indexOf(before)!==-1)filterEl.value=before;
      el('pluto-status').textContent=plutoChannels.length+' canais disponíveis no catálogo. Reprodução sujeita à disponibilidade do provedor.';
      renderPlutoChannels();
    });
  }
  el('pluto-category').addEventListener('change',function(){plutoVisible=plutoPageSize;renderPlutoChannels();});
  el('pluto-search').addEventListener('input',function(){plutoVisible=plutoPageSize;renderPlutoChannels();});
  el('pluto-refresh').addEventListener('click',function(){loadPlutoChannels(true);});
  el('pluto-more').addEventListener('click',function(){plutoVisible+=plutoPageSize;renderPlutoChannels();});

  function refreshNetwork(){
    get('/api/network/status',function(err,data){
      if(err){el('network-status').textContent='Servidor de rede indisponível: '+err.message;return;}
      var n=data.network;
      el('network-status').textContent=n.available?('Wi-Fi: '+(n.wifi_enabled?'ativado':'desativado')):('Rede indisponível: '+n.error);
      var root=el('network-devices');root.textContent='';
      (n.devices||[]).forEach(function(d){
        root.appendChild(makeCard(d.kind==='ethernet'?'Ethernet':'Wi-Fi',d.name+' · '+d.state+' · '+(d.connection||'sem conexão'),function(){}));
      });
    });
  }
  function scanNetwork(){
    el('wifi-feedback').textContent='Buscando redes…';
    get('/api/network/wifi',function(err,data){
      if(err){el('wifi-feedback').textContent='Erro na busca: '+err.message;return;}
      var choices=el('wifi-ssid'),saved=choices.value;
      choices.textContent='';
      (data.networks||[]).forEach(function(n){
        var option=document.createElement('option');option.value=n.ssid;
        option.textContent=n.ssid+' · '+n.signal+'%'+(n.secure?' 🔒':'')+(n.connected?' ✓ conectado':'');
        choices.appendChild(option);
      });
      if((data.networks||[]).some(function(n){return n.ssid===saved;}))choices.value=saved;
      el('wifi-feedback').textContent=data.networks.length+' rede(s) encontrada(s).';
      refreshNetwork();
    });
  }
  el('wifi-scan').addEventListener('click',scanNetwork);
  el('network-refresh').addEventListener('click',refreshNetwork);
  el('wifi-enable').addEventListener('click',function(){
    post('/api/network/wifi-radio',{enabled:true},function(err,data){
      el('wifi-feedback').textContent=err?('Falha ao ativar Wi-Fi: '+err.message):data.result.message;
      if(!err)scanNetwork();
    });
  });
  el('wifi-connect').addEventListener('click',function(){
    var ssid=el('wifi-ssid').value;
    if(!ssid){el('wifi-feedback').textContent='Primeiro selecione uma rede Wi-Fi.';return;}
    el('wifi-connect').disabled=true;
    el('wifi-feedback').textContent='Tentando conectar…';
    var secret=el('wifi-password').value;
    post('/api/network/connect',{ssid:ssid,password:secret},function(err,data){
      el('wifi-password').value='';secret='';
      el('wifi-connect').disabled=false;
      el('wifi-feedback').textContent=err?('Falha na conexão: '+err.message):data.result.message;
      refreshNetwork();
    });
  });
  loadPublicChannels();

  function loadChannels(){
    get('/api/channels',function(err,data){
      if(err){message(el('channels'),'Não foi possível carregar os canais: '+err.message);return;}
      channelCache=data.channels;renderChannels();
    });
  }
  function loadBackupDevices(){
    get('/api/devices',function(err,data){
      var select=el('backup-device');
      var previous=select.value;
      select.textContent='';
      var placeholder=document.createElement('option');
      placeholder.value='';placeholder.textContent='Selecione uma unidade USB';select.appendChild(placeholder);
      if(err){statusMsg('backup-result','Falha ao consultar USB: '+err.message);return;}
      data.devices.forEach(function(device){
        var option=document.createElement('option');
        option.value=device.id;option.textContent=device.label;
        select.appendChild(option);
      });
      if(data.devices.some(function(d){return d.id===previous;}))select.value=previous;
      else if(data.devices.length)select.value=data.devices[0].id;
    });
  }
  function backupRequest(path){
    var device=el('backup-device').value;
    if(!device){statusMsg('backup-result','Conecte e escolha um pendrive no computador.');return;}
    if(path.indexOf('restore')!==-1&&!window.confirm('Restaurar backup USB? A lista atual de canais será substituída.'))return;
    post('/api/channels/usb-'+path,{device:device},function(err,data){
      if(err){statusMsg('backup-result','Falha: '+err.message);return;}
      statusMsg('backup-result',path==='backup'?'Backup salvo em '+device+'.':('Backup restaurado: '+data.channels.length+' canais.'));
      if(path==='restore'){channelCache=data.channels;renderChannels();}
    });
  }
  function renderPersistence(p) {
    var label = !p || !p.enabled ? 'Desativada' :
      (p.connected ? (p.pending ? 'USB conectado • alterações pendentes' : 'Ativa • alterações salvas') :
                     'USB removido • estado temporário');
    el('persistence-status').textContent = label;
    if(p && p.error)statusMsg('persistence-result',p.error);
  }
  function loadPersistenceStatus(){
    get('/api/persistence/status',function(err,data){
      if(err){statusMsg('persistence-result','Falha ao consultar persistência: '+err.message);return;}
      renderPersistence(data.persistence);
    });
  }
  el('persistence-enable').addEventListener('click',function(){
    var device=el('backup-device').value;
    if(!device){statusMsg('persistence-result','Selecione um pendrive de dados nas opções de backup.');return;}
    if(!window.confirm('Ativar gravação automática de canais neste pendrive? A cópia persistente anterior do KTV OS nesta unidade poderá ser substituída. Nenhum dispositivo será formatado.'))return;
    post('/api/persistence/enable',{device:device},function(err,data){
      if(err){statusMsg('persistence-result','Falha: '+err.message);return;}
      renderPersistence(data.persistence);
      statusMsg('persistence-result','Persistência ativada. Mantenha este pendrive de dados conectado nas próximas inicializações.');
    });
  });
  el('persistence-disable').addEventListener('click',function(){
    post('/api/persistence/disable',{},function(err,data){
      if(err){statusMsg('persistence-result','Falha: '+err.message);return;}
      renderPersistence(data.persistence);
      statusMsg('persistence-result','Gravação automática desligada. Os arquivos já salvos no USB foram preservados.');
    });
  });
  setInterval(function(){if(currentRoute==='config')loadPersistenceStatus();},7000);
  el('backup-refresh').addEventListener('click',loadBackupDevices);
  el('backup-save').addEventListener('click',function(){backupRequest('backup');});
  el('backup-restore').addEventListener('click',function(){backupRequest('restore');});
  get('/api/status',function(err,data){
    el('connection').textContent=err?'Servidor indisponível':'Sistema local conectado';
    if(!err){
      nativeAvailable=!!(data.player&&data.player.available);
      el('server-detail').textContent='KTV OS '+data.version+' · '+data.host+' · Player: '+(nativeAvailable?'mpv nativo pronto':'navegador (mpv não encontrado)')+' · Acesso local.';
    }
  });


  // A resolution change lasts at most 20 seconds unless explicitly confirmed.
  // Even if the browser becomes unresponsive the Linux backend timer rolls it back.
  function videoFeedback(message){el('video-feedback').textContent=message;}
  function audioFeedback(message){el('audio-feedback').textContent=message;}
  function options(id, entries, key, label){
    var element=el(id),selected=element.value;
    element.textContent='';
    entries.forEach(function(entry){
      var option=document.createElement('option');
      option.value=entry[key];option.textContent=entry[label];
      element.appendChild(option);
    });
    if(entries.some(function(entry){return entry[key]===selected;}))element.value=selected;
  }
  function refreshModes(){
    var output=discoveredDisplays.filter(function(o){return o.name===el('display-output').value;})[0];
    var modes=(output?output.modes:[]).map(function(m){return {value:m,label:m+(m===output.current?' (atual)':'')};});
    options('display-mode',modes,'value','label');
    if(output && !modes.some(function(x){return x.value===el('display-mode').value;}))el('display-mode').value=output.current||'';
  }
  function refreshHardware(){
    get('/api/hardware',function(err,data){
      if(err){videoFeedback('Falha ao consultar hardware: '+err.message);return;}
      var display=data.hardware.display,audio=data.hardware.audio;
      discoveredDisplays=display.outputs.filter(function(o){return o.hdmi;});
      options('display-output',discoveredDisplays,'name','name');
      refreshModes();
      el('display-apply').disabled=!display.available||!discoveredDisplays.length||display.pending;
      el('display-layout-apply').disabled=!display.available||!discoveredDisplays.length||display.pending;
      var connected=(display.layout||[]).filter(function(o){return !!o.mode;});
      el('display-layout-state').textContent=connected.length?
        ('Telas ativas: '+connected.map(function(o){return o.name+' '+o.mode+' ('+o.x+','+o.y+')';}).join(' • ')+'. Se os monitores estiverem lado a lado, escolha um modo HDMI acima.'):
        'Nenhuma saída de vídeo ativa identificada; confira o cabo, xrandr e o driver gráfico.';
      el('display-status').textContent=display.available?
        (discoveredDisplays.length?'Saídas HDMI/DisplayPort detectadas no computador.':'Nenhuma saída HDMI ou DisplayPort ativa. Confira o cabo e o driver Linux.'):
        ('Configuração de vídeo indisponível: '+display.error);
      options('audio-sink',audio.sinks,'name','name');
      if(audio.default && audio.sinks.some(function(x){return x.name===audio.default;}))el('audio-sink').value=audio.default;
      el('audio-status').textContent=audio.available?
        ('Saída ativa: '+(audio.default||'não identificada')+(audio.muted?' • mudo':'') ):
        ('Áudio do Linux indisponível: '+audio.error);
      if(typeof audio.volume==='number'){
        el('audio-volume').value=Math.max(0,Math.min(100,audio.volume));
        el('audio-volume-label').textContent=el('audio-volume').value+'%';
      }
      el('audio-apply').disabled=!audio.available||!audio.sinks.length;
      el('audio-set-volume').disabled=!audio.available;
      el('audio-mute').disabled=!audio.available;
    });
  }
  el('display-output').addEventListener('change',refreshModes);
  function clearVideoTimer(){
    if(pendingVideoTimer){window.clearInterval(pendingVideoTimer);pendingVideoTimer=null;}
    el('video-confirm').hidden=true;
  }
  function cancelVideoPreview(){
    if(!pendingVideoToken)return;
    pendingVideoToken=null;
    clearVideoTimer();
    post('/api/hardware/video/cancel',{},function(err){
      if(err)videoFeedback('Falha ao reverter imagem: '+err.message);
      else videoFeedback('Resolução anterior restaurada.');
      refreshHardware();
    });
  }
  function handleVideoPreview(err,data){
    if(err){videoFeedback('Não foi possível alterar as telas: '+err.message);return;}
    if(!data.result.pending){videoFeedback(data.result.message);return;}
    pendingVideoToken=data.result.token;
    var left=data.result.seconds;
    dialog('Confirmar imagem HDMI','Se a imagem está correta na televisão, selecione “Manter esta resolução”. O Linux tentará restaurar as telas depois de 20 segundos.');
    el('video-confirm').hidden=false;
    el('video-confirm').focus();
    function redraw(){
      el('dialog-message').textContent='A imagem está correta na TV? Confirme somente se você está vendo a interface.\n\nReversão automática em '+left+' segundo(s).';
    }
    redraw();
    pendingVideoTimer=window.setInterval(function(){
      left--;
      if(left<=0){
        pendingVideoToken=null;
        clearVideoTimer();
        closeDialog();
        videoFeedback('Prazo encerrado. O Linux tentou restaurar a configuração anterior das telas.');
        refreshHardware();
      }else redraw();
    },1000);
  }
  el('display-apply').addEventListener('click',function(){
    var output=el('display-output').value,mode=el('display-mode').value;
    if(!output||!mode){videoFeedback('Selecione a saída e a resolução.');return;}
    post('/api/hardware/video/preview',{output:output,mode:mode},handleVideoPreview);
  });
  el('display-layout-apply').addEventListener('click',function(){
    var output=el('display-output').value,layout=el('display-layout').value;
    if(!output){videoFeedback('Selecione uma saída HDMI ativa para testar.');return;}
    post('/api/hardware/video/layout-preview',{output:output,layout:layout},handleVideoPreview);
  });
  el('video-confirm').addEventListener('click',function(){
    var token=pendingVideoToken;
    if(!token)return;
    pendingVideoToken=null;
    clearVideoTimer();
    post('/api/hardware/video/confirm',{token:token},function(err,data){
      closeDialog();
      videoFeedback(err?'Confirmação não aplicada: '+err.message:data.result.message);
      refreshHardware();
    });
  });
  el('hardware-refresh').addEventListener('click',refreshHardware);
  el('audio-volume').addEventListener('input',function(){
    el('audio-volume-label').textContent=el('audio-volume').value+'%';
  });
  function updateAudio(path,payload){
    post(path,payload,function(err,data){
      audioFeedback(err?'Falha de áudio: '+err.message:data.result.message);
      refreshHardware();
    });
  }
  el('audio-apply').addEventListener('click',function(){
    updateAudio('/api/hardware/audio/output',{sink:el('audio-sink').value});
  });
  el('audio-set-volume').addEventListener('click',function(){
    updateAudio('/api/hardware/audio/volume',{volume:Number(el('audio-volume').value)});
  });
  el('audio-mute').addEventListener('click',function(){
    updateAudio('/api/hardware/audio/mute',{});
  });


  // Optional HDMI-CEC via libCEC. Never assume notebook HDMI handles CEC.
  var cecEnabled=false, cecSeq=0, cecBusy=false;
  function renderCEC(status) {
    cecEnabled=!!(status && status.running);
    el('cec-status').textContent=!status.supported?'libCEC indisponível':
      (status.running?'Recebendo botões CEC':status.enabled?'Inicializando adaptador':'Desativado / sem adaptador');
    if(status.error)el('cec-result').textContent=status.error;
    el('cec-enable').disabled=!status.supported||status.running;
    el('cec-disable').disabled=!status.enabled;
  }
  function refreshCEC() {
    get('/api/cec/status',function(err,data) {
      if(err){el('cec-result').textContent='Falha de diagnóstico CEC: '+err.message;return;}
      renderCEC(data.cec);
    });
  }
  el('cec-refresh').addEventListener('click',refreshCEC);
  el('cec-enable').addEventListener('click',function(){
    if(!window.confirm('Tentar receber botões da TV via HDMI-CEC? É necessário hardware CEC compatível no computador, possivelmente um adaptador USB. O libCEC pode registrar um novo dispositivo de reprodução na rede HDMI.'))return;
    post('/api/cec/enable',{},function(err,data){
      if(err){el('cec-result').textContent='Não foi possível iniciar CEC: '+err.message;refreshCEC();return;}
      cecSeq=0;
      renderCEC(data.cec);
      el('cec-result').textContent='Receptor iniciado. Pressione as setas e OK no controle. Se não houver adaptador compatível, o serviço poderá encerrar.';
    });
  });
  el('cec-disable').addEventListener('click',function(){
    post('/api/cec/disable',{},function(err,data){
      if(err){el('cec-result').textContent='Erro ao parar CEC: '+err.message;return;}
      renderCEC(data.cec);el('cec-result').textContent='CEC desativado; teclado e joystick continuam disponíveis.';
    });
  });
  function pollCEC(){
    if(!cecEnabled||cecBusy)return;
    cecBusy=true;
    get('/api/cec/events?after='+cecSeq,function(err,data){
      cecBusy=false;
      if(err)return;
      if(typeof data.last==='number')cecSeq=Math.max(cecSeq,data.last);
      (data.events||[]).forEach(function(event){
        if(['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].indexOf(event.key)!==-1)padAction(event.key);
        else if(event.key==='Enter')padAction('accept');
        else if(event.key==='Escape')padAction('back');
        else if(event.key==='Home')padAction('home');
      });
    });
  }
  setInterval(pollCEC,350);
  setInterval(function(){if(cecEnabled||currentRoute==='config')refreshCEC();},5000);

  // Gamepad API works with controllers connected to the computer, not the
  // Samsung infrared remote unless a compatible HDMI-CEC adapter is provided.
  var lastPadAction = '';
  var lastPadTime = 0;
  var lastPadConnected = false;
  function padAction(action) {
    if(action==='accept'){
      var focused=document.activeElement;
      if(focused && typeof focused.click==='function')focused.click();
      return;
    }
    if(action==='back'){
      if(!overlay.hidden)closeDialog();
      else if(currentRoute!=='inicio')route('inicio');
      return;
    }
    if(action==='home'){route('inicio');return;}
    document.dispatchEvent(new KeyboardEvent('keydown',{key:action,bubbles:true,cancelable:true}));
  }
  function gamepadPoll(timestamp) {
    if(typeof navigator.getGamepads==='function'){
      var pads=navigator.getGamepads();
      var pad=null;
      for(var i=0;i<pads.length;i++){if(pads[i]&&pads[i].connected){pad=pads[i];break;}}
      if(!!pad!==lastPadConnected){
        lastPadConnected=!!pad;
        el('gamepad-status').textContent=pad?'🎮 Conectado':'';
      }
      if(pad){
        var b=pad.buttons||[], axes=pad.axes||[];
        function pressed(n){return b[n]&&b[n].pressed;}
        var action='';
        if(pressed(0))action='accept';
        else if(pressed(1))action='back';
        else if(pressed(9))action='home';
        else if(pressed(12)||(axes[1]!==undefined&&axes[1]<-0.65))action='ArrowUp';
        else if(pressed(13)||(axes[1]!==undefined&&axes[1]>0.65))action='ArrowDown';
        else if(pressed(14)||(axes[0]!==undefined&&axes[0]<-0.65))action='ArrowLeft';
        else if(pressed(15)||(axes[0]!==undefined&&axes[0]>0.65))action='ArrowRight';
        if(action && (action!==lastPadAction||timestamp-lastPadTime>240)){
          padAction(action);
          lastPadTime=timestamp;
        }
        lastPadAction=action;
      }else lastPadAction='';
    }
    window.requestAnimationFrame(gamepadPoll);
  }
  if(window.requestAnimationFrame)window.requestAnimationFrame(gamepadPoll);
  loadChannels(); loadUSB();
  document.querySelector('.nav-link.active').focus();
})();