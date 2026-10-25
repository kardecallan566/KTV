(function(){
'use strict';
/* Lightweight KTV keyboard for local input fields. Works with a mouse.
   External Chromium pages may use the optional native X11 keyboard. */
var cssId='ktv-osk';
var panel=document.createElement('div');
panel.id=cssId; panel.hidden=true;
panel.setAttribute('role','group');
panel.setAttribute('aria-label','Teclado virtual KTV');
var head=document.createElement('div');head.className='osk-head';
var title=document.createElement('strong');title.textContent='Teclado virtual KTV';
var close=document.createElement('button');close.textContent='✕ Fechar';close.type='button';close.className='osk-close';head.appendChild(title);head.appendChild(close);panel.appendChild(head);
var holder=document.createElement('div');holder.className='osk-keys';panel.appendChild(holder);
var toggle=document.createElement('button');toggle.id='ktv-osk-toggle';toggle.type='button';toggle.textContent='⌨ Teclado';
toggle.setAttribute('aria-label','Abrir ou fechar teclado virtual');
toggle.setAttribute('aria-expanded','false');
var target=null, automatic=false, shift=false;
function suitable(el){
  if(!el||el.disabled||el.readOnly)return false;
  if(el.tagName==='TEXTAREA')return true;
  if(el.tagName!=='INPUT')return false;
  return ['text','search','url','password','email','number',''].indexOf(el.type)>=0;
}
function open(state){
  panel.hidden=!state;
  toggle.setAttribute('aria-expanded',state?'true':'false');
}
function setText(text){
  if(!target||!suitable(target))return;
  target.focus();
  if(typeof target.setRangeText==='function'){
    var at=target.selectionStart||0;
    var end=target.selectionEnd||at;
    target.setRangeText(text,at,end,'end');
  }else target.value+=text;
  target.dispatchEvent(new Event('input',{bubbles:true}));
}
function action(value){
  if(value==='SHIFT'){shift=!shift;build();return;}
  if(value==='BACKSPACE'){
    if(!target)return;
    target.focus();
    var pos=target.selectionStart||0,end=target.selectionEnd||pos;
    target.setRangeText('',Math.max(0,pos-(pos===end?1:0)),end,'end');
    target.dispatchEvent(new Event('input',{bubbles:true}));
  }else if(value==='ENTER'){
    if(!target)return;
    if(target.tagName==='TEXTAREA')setText('\n');
    else if(target.form){if(typeof target.form.requestSubmit==='function')target.form.requestSubmit();}
  }else setText(shift?value.toUpperCase():value);
}
function key(value,caption,wide){
  var b=document.createElement('button');
  b.type='button';b.className='osk-key'+(wide?' wide':'');
  b.textContent=caption||value;
  b.addEventListener('pointerdown',function(e){e.preventDefault();});
  b.addEventListener('click',function(){action(value);});
  return b;
}
function build(){
  holder.textContent='';
  ['1234567890','qwertyuiop','asdfghjklç','zxcvbnm.,?-'].forEach(function(row){
    var div=document.createElement('div');div.className='osk-row';
    if(row.indexOf('zxc')===0)div.appendChild(key('SHIFT','⇧ Shift',true));
    Array.from(row).forEach(function(ch){div.appendChild(key(ch,shift?ch.toUpperCase():ch));});
    if(row.indexOf('zxc')===0)div.appendChild(key('BACKSPACE','⌫',true));
    holder.appendChild(div);
  });
  var bottom=document.createElement('div');bottom.className='osk-row';
  bottom.appendChild(key('@','@'));
  bottom.appendChild(key('/','/'));
  bottom.appendChild(key(' ','Espaço',true));
  bottom.appendChild(key('ENTER','↵ Enter',true));
  holder.appendChild(bottom);
}
close.addEventListener('click',function(){open(false);});
toggle.addEventListener('click',function(){
  if(suitable(document.activeElement))target=document.activeElement;
  open(panel.hidden);
  if(target)target.focus();
});
document.addEventListener('focusin',function(ev){
  if(suitable(ev.target)){
    target=ev.target;
    if(automatic)open(true);
  }
});
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&!panel.hidden)open(false);});
build();document.body.appendChild(panel);document.body.appendChild(toggle);
fetch('/api/input/status',{cache:'no-store'})
  .then(function(r){if(!r.ok)throw Error('no input status');return r.json();})
  .then(function(data){
    automatic=data.input && data.input.keyboard_detected===false;
    if(automatic && suitable(document.activeElement)){target=document.activeElement;open(true);}
  }).catch(function(){/* Manual keyboard still accessible without system API. */});
})();