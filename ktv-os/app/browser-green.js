(function(){
'use strict';
var form=document.getElementById('green-search');
var query=document.getElementById('green-query');
var status=document.getElementById('green-status');
function search(value){
  var text=(value||'').trim();
  if(!text||text.length>180){status.textContent='Digite uma pesquisa de até 180 caracteres.';return;}
  var target='https://duckduckgo.com/?q='+encodeURIComponent(text);
  var tab=window.open(target,'_blank','noopener,noreferrer');
  status.textContent='Pesquisa enviada ao DuckDuckGo em uma nova aba. Use Alt+Tab ou Ctrl+Tab para voltar.';
  if(!tab)status.textContent='O navegador pode ter bloqueado a nova aba. Permita pop-ups deste endereço local.';
}
form.addEventListener('submit',function(e){e.preventDefault();search(query.value);});
document.querySelectorAll('[data-search]').forEach(function(button){
  button.addEventListener('click',function(){query.value=button.getAttribute('data-search');search(query.value);});
});
document.getElementById('virtual-system').addEventListener('click',function(){
  fetch('/api/input/virtual-toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
   .then(function(r){return r.json().then(function(x){if(!r.ok)throw new Error(x.error||'Erro');return x;});})
   .then(function(x){status.textContent=x.input.virtual_open?'Teclado de sistema aberto para sites externos.':'Teclado de sistema fechado.';})
   .catch(function(e){status.textContent=e.message+' — o teclado KTV na tela continua disponível.';});
});
})();