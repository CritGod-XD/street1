function showRegister(){document.getElementById('loginFormView').classList.add('hidden');document.getElementById('registerView').classList.remove('hidden')}
function showLogin(){document.getElementById('registerView').classList.add('hidden');document.getElementById('loginFormView').classList.remove('hidden')}
function toggleDetails(){const c=document.getElementById('detailsContent');const t=document.getElementById('detailsToggle');if(!c||!t)return;c.classList.toggle('hidden');t.classList.toggle('on')}
function openMap(){const m=document.getElementById('mapModal');if(m)m.classList.remove('hidden')}
function closeMap(e){const m=document.getElementById('mapModal');if(m)m.classList.add('hidden')}
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}))})
