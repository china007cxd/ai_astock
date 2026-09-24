/* ============ 交易日历(周末/节假日自动屏蔽) ============ */
"use strict";

const cal={y:0,m:0,target:"",cache:{},latest:"",prev:""};
const DATE_RELOAD={dsDate:loadDuishu,luDate:loadLimitUp,ztDate:loadZtPool,
  zbDate:loadZbPool,dtDate:loadDtPool,bkDate:loadBroken,lhbDate:loadLhb};
function pad2(n){return String(n).padStart(2,"0")}
function fmtD(d){return `${d.getFullYear()}-${pad2(d.getMonth()+1)}-${pad2(d.getDate())}`}

async function loadCalYear(y){
  if(cal.cache[y])return cal.cache[y];
  try{
    const j=await api("trade_dates",{year:y});
    cal.cache[y]=j.days||{};
    if(j.latest)cal.latest=j.latest;
    if(j.prev)cal.prev=j.prev;
  }catch(e){cal.cache[y]={}}
  return cal.cache[y];
}

function openCal(id){
  cal.target=id;
  const v=$("#"+id).val()||"";
  const m=/^(\d{4})-(\d{2})/.exec(v);
  if(m){cal.y=+m[1];cal.m=+m[2]-1}
  else{const d=cal.latest?new Date(cal.latest+"T00:00:00"):new Date();cal.y=d.getFullYear();cal.m=d.getMonth()}
  renderCal().then(()=>$("#calMask").addClass("show"));
}

function closeCal(){$("#calMask").removeClass("show");cal.target=""}

async function renderCal(){
  $("#calTitle").text(`${cal.y}年${cal.m+1}月`);
  $("#calGrid").html(LOADING);
  const days=await loadCalYear(cal.y);
  const start=(new Date(cal.y,cal.m,1).getDay()+6)%7; // 周一为第一列
  const total=new Date(cal.y,cal.m+1,0).getDate();
  const cur=$("#"+cal.target).val()||"";
  const tdy=new Date();
  let html="";
  for(let i=0;i<start;i++)html+=`<span></span>`;
  for(let d=1;d<=total;d++){
    const ds=`${cal.y}-${pad2(cal.m+1)}-${pad2(d)}`;
    const wd=new Date(cal.y,cal.m,d).getDay();
    // 降级: 日历数据缺失时仅按周末判断
    const info=days[pad2(cal.m+1)+"-"+pad2(d)]||{t:wd!==0&&wd!==6,h:""};
    let cls="day";
    if(info.t){if(info.h)cls+=" make"}else{cls+=info.h?" hol":" off"}
    if(ds===cur)cls+=" sel";
    if(ds===fmtD(tdy))cls+=" today";
    const hl=!info.t&&info.h?`<span class="hl">${esc(info.h)}</span>`:"";
    const mk=info.t&&info.h?`<i class="mk"></i>`:"";
    const act=info.t?`onclick="pickDay('${ds}')"`:"";
    const tip=info.h?` title="${esc(info.h)}${info.t?"(调休开市)":"(休市)"}"`:"";
    html+=`<span class="${cls}"${act}${tip}>${d}${hl}${mk}</span>`;
  }
  $("#calGrid").html(html);
}

function pickDay(ds){
  const id=cal.target;
  $("#"+id).val(ds);
  closeCal();
  const fn=DATE_RELOAD[id];
  if(fn)fn();
}

async function calMonth(delta){
  cal.m+=delta;
  while(cal.m<0){cal.m+=12;cal.y--}
  while(cal.m>11){cal.m-=12;cal.y++}
  await renderCal();
}

async function calLatest(){
  const d=new Date((cal.latest||fmtD(new Date()))+"T00:00:00");
  cal.y=d.getFullYear();cal.m=d.getMonth();
  await renderCal();
  pickDay(cal.latest);
}

async function setDates(){
  await loadCalYear(new Date().getFullYear());
  let latest=cal.latest||"";
  if(!latest){  // 降级: 日历接口不可用时周末回退
    const d=new Date();
    while(d.getDay()===0||d.getDay()===6)d.setDate(d.getDate()-1);
    latest=fmtD(d);
  }
  const prev=cal.prev||latest;
  $("#luDate").val(latest);$("#ztDate").val(latest);$("#zbDate").val(latest);
  $("#dtDate").val(latest);$("#dsDate").val(latest);$("#bkDate").val(latest);
  $("#zrDate").val(latest);$("#rvDate").val(latest);$("#drDate").val(latest);
  $("#lyDate").val(latest);$("#pmDate").val(latest);
  $("#lhbDate").val(prev);
}
