(function(){
'use strict';
/* Mouse and touch keyboard. Manual only. Position resets whenever reopened. */
var panel=document.createElement('div');panel.id='ktv-osk';panel.hidden=true;
panel.setAttribute('role','group');panel.setAttribute('aria-label','Teclado KTV arrastável');
var head=document.createElement('div');head.className='osk-head';head.title='Arraste por aqui';
var title=document.createElement('strong');title.textContent='⠿ Arraste para mover · Teclado KTV';
var close=document.createElement('button');close.className='osk-close';close.type='button';close.textContent='✕ Fechar';
head.appendChild(title);head.appendChild(close);panel.appendChild(head);
var modes=document.createElement('div');modes.className='osk-modes';panel.appendChild(modes);
var holder=document.createElement('div');holder.className='osk-keys';panel.appendChild(holder);
var toggle=document.createElement('button');toggle.id='ktv-osk-toggle';toggle.type='button';
toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-pressed','false');
var target=null,mode='abc',shift=false,dragId=null,deltaX=0,deltaY=0;
function suitable(el){
  if(!el||el.disabled||el.readOnly)return false;
  if(el.tagName==='TEXTAREA')return true;
  return el.tagName==='INPUT'&&['text','search','url','password','email','number',''].indexOf(el.type)>=0;
}
function open(show){
  if(show&&panel.hidden){panel.style.left='';panel.style.top='';panel.style.bottom='';panel.style.transform='';}
  panel.hidden=!show;
  toggle.setAttribute('aria-expanded',show?'true':'false');toggle.setAttribute('aria-pressed',show?'true':'false');
  toggle.textContent=show?'✕ Fechar teclado':'⌨ Abrir teclado';
  if(!show)dragId=null;
}
function insert(value){
  if(!target||!suitable(target))return;
  target.focus();
  if(typeof target.setRangeText==='function'){
    var start=target.selectionStart||0,end=target.selectionEnd||start;
    target.setRangeText(value,start,end,'end');
  }else target.value+=value;
  target.dispatchEvent(new Event('input',{bubbles:true}));
}
function action(value){
  if(value==='SHIFT'){shift=!shift;build();return;}
  if(value==='BACKSPACE'){
    if(!target||!suitable(target))return;
    target.focus();
    var start=target.selectionStart||0,end=target.selectionEnd||start;
    if(typeof target.setRangeText==='function')target.setRangeText('',Math.max(0,start-(start===end?1:0)),end,'end');
    else target.value=target.value.slice(0,-1);
    target.dispatchEvent(new Event('input',{bubbles:true}));
  }else if(value==='ENTER'){
    if(!target)return;
    if(target.tagName==='TEXTAREA')insert('\n');
    else if(target.form&&typeof target.form.requestSubmit==='function')target.form.requestSubmit();
  }else insert(shift?value.toUpperCase():value);
}
function key(value,label,wide){
  var b=document.createElement('button');b.type='button';b.className='osk-key'+(wide?' wide':'');
  b.textContent=label||value;
  b.addEventListener('pointerdown',function(ev){ev.preventDefault();});
  b.addEventListener('click',function(){action(value);});
  return b;
}
var layouts={
  abc:['1234567890','qwertyuiop','asdfghjklç','zxcvbnm.,?-'],
  symbols:['!@#$%¨&*()','-_+=[]{}','/\\|:;','<>?^°§©®€£¥'],
  accents:['áàâãäéèêë','íìîïóòôõö','úùûüñçýÿ','æœß¡¿ªºµ¢₿']
};
function build(){
  modes.textContent='';holder.textContent='';
  [['abc','ABC'],['symbols','123 / Símbolos'],['accents','Acentos']].forEach(function(opt){
    var b=document.createElement('button');b.type='button';b.textContent=opt[1];
    b.className='osk-mode'+(mode===opt[0]?' selected':'');
    b.setAttribute('aria-pressed',mode===opt[0]?'true':'false');
    b.addEventListener('click',function(){mode=opt[0];build();});modes.appendChild(b);
  });
  layouts[mode].forEach(function(row,i){
    var div=document.createElement('div');div.className='osk-row';
    if(mode==='abc'&&i===3)div.appendChild(key('SHIFT','⇧ Shift',true));
    Array.from(row).forEach(function(ch){div.appendChild(key(ch,shift?ch.toUpperCase():ch));});
    if(i===3)div.appendChild(key('BACKSPACE','⌫',true));
    holder.appendChild(div);
  });
  var bottom=document.createElement('div');bottom.className='osk-row';
  bottom.appendChild(key('@','@'));bottom.appendChild(key('/','/'));
  bottom.appendChild(key(' ','Espaço',true));bottom.appendChild(key('ENTER','↵ Enter',true));
  holder.appendChild(bottom);
}
head.addEventListener('pointerdown',function(ev){
  if(ev.target===close||ev.button!==0||panel.hidden)return;
  var rect=panel.getBoundingClientRect();dragId=ev.pointerId;
  deltaX=ev.clientX-rect.left;deltaY=ev.clientY-rect.top;
  head.setPointerCapture(ev.pointerId);ev.preventDefault();
});
head.addEventListener('pointermove',function(ev){
  if(dragId!==ev.pointerId)return;
  var x=Math.max(0,Math.min(window.innerWidth-panel.offsetWidth,ev.clientX-deltaX));
  var y=Math.max(0,Math.min(window.innerHeight-panel.offsetHeight,ev.clientY-deltaY));
  panel.style.left=x+'px';panel.style.top=y+'px';
  panel.style.bottom='auto';panel.style.transform='none';
});
function endDrag(ev){if(dragId===ev.pointerId)dragId=null;}
head.addEventListener('pointerup',endDrag);head.addEventListener('pointercancel',endDrag);
window.addEventListener('resize',function(){
  if(panel.hidden||!panel.style.top)return;
  panel.style.left=Math.max(0,Math.min(parseFloat(panel.style.left)||0,window.innerWidth-panel.offsetWidth))+'px';
  panel.style.top=Math.max(0,Math.min(parseFloat(panel.style.top)||0,window.innerHeight-panel.offsetHeight))+'px';
});
close.addEventListener('click',function(){open(false);});
toggle.addEventListener('click',function(){
  if(suitable(document.activeElement))target=document.activeElement;
  open(panel.hidden);if(target)target.focus();
});
document.addEventListener('focusin',function(ev){if(suitable(ev.target))target=ev.target;});
document.addEventListener('keydown',function(ev){if(ev.key==='Escape'&&!panel.hidden)open(false);});
build();document.body.appendChild(panel);document.body.appendChild(toggle);
open(false);
})();