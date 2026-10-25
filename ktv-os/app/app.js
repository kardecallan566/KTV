(function () {
  'use strict';
  var currentRoute = 'inicio';
  var overlay = document.getElementById('dialog-overlay');
  var dialogClose = document.getElementById('dialog-close');
  var video = document.getElementById('video-player');
  var image = document.getElementById('image-player');
  var playerStop = document.getElementById('player-stop');
  var nativeAvailable = false;
  var nativeActive = false;
  var pendingVideoToken = null;
  var pendingVideoTimer = null;
  var discoveredDisplays = [];
  function el(id) { return document.getElementById(id); }
  function clock() {
    el('clock').textContent = new Date().toLocaleTimeString('pt-BR', {hour:'2-digit', minute:'2-digit'});
  }
  clock(); setInterval(clock, 20000);
  function dialog(title, body) {
    el('dialog-title').textContent = title;
    el('dialog-message').textContent = body;
    overlay.hidden = false; playerStop.hidden = !nativeActive; dialogClose.focus();
  }
  function closeDialog() {
    if (overlay.hidden) return;
    if (pendingVideoToken) cancelVideoPreview();
    video.pause(); video.removeAttribute('src'); video.load(); video.hidden = true;
    image.removeAttribute('src'); image.hidden = true; overlay.hidden = true;
    if (nativeActive) stopNative();
    playerStop.hidden = true;
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
    if (name === 'canais') {loadChannels();loadPublicChannels();}
    if (name === 'config') {loadBackupDevices();loadPersistenceStatus();refreshCEC();}
    if (name === 'hardware') refreshHardware();
  }
  function activate(button) {
    var r = button.getAttribute('data-route'), a = button.getAttribute('data-action');
    if (r) { route(r); return; }
    if (a === 'tv-aberta') {
      dialog('TV aberta', 'A antena continua conectada à Samsung. Pressione SOURCE no controle da TV e selecione TV / Antena.\n\nPara usar canais abertos dentro do KTV OS precisaremos, futuramente, de um sintonizador ISDB-Tb compatível conectado ao computador.');
    } else if (a === 'sources') {
      dialog('Entradas HDMI', 'As portas HDMI pertencem à Samsung. Para alternar, use SOURCE no controle da televisão.\n\nO HDMI-CEC experimental recebe botões quando existe um adaptador CEC compatível, mas ainda não alterna as entradas da Samsung.');
    } else if (a === 'refresh-usb') {
      loadUSB();
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
    var typing = e.target && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
    if (typing && e.key !== 'Escape') return;
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
  function post(path, payload, done) {
    fetch(path, {method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)}).then(function(resp){return resp.json().then(function(data){
        if(!resp.ok)throw new Error(data.error||('HTTP '+resp.status));
        return data;
      });}).then(function(data){done(null,data);}).catch(function(error){done(error);});
  }
  function stopNative() {
    nativeActive = false;
    playerStop.hidden = true;
    post('/api/player/stop', {}, function(){});
  }
  playerStop.addEventListener('click', function(){stopNative();el('dialog-message').textContent='Reprodução encerrada. Pressione Voltar.';});
  function nativePlay(payload,title,fallback) {
    if (!nativeAvailable) {
      if(fallback){fallback();return;}
      dialog(title,'Player mpv indisponível. Na imagem Linux KTV OS o mpv já vem instalado. Para testar no Windows, instale o mpv e reinicie o KTV OS.');
      return;
    }
    post('/api/player/play',payload,function(err){
      if(err){dialog(title,'Não foi possível iniciar o player: '+err.message);return;}
      nativeActive=true;
      dialog(title,'Reproduzindo pelo mpv nativo em tela cheia.\nUse Q para fechar a janela do mpv e voltar à interface do KTV OS.');
    });
  }
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
      if (/\.mp4(?:\?|$)/i.test(c.url)) {
        dialog(c.name,'MP4 pelo navegador; compatibilidade depende dos codecs.');
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
    sorted.forEach(function(entry){
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
  }

  // Curated public institutions only; no untrusted third-party IPTV aggregator.
  function loadPublicChannels(){
    get('/api/public-channels',function(err,data){
      var container=el('public-channels');container.textContent='';
      if(err){message(container,'Catálogo indisponível: '+err.message);return;}
      (data.channels||[]).forEach(function(c){
        var card=document.createElement('div');card.className='info-card channel-card';
        var icon=document.createElement('span');icon.className='card-icon';icon.textContent='◉';
        var title=document.createElement('strong');title.textContent=c.name;
        var label=document.createElement('small');label.textContent=c.provider+' • sinal experimental';
        var controls=document.createElement('div');controls.className='channel-buttons';
        controls.appendChild(miniButton('▶ Assistir',function(){
          nativePlay({kind:'public',id:c.id},c.name,function(){
            dialog(c.name,'Este canal usa HLS. Instale e utilize o KTV OS Linux Live com mpv para reproduzir. O link pode estar indisponível.');
          });
        },true));
        controls.appendChild(miniButton('Adicionar aos meus canais',function(){
          post('/api/channels/change',{action:'add',name:c.name,url:c.url,category:c.category},function(fault,response){
            statusMsg('channel-result',fault?'Falha ao adicionar: '+fault.message:'Canal adicionado à sua lista pessoal.');
            if(!fault){channelCache=response.channels;renderChannels();}
          });
        }));
        card.appendChild(icon);card.appendChild(title);card.appendChild(label);card.appendChild(controls);container.appendChild(card);
      });
    });
  }

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
  el('display-apply').addEventListener('click',function(){
    var output=el('display-output').value,mode=el('display-mode').value;
    if(!output||!mode){videoFeedback('Selecione uma saída HDMI e uma resolução disponível.');return;}
    post('/api/hardware/video/preview',{output:output,mode:mode},function(err,data){
      if(err){videoFeedback('Não foi possível alterar resolução: '+err.message);return;}
      if(!data.result.pending){videoFeedback(data.result.message);return;}
      pendingVideoToken=data.result.token;
      var left=data.result.seconds;
      dialog('Confirmar nova resolução','Se a imagem está correta, selecione “Manter esta resolução”.\n\nA resolução anterior volta automaticamente após 20 segundos.');
      el('video-confirm').hidden=false;
      el('video-confirm').focus();
      function redraw(){
        el('dialog-message').textContent='Confirme somente se a imagem está correta.\n\nRetorno automático em '+left+' segundo(s).';
      }
      redraw();
      pendingVideoTimer=window.setInterval(function(){
        left--;
        if(left<=0){
          pendingVideoToken=null;
          clearVideoTimer();
          closeDialog();
          videoFeedback('Tempo encerrado. O Linux restaurou a resolução anterior.');
          refreshHardware();
        }else redraw();
      },1000);
    });
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