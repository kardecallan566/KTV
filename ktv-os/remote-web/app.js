const $=s=>document.querySelector(s);let token="",ws=null;
function status(t,ok=false){$("#status").textContent=t;$("#dot").classList.toggle("on",ok)}
async function pair(pin){const r=await fetch("/api/pair",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({pin})});if(!r.ok)throw Error(await r.text());return (await r.json()).token}
function connect(){ws=new WebSocket(`ws://${location.host}/ws?token=${encodeURIComponent(token)}`);ws.onopen=()=>status("Controle conectado",true);ws.onclose=()=>status("Desconectado");ws.onerror=()=>status("Falha na conexão");ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==="error")status(m.message)};
}
function send(o){if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify(o))}
$("#pairForm").onsubmit=async e=>{e.preventDefault();$("#pairError").textContent="";try{token=await pair($("#pin").value.trim());sessionStorage.ktvToken=token;$("#pair").hidden=true;$("#controls").hidden=false;connect()}catch(err){$("#pairError").textContent="PIN inválido ou servidor indisponível"}};
if(sessionStorage.ktvToken){token=sessionStorage.ktvToken;$("#pair").hidden=true;$("#controls").hidden=false;connect()}
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x===b));["mouse","tv","keyboard"].forEach(id=>$("#"+id).hidden=id!==b.dataset.mode)});
document.querySelectorAll("[data-click]").forEach(b=>b.onclick=()=>send({type:"click",button:b.dataset.click}));
document.querySelectorAll("[data-key]").forEach(b=>{const k=b.dataset.key;b.onpointerdown=e=>{e.preventDefault();send({type:"key",key:k,down:true});send({type:"key",key:k,down:false})}});
$("#textForm").onsubmit=e=>{e.preventDefault();const v=$("#textInput").value;for(const ch of v)send({type:"key",key:ch,down:true}),send({type:"key",key:ch,down:false});$("#textInput").value=""};
$("#disconnect").onclick=()=>{sessionStorage.removeItem("ktvToken");token="";ws?.close();$("#controls").hidden=true;$("#pair").hidden=false;status("Desconectado")};
const pad=$("#pad");let last=null,moved=false;
pad.onpointerdown=e=>{last={x:e.clientX,y:e.clientY};moved=false;pad.setPointerCapture(e.pointerId)};
pad.onpointermove=e=>{if(!last)return;const dx=e.clientX-last.x,dy=e.clientY-last.y;last={x:e.clientX,y:e.clientY};if(Math.abs(dx)+Math.abs(dy)>0){moved=true;send({type:"move",x:Math.round(dx*1.8),y:Math.round(dy*1.8)})}};
pad.onpointerup=e=>{if(last&&!moved)send({type:"click",button:"left"});last=null};
pad.onpointercancel=()=>last=null;
pad.oncontextmenu=e=>{e.preventDefault();send({type:"click",button:"right"})};
pad.addEventListener("wheel",e=>{e.preventDefault();send({type:"scroll",y:Math.sign(e.deltaY)*Math.max(1,Math.round(Math.abs(e.deltaY)/80))})},{passive:false});
