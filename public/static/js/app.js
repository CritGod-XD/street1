function showRegister(){document.getElementById('loginFormView').classList.add('hidden');document.getElementById('registerView').classList.remove('hidden')}
function showLogin(){document.getElementById('registerView').classList.add('hidden');document.getElementById('loginFormView').classList.remove('hidden')}
function toggleDetails(){const c=document.getElementById('detailsContent');const t=document.getElementById('detailsToggle');if(!c||!t)return;c.classList.toggle('hidden');t.classList.toggle('on')}
function openMap(){const m=document.getElementById('mapModal');if(m)m.classList.remove('hidden')}
function closeMap(e){const m=document.getElementById('mapModal');if(m)m.classList.add('hidden')}
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}))})

// Linked ML road viewer. Populated from the road selected on the map.
let streetLensRoadViewerState = null;

function initStreetLensRoadViewer(){
    const viewer=document.getElementById('streetLensRoadScroll');
    const strip=document.getElementById('streetLensRoadStrip');
    const status=document.getElementById('streetLensFrameStatus');
    const zoomInBtn=document.getElementById('streetLensRoadZoomIn');
    const zoomLabel=document.getElementById('streetLensRoadZoomLabel');
    const pending=document.getElementById('streetLensRoadPending');
    if(!viewer||!strip)return;

    const levels=[0.08,0.12,0.18,0.25,0.35,0.50,0.70,0.85,1.0,1.25,1.5,1.75,2.0,2.5,3.0];
    let zoomIndex=levels.indexOf(1);

    function getFrames(){ return [...strip.querySelectorAll('.streetlens-road-frame')]; }

    function updateStatus(){
        const frames=getFrames();
        if(!frames.length){ if(status)status.textContent='—'; return; }
        const scale=levels[zoomIndex];
        const center=(viewer.scrollTop + viewer.clientHeight/2) / scale;
        let active=0;
        frames.forEach((frame,i)=>{
            const top=frame.offsetTop;
            const bottom=top+frame.offsetHeight;
            if(center>=top && center<bottom) active=i;
        });
        if(status)status.textContent=`${active+1} / ${frames.length}`;
    }

    function setScale(index, anchor){
        const frames=getFrames();
        if(!frames.length) return;
        const oldScale=levels[zoomIndex];
        const nextIndex=Math.max(0,Math.min(levels.length-1,index));
        const newScale=levels[nextIndex];
        if(oldScale===newScale) return;

        // Anchor the exact image point under the mouse while zooming.
        const rect=viewer.getBoundingClientRect();
        const ax=anchor ? anchor.x-rect.left : viewer.clientWidth/2;
        const ay=anchor ? anchor.y-rect.top : viewer.clientHeight/2;
        const contentX=(viewer.scrollLeft+ax)/oldScale;
        const contentY=(viewer.scrollTop+ay)/oldScale;

        zoomIndex=nextIndex;
        strip.style.transform=`scale(${newScale})`;
        strip.style.width='100%';
        strip.style.marginBottom='0';
        strip.dataset.scale=String(newScale);
        if(zoomLabel)zoomLabel.textContent=`${Math.round(newScale*100)}%`;

        requestAnimationFrame(()=>{
            viewer.scrollLeft=Math.max(0,contentX*newScale-ax);
            viewer.scrollTop=Math.max(0,contentY*newScale-ay);
            updateStatus();
        });
    }

    function fitWholeRoad(){
        const frames=getFrames();
        if(!frames.length)return;
        const naturalHeight=frames.reduce((sum,f)=>sum+f.offsetHeight,0);
        if(!naturalHeight)return;
        const available=Math.max(120,viewer.clientHeight-12);
        // Fit the complete inspected corridor vertically while preserving its proportions.
        const target=Math.max(0.08,Math.min(0.85,available/naturalHeight));
        let closest=0;
        levels.forEach((v,i)=>{ if(Math.abs(v-target)<Math.abs(levels[closest]-target)) closest=i; });
        const oldScale=levels[zoomIndex];
        zoomIndex=closest;
        const scale=levels[zoomIndex];
        strip.style.transform=`scale(${scale})`;
        strip.style.width='100%';
        strip.style.marginBottom='0';
        strip.dataset.scale=String(scale);
        if(zoomLabel)zoomLabel.textContent=`${Math.round(scale*100)}%`;
        viewer.scrollTop=0;
        viewer.scrollLeft=0;
        updateStatus();
    }

    function resetZoom(){
        zoomIndex=levels.indexOf(1);
        strip.style.transform='scale(1)';
        strip.style.width='100%';
        strip.style.marginBottom='0';
        strip.dataset.scale='1';
        if(zoomLabel)zoomLabel.textContent='100%';
        viewer.scrollTop=0;
        viewer.scrollLeft=0;
        updateStatus();
    }

    function render(frames){
        strip.innerHTML='';
        resetZoom();
        if(!frames || !frames.length){
            strip.classList.add('hidden');
            if(pending)pending.classList.remove('hidden');
            if(status)status.textContent='—';
            return;
        }

        strip.classList.remove('hidden');
        if(pending)pending.classList.add('hidden');

        frames.forEach((frame,index)=>{
            const figure=document.createElement('figure');
            figure.className='streetlens-road-frame';
            figure.dataset.frameIndex=index;
            figure.dataset.stationStart=frame.station_start ?? '';
            figure.dataset.stationEnd=frame.station_end ?? '';

            const img=document.createElement('img');
            img.src=`/static/images/${frame.file}`;
            img.alt=`Pavement inspection frame ${frame.frame}, station ${frame.station_start} to ${frame.station_end} feet`;
            img.loading='lazy';

            const caption=document.createElement('figcaption');
            const left=document.createElement('span');
            left.textContent=`#${frame.frame}`;
            const right=document.createElement('span');
            right.textContent=`${Number(frame.station_start).toFixed(2)}–${Number(frame.station_end).toFixed(2)} ft`;
            caption.append(left,right);
            figure.append(img,caption);
            strip.appendChild(figure);
        });

        const imgs=[...strip.querySelectorAll('img')];
        let refreshed=false;
        const once=()=>{ if(!refreshed){refreshed=true; requestAnimationFrame(()=>{updateStatus();});} };
        if(imgs.every(img=>img.complete)) once();
        else imgs.forEach(img=>img.addEventListener('load',once,{once:true}));
        updateStatus();
    }

    // Normal wheel = scroll through the road. Ctrl + wheel = zoom at the cursor.
    viewer.addEventListener('wheel',(event)=>{
        if(!event.ctrlKey)return;
        event.preventDefault();
        const direction=event.deltaY<0 ? 1 : -1;
        setScale(zoomIndex+direction,{x:event.clientX,y:event.clientY});
    },{passive:false});

    if(zoomInBtn)zoomInBtn.addEventListener('click',()=>setScale(zoomIndex+1));
    viewer.addEventListener('scroll',updateStatus,{passive:true});
    window.addEventListener('resize',()=>updateStatus());

    streetLensRoadViewerState={render,updateStatus,setScale,fitWholeRoad};
    window.streetLensLoadRoadFrames=render;
}

document.addEventListener('DOMContentLoaded',initStreetLensRoadViewer);
