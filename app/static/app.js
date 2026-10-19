'use strict';
let state,editing=null;
const $=id=>document.getElementById(id);
function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
function show(message,error=false){const n=$('message');n.textContent=message;n.className=error?'error':'';n.style.display='block';}
async function api(path,data){const response=await fetch(path,{method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-Notebook-Token':state.token}:{},body:data?JSON.stringify(data):undefined});const body=await response.json();if(!response.ok)throw Error(body.error||'请求未完成');return body;}
function field(def){const [key,label,kind]=def;const wrap=el('div',undefined,'field');if(['file_name','source_path','angle_source','step_notes','other','energy_range'].includes(key))wrap.classList.add('wide');const lab=el('label',label);lab.htmlFor='f_'+key;let input;if(key==='processing'){input=el('select');state.modes.forEach(m=>{const o=el('option',m);o.value=m;input.append(o);});}else{input=el(key==='other'||key==='step_notes'?'textarea':'input');if(kind==='number'){input.type='number';input.step='any';}}input.id='f_'+key;input.name=key;if(key==='file_name')input.required=true;wrap.append(lab,input);return wrap;}
function construct(){const groups=[['基础条件',['run_mode','change','ep','slit','hv','polarization','temperature','vacuum']],['位置与角度',['x','y','z','polar','tilt','azimuth','directions']],['采集参数与备注',['energy_range','energy_center','energy_step','motor_step','frames','repeats','time','counts','step_notes','other']],['机械 mapping 关联',['scan_id','sequence','theta','phi','omega','angle_source','source_path']]];
const defs=new Map(state.fields.map(f=>[f[0],f]));['file_name','processing'].forEach(k=>$('identityFields').append(field(defs.get(k))));for(const [title,keys] of groups){const details=el('details');details.open=title==='基础条件';details.append(el('summary',title));const grid=el('div',undefined,'formgrid');keys.forEach(k=>grid.append(field(defs.get(k))));details.append(grid);$('fieldSections').append(details);}
const all=el('option','全部类型');all.value='';$('modeFilter').append(all);state.modes.forEach(m=>{const o=el('option',m);o.value=m;$('modeFilter').append(o);});state.session_fields.forEach(key=>{const d=el('div',undefined,'field');const l=el('label',key),i=el('input');i.name=key;i.id='s_'+key;l.htmlFor=i.id;d.append(l,i);$('sessionFields').append(d);});
}
function render(){ $('recordCount').textContent=state.records.length;$('sessionTitle').textContent=state.session['实验名称']||'记录条件，关联数据，提交处理任务';for(const key of state.session_fields)$('s_'+key).value=state.session[key]||'';renderConnection();renderRecords();renderGroups();renderJobs();}
function renderConnection(){const bridge=state.igor_bridge||{};$('igorPath').textContent=(bridge.message||'Igor 未连接')+(bridge.busy&&bridge.busy!=='stopped'?' · 正在处理任务':'');}
function renderRecords(){const text=$('search').value.toLocaleLowerCase(),mode=$('modeFilter').value;const rows=state.records.filter(r=>(!mode||r.processing===mode)&&JSON.stringify(r).toLocaleLowerCase().includes(text));const host=$('recordTable');host.replaceChildren();if(!rows.length){host.append(el('div',state.records.length?'没有符合筛选条件的记录':'尚无记录。在左侧填写后保存。','empty'));return;}const table=el('table'),head=el('tr');['文件 / 记录','处理类型','扫描组','顺序','theta (°)','hv (eV)','温度 (K)','偏振',''].forEach(v=>head.append(el('th',v)));table.append(el('thead'));table.firstChild.append(head);const tbody=el('tbody');rows.forEach(r=>{const row=el('tr');for(const k of ['file_name','processing','scan_id','sequence','theta','hv','temperature','polarization']){const td=el('td');if(k==='processing')td.append(el('span',r[k],'tag '+(r[k]==='机械 mapping'?'':'neutral')));else td.textContent=r[k]??'—';row.append(td);}const td=el('td'),b=el('button','编辑');b.onclick=()=>fill(r);td.append(b);row.append(td);tbody.append(row);});table.append(tbody);const div=el('div',undefined,'tablewrap');div.append(table);host.append(div);}
function fill(record){editing=record?{...record}:null;$('recordForm').reset();if(record)for(const [key] of state.fields)$('f_'+key).value=record[key]??'';$('formTitle').textContent=record?'编辑实验记录':'新增实验记录';$('f_file_name').focus();}
function renderGroups(){const host=$('scanGroups');host.replaceChildren();const groups=new Map();for(const r of state.records)if(r.processing==='机械 mapping'&&r.scan_id){if(!groups.has(r.scan_id))groups.set(r.scan_id,[]);groups.get(r.scan_id).push(r);}if(!groups.size)host.append(el('div','将记录类型设为“机械 mapping”，填写相同扫描组编号后在此提交。','empty'));for(const [id,rows]of groups){const box=el('div',undefined,'group'),info=el('div');info.append(el('strong',id),el('div',`${rows.length} 条 CUT · theta ${rows.map(r=>r.theta??'未填').join(', ')}°`,'muted'));const b=el('button','本组已完成，试跑','primary nowrap');b.onclick=async()=>{b.disabled=true;try{await api('/api/run',{scan_id:id,low:Number($('low').value)/1000,high:Number($('high').value)/1000,nx:Number($('nx').value),ny:Number($('ny').value)});show('任务已建立。记录可继续编辑；Igor 结果需核对实际运行回执。');await refresh();}catch(e){show(e.message,true);}finally{b.disabled=false;}};box.append(info,b);host.append(box);}}
function renderJobs(){
  const host=$('jobs');host.replaceChildren();
  if(!state.jobs.length){host.append(el('div','暂无处理任务','muted'));return;}
  const statuses={queued:'建立任务中',awaiting_igor:'等待 Igor 回执',waiting_unverified:'回执延迟 · 请检查 Igor',memory_complete:'内存试跑完成',failed:'任务失败',dispatched_unverified:'历史发送 · 未核验'};
  for(const job of state.jobs){
    const d=el('div',undefined,'job');
    d.append(el('strong',job.scan_id+' · '+(statuses[job.status]||job.status)),el('div',new Date(job.created).toLocaleString(),'muted'));
    if(job.error)d.append(el('p',job.error,'error'));
    const message=job.status==='failed'?'此任务已停止；实验记录仍可正常保存和导出。':job.message;
    if(message)d.append(el('p',message,'muted'));
    if(job.shape)d.append(el('p','三维数据：'+job.shape.join(' × ')+'（E, kx, ky）；网格覆盖 '+(100*job.finite/(job.finite+job.nans)).toFixed(1)+'%'));
    if(job.status==='memory_complete'&&job.result_folder)d.append(el('div','Igor 结果位置：'+job.result_folder,'muted'));
    host.append(d);
  }
}
async function refresh(){state=await api('/api/state');render();}
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-tab]').forEach(n=>n.classList.toggle('active',n===b));document.querySelectorAll('.section').forEach(n=>n.classList.toggle('active',n.id===b.dataset.tab));});
$('recordForm').onsubmit=async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target));if(editing){data.id=editing.id;data.revision=editing.revision;}try{const result=await api('/api/record',data);await refresh();fill(state.records.find(r=>r.id===result.id));show('记录已保存。');}catch(e){show(e.message,true);}};
$('sessionForm').onsubmit=async event=>{event.preventDefault();try{await api('/api/session',Object.fromEntries(new FormData(event.target)));await refresh();show('实验公共条件已保存，Excel 导出会包含这些条件。');}catch(e){show(e.message,true);}};
$('clearForm').onclick=()=>fill(null);
$('copyRecord').onclick=()=>{const data=Object.fromEntries(new FormData($('recordForm')));fill(null);for(const [key]of state.fields)$('f_'+key).value=data[key]??'';$('f_file_name').value='';if(data.sequence)$('f_sequence').value=Number(data.sequence)+1;show('已沿用条件。请填写新文件名，并核对本条实际角度与其他变化。');};
$('search').oninput=renderRecords;$('modeFilter').onchange=renderRecords;
(async()=>{try{state=await api('/api/state');construct();render();}catch(e){show('无法连接本机记录服务：'+e.message,true);}})();
setInterval(async()=>{if(!state)return;try{const newer=await api('/api/state');state.jobs=newer.jobs;state.igor_bridge=newer.igor_bridge;renderJobs();renderConnection();}catch{}},3000);
