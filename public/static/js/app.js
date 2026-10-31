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
    const datasetSelect=document.getElementById('streetLensDatasetSelect');
    const annotationNote=document.getElementById('streetLensAnnotationNote');
    const categoryInputs=[...document.querySelectorAll('[data-annotation-label]')];
    let currentSelection=0;
    let currentFrames=[];
    const annotationCache=new Map();
    const imageCache=new Map();
    const enabledLabels=()=>new Set(categoryInputs.filter(input=>input.checked).map(input=>input.dataset.annotationLabel));
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

    function drawAnnotations(canvas, annotation, image){
        const ctx=canvas.getContext('2d');
        canvas.width=image.naturalWidth;
        canvas.height=image.naturalHeight;
        ctx.clearRect(0,0,canvas.width,canvas.height);
        const visible=enabledLabels();
        const colors={C:'#ff3b30',P:'#ff9500',M:'#0a84ff',S:'#ffd60a'};
        for(const shape of (annotation?.shapes||[])){
            const label=String(shape.label||'');
            if(!visible.has(label)||!Array.isArray(shape.points)||shape.points.length<2)continue;
            const color=colors[label];
            if(!color)continue;
            ctx.beginPath();
            shape.points.forEach((point,i)=>{
                if(!Array.isArray(point)||point.length<2)return;
                const x=Number(point[0]),y=Number(point[1]);
                if(!Number.isFinite(x)||!Number.isFinite(y))return;
                if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
            });
            if(String(shape.shape_type||'polygon')==='polygon')ctx.closePath();
            ctx.fillStyle=color+'35';
            ctx.strokeStyle=color;
            ctx.lineWidth=Math.max(2,canvas.width/820);
            ctx.fill();ctx.stroke();
        }
    }

    async function loadAnnotation(frame){
        if(!frame.annotation)return null;
        if(annotationCache.has(frame.annotation))return annotationCache.get(frame.annotation);
        const promise=fetch(frame.annotation,{cache:'force-cache'}).then(response=>{
            if(!response.ok)throw new Error(`Annotation request failed (${response.status})`);
            return response.json();
        });
        annotationCache.set(frame.annotation,promise);
        try{return await promise;}catch(error){annotationCache.delete(frame.annotation);throw error;}
    }

    function attachFrame(frame,figure,img,canvas,selectionId){
        let started=false;
        const start=async()=>{
            if(started||!frame.annotation||!img.complete||!img.naturalWidth)return;
            started=true;
            try{
                const annotation=await loadAnnotation(frame);
                if(selectionId!==currentSelection||!figure.isConnected)return;
                const aw=Number(annotation?.imageWidth),ah=Number(annotation?.imageHeight);
                if(aw&&ah&&(aw!==img.naturalWidth||ah!==img.naturalHeight)){
                    if(annotationNote)annotationNote.textContent=`Dimension mismatch on ${frame.frame_id||frame.frame}: image ${img.naturalWidth}×${img.naturalHeight}, annotation ${aw}×${ah}.`;
                    return;
                }
                drawAnnotations(canvas,annotation,img);
                figure.dataset.annotationLoaded='true';
                if(annotationNote&&selectionId===currentSelection){
                    const shapes=Array.isArray(annotation?.shapes)?annotation.shapes:[];
                    const counts={C:0,P:0,M:0,S:0};
                    shapes.forEach(shape=>{if(Object.prototype.hasOwnProperty.call(counts,shape.label))counts[shape.label]++;});
                    annotationNote.textContent=`${frame.frame_id||frame.frame}: ${shapes.length} shapes · ${counts.C} cracks · ${counts.P} potholes · ${counts.M} patches · ${counts.S} sealant`;
                }
            }catch(error){
                if(selectionId!==currentSelection||!figure.isConnected)return;
                canvas.getContext('2d').clearRect(0,0,canvas.width,canvas.height);
                const warning=document.createElement('span');warning.className='streetlens-frame-error';warning.textContent='Annotations unavailable';figure.appendChild(warning);
                if(annotationNote)annotationNote.textContent=`Could not load annotations for ${frame.frame_id||frame.frame}: ${error.message}. Image remains visible.`;
            }
        };
        if(img.complete&&img.naturalWidth)start();else img.addEventListener('load',start,{once:true});
    }

    // Keep a rolling preload window around the frame nearest the viewer center.
    // Images and their annotations are requested together; loaded frames remain cached
    // in the DOM so scrolling back does not trigger another download.
    const PRELOAD_RADIUS = 3;

    function preloadFrame(index, selectionId){
        if(selectionId !== currentSelection) return;
        const figure = strip.querySelector(`.streetlens-road-frame[data-frame-index="${index}"]`);
        if(!figure) return;
        const frame = figure._streetLensFrame;
        const img = figure.querySelector('img');
        if(!img) return;

        if(!img.getAttribute('src') && img.dataset.src){
            img.loading = 'eager';
            img.fetchPriority = Math.abs(index - getActiveFrameIndex()) <= 1 ? 'high' : 'auto';
            img.src = img.dataset.src;
        }

        // Warm the annotation cache at the same time as the image request.
        // attachFrame() draws it once the image has decoded.
        if(frame?.annotation) loadAnnotation(frame).catch(()=>{});
    }

    function getActiveFrameIndex(){
        const frames=getFrames();
        if(!frames.length) return 0;
        const scale=levels[zoomIndex];
        const center=(viewer.scrollTop + viewer.clientHeight/2) / scale;
        let active=0;
        frames.forEach((frame,i)=>{
            const top=frame.offsetTop;
            const bottom=top+frame.offsetHeight;
            if(center>=top && center<bottom) active=i;
        });
        return active;
    }

    function preloadWindow(centerIndex, selectionId=currentSelection){
        if(selectionId !== currentSelection) return;
        const first=Math.max(0,centerIndex-PRELOAD_RADIUS);
        const last=Math.min(currentFrames.length-1,centerIndex+PRELOAD_RADIUS);
        for(let i=first;i<=last;i++) preloadFrame(i,selectionId);
    }

    function render(frames){
        const selectionId=++currentSelection;
        currentFrames=Array.isArray(frames)?frames:[];
        strip.innerHTML='';
        resetZoom();
        if(annotationNote){
            if(!currentFrames.length) annotationNote.textContent='Select a road section to view its inspection frames and annotations.';
            else if(currentFrames.some(frame=>frame.annotation)) annotationNote.textContent='Loading nearby frames and matching annotations…';
            else annotationNote.textContent='Frames loaded. Annotation paths are not yet mapped for this road.';
        }
        if(!currentFrames.length){
            strip.classList.add('hidden');
            if(pending) pending.classList.remove('hidden');
            if(status) status.textContent='—';
            return;
        }
        strip.classList.remove('hidden');
        if(pending) pending.classList.add('hidden');

        currentFrames.forEach((frame,index)=>{
            const figure=document.createElement('figure');
            figure.className='streetlens-road-frame';
            figure.dataset.frameIndex=index;
            const frameWidth=Number(frame.image_width||1640);
            const frameHeight=Number(frame.image_height||787);
            if(frameWidth>0&&frameHeight>0) figure.style.aspectRatio=`${frameWidth} / ${frameHeight}`;
            figure.dataset.stationStart=frame.station_start??'';
            figure.dataset.stationEnd=frame.station_end??'';
            figure._streetLensFrame=frame;

            const img=document.createElement('img');
            const imagePath=frame.image||(`/static/images/${frame.file}`);
            img.alt=`Pavement inspection frame ${frame.frame_id||frame.frame||index+1}`;
            img.loading='lazy';
            img.decoding='async';
            img.style.aspectRatio=(frameWidth>0&&frameHeight>0)?`${frameWidth} / ${frameHeight}`:'1640 / 787';
            img.dataset.src=imagePath;
            img.addEventListener('load',()=>attachFrame(frame,figure,img,figure.querySelector('canvas'),selectionId),{once:true});
            img.addEventListener('error',()=>{
                if(selectionId!==currentSelection) return;
                const warning=document.createElement('span');
                warning.className='streetlens-frame-error';
                warning.textContent='Image unavailable';
                figure.appendChild(warning);
            },{once:true});

            const canvas=document.createElement('canvas');
            canvas.className='streetlens-frame-overlay';
            canvas.setAttribute('aria-hidden','true');
            const caption=document.createElement('figcaption');
            const left=document.createElement('span');
            left.textContent=`#${frame.frame_id||frame.frame||String(index+1).padStart(4,'0')}`;
            const right=document.createElement('span');
            if(Number.isFinite(Number(frame.station_start))&&Number.isFinite(Number(frame.station_end))) right.textContent=`${Number(frame.station_start).toFixed(2)}–${Number(frame.station_end).toFixed(2)} ft`;
            else right.textContent='Road frame';
            caption.append(left,right);
            figure.append(img,canvas,caption);
            strip.appendChild(figure);
        });

        updateStatus();
        // Start the first frame plus the next three immediately.
        preloadWindow(0,selectionId);
    }

    async function loadRoadDataset(indexPath,roadName){
        if(annotationNote)annotationNote.textContent=`Loading ${roadName||'selected road'} inspection frames…`;
        try{
            const response=await fetch(indexPath,{cache:'no-store'});
            if(!response.ok)throw new Error(`Dataset index request failed (${response.status})`);
            const data=await response.json();
            render(data.frames||[]);
            if(annotationNote)annotationNote.textContent=(data.frames||[]).length
                ? `${roadName||data.road_name||'Selected road'} · ${data.frames.length} inspection frames loaded`
                : `No inspection frames are currently available for ${roadName||'this road'}.`;
            return data;
        }catch(error){
            render([]);
            if(annotationNote)annotationNote.textContent=`Could not load ${roadName||'road'} dataset: ${error.message}`;
            return null;
        }
    }
    async function loadSampleDataset(){
        return loadRoadDataset('/static/data/penn_ave_n_sample_frames.json','Penn Ave N · sample');
    }

    if(datasetSelect)datasetSelect.addEventListener('change',()=>{
        if(datasetSelect.value==='penn-sample')loadSampleDataset();
        else {render([]);if(annotationNote)annotationNote.textContent='Select a road section on the map to load its frames.';}
    });
    categoryInputs.forEach(input=>input.addEventListener('change',()=>{
        const selectionId=currentSelection;
        strip.querySelectorAll('.streetlens-road-frame').forEach(figure=>{
            const frame=figure._streetLensFrame,img=figure.querySelector('img'),canvas=figure.querySelector('canvas');
            if(!frame?.annotation||!img?.naturalWidth||!canvas?.width)return;
            loadAnnotation(frame).then(annotation=>{if(selectionId===currentSelection&&figure.isConnected)drawAnnotations(canvas,annotation,img);}).catch(()=>{});
        });
    }));

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
    window.streetLensLoadRoadFrames=(frames)=>{
        if(datasetSelect)datasetSelect.value='map';
        render(frames);
    };
    window.streetLensLoadRoadDataset=(indexPath,roadName)=>{
        if(datasetSelect)datasetSelect.value='map';
        return loadRoadDataset(indexPath,roadName);
    };
    window.streetLensClearRoadFrames=(message)=>{
        if(datasetSelect)datasetSelect.value='map';
        render([]);
        if(annotationNote&&message)annotationNote.textContent=message;
    };
}

document.addEventListener('DOMContentLoaded',initStreetLensRoadViewer);
