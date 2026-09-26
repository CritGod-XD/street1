function showRegister(){document.getElementById('loginFormView').classList.add('hidden');document.getElementById('registerView').classList.remove('hidden')}
function showLogin(){document.getElementById('registerView').classList.add('hidden');document.getElementById('loginFormView').classList.remove('hidden')}
function toggleDetails(){const c=document.getElementById('detailsContent');const t=document.getElementById('detailsToggle');if(!c||!t)return;c.classList.toggle('hidden');t.classList.toggle('on')}
function openMap(){const m=document.getElementById('mapModal');if(m)m.classList.remove('hidden')}
function closeMap(e){const m=document.getElementById('mapModal');if(m)m.classList.add('hidden')}
document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));b.classList.add('active')}))})

// Excel-backed ML road viewer. Frames are ordered by the Image Log station
// sequence and are stacked vertically because each source image is a
// longitudinal road slice. The controls are deliberately simple so the
// viewer can later be fed by an API without changing the UI.
function initStreetLensRoadViewer(){
    const viewer=document.getElementById('streetLensRoadScroll');
    const strip=document.getElementById('streetLensRoadStrip');
    const status=document.getElementById('streetLensFrameStatus');
    const fitBtn=document.getElementById('streetLensRoadFit');
    const zoomInBtn=document.getElementById('streetLensRoadZoomIn');
    const zoomLabel=document.getElementById('streetLensRoadZoomLabel');
    if(!viewer||!strip)return;

    const frames=[...strip.querySelectorAll('.streetlens-road-frame')];
    if(!frames.length)return;

    // 8% is approximately the scale required to show the full 41-frame
    // inspection corridor inside the compact center column.
    const levels=[0.08,0.13,0.20,0.30,0.45,0.60,0.80,1.00];
    let zoomIndex=levels.length-1;

    function updateStatus(){
        const scale=levels[zoomIndex];
        // offsetTop is measured before transform, so convert the visible
        // scroll position back into the strip's unscaled coordinate space.
        const center=(viewer.scrollTop/scale)+(viewer.clientHeight/(2*scale));
        let active=0;
        frames.forEach((frame,i)=>{
            const top=frame.offsetTop;
            const bottom=top+frame.offsetHeight;
            if(center>=top&&center<bottom)active=i;
        });
        if(status)status.textContent=`${active+1} / ${frames.length}`;
    }

    function applyZoom(index, keepPosition){
        zoomIndex=Math.max(0,Math.min(levels.length-1,index));
        const scale=levels[zoomIndex];
        const oldScale=Number(strip.dataset.scale||1);
        const oldCenter=(viewer.scrollTop+viewer.clientHeight/2)/oldScale;
        strip.style.transform=`scale(${scale})`;
        // Transform does not change layout height; the negative margin makes
        // the scrollable area match the transformed visual height.
        const naturalHeight=strip.scrollHeight;
        strip.style.marginBottom=`-${Math.max(0,(1-scale)*naturalHeight)}px`;
        strip.dataset.scale=String(scale);
        if(zoomLabel)zoomLabel.textContent=`${Math.round(scale*100)}%`;
        if(keepPosition){
            requestAnimationFrame(()=>{
                viewer.scrollTop=Math.max(0,(oldCenter*scale)-(viewer.clientHeight/2));
                updateStatus();
            });
        }else{
            viewer.scrollTop=0;
            updateStatus();
        }
    }

    if(fitBtn)fitBtn.addEventListener('click',()=>applyZoom(0,false));
    if(zoomInBtn)zoomInBtn.addEventListener('click',()=>applyZoom(zoomIndex+1,true));
    viewer.addEventListener('scroll',updateStatus,{passive:true});
    window.addEventListener('resize',()=>applyZoom(zoomIndex,true));

    // Wait for the first image dimensions before measuring the full road.
    const refresh=()=>applyZoom(zoomIndex,false);
    if(frames.every(f=>f.querySelector('img')?.complete)) refresh();
    else frames.forEach(f=>{const img=f.querySelector('img');if(img)img.addEventListener('load',refresh,{once:true});});
    applyZoom(zoomIndex,false);
}

document.addEventListener('DOMContentLoaded',initStreetLensRoadViewer);
