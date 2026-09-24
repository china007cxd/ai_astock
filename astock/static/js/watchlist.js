/* ============ 自选股: 搜索联想 + 自选列表 ============ */
"use strict";

const WL_KEY="astock_watchlist";
let wlTimer=null,wlSel=-1,wlResults=[];

function watchList(){
  try{const a=JSON.parse(localStorage.getItem(WL_KEY)||"[]");return Array.isArray(a)?a:[]}
  catch(e){return[]}
}
function saveWatchList(a){localStorage.setItem(WL_KEY,JSON.stringify(a))}

/* ---------- 搜索联想(代码/名称/拼音首字母) ---------- */
function wlInput(){
  clearTimeout(wlTimer);
  const q=$("#wlSearch").val().trim();
  if(!q){$("#wlDrop").removeClass("show");wlResults=[];return}
  wlTimer=setTimeout(async()=>{
    try{
      const j=await api("search",{q});
      wlResults=j.rows||[];
      renderWlDrop();
    }catch(e){}
  },250);
}

function renderWlDrop(){
  wlSel=-1;
  if(!wlResults.length){
    $("#wlDrop").html('<div class="s-empty">无匹配股票</div>').addClass("show");
    return;
  }
  $("#wlDrop").html(wlResults.map((r,i)=>`<div class="s-item" data-i="${i}" data-code="${esc(r.code)}">
    <span class="s-name">${esc(r.name)}</span>
    <span class="s-py">${esc(r.py)}</span>
    <span class="s-code">${esc(r.code)}</span></div>`).join("")).addClass("show");
  $("#wlDrop .s-item").on("click",function(){
    const d=$(this);
    addWatch(d.data("code"),d.find(".s-name").text());
  });
}

function markSel(){
  $("#wlDrop .s-item").removeClass("sel");
  const it=$("#wlDrop .s-item").eq(wlSel);
  if(it.length)it.addClass("sel");
}

function addWatch(code,name){
  code=stockCode(code);
  if(!code)return;
  const list=watchList();
  if(!list.includes(code)){list.unshift(code);saveWatchList(list)}
  $("#wlSearch").val("");
  $("#wlDrop").removeClass("show");
  wlResults=[];
  if(curTab==="watchlist")loadWatchlist();
  openKline(code,name||code);
}

/* ---------- 自选列表(行情实时刷新, 行点击弹K线) ---------- */
async function loadWatchlist(){
  const el=$("#wlTblWrap");
  const list=watchList();
  if(!list.length){
    show(el,`<div class="empty"><i class="bi bi-star"></i>暂无自选，在上方搜索框输入代码/名称/拼音首字母添加</div>`);
    return;
  }
  show(el,LOADING);
  try{
    const j=await api("quotes",{codes:list.join(",")});
    const rows=j.rows||[];
    let html=`<table><thead><tr><th style="text-align:left">#</th><th style="text-align:left">代码</th>
      <th style="text-align:left">名称</th><th>现价</th><th>涨跌幅</th><th>操作</th></tr></thead><tbody>`;
    rows.forEach((r,i)=>{
      const cls=colorOf(r.pct);
      html+=`<tr data-code="${esc(r.code)}"><td class="dim">${i+1}</td>
        <td class="dim">${esc(r.code)}</td><td><b>${esc(r.name)}</b></td>
        <td class="${cls}">${esc(r.price)}</td><td class="${cls}">${pct(Number(r.pct))}</td>
        <td><button class="btn mini del" data-code="${esc(r.code)}" title="移出自选"><i class="bi bi-trash"></i></button></td></tr>`;
    });
    html+=`</tbody></table>`;
    show(el,html);
    el.find("tbody tr").on("click",function(){
      const tr=$(this);
      const code=tr.data("code");
      if(!code)return;
      openKline(code,tr.find("td b").text());
    });
    el.find("button.del").on("click",function(e){
      e.stopPropagation();
      const code=$(this).data("code");
      saveWatchList(watchList().filter(c=>c!==code));
      loadWatchlist();
    });
    $("#wlHint").text(`共 ${rows.length} 只自选 · 更新 ${new Date().toLocaleTimeString()}`);
  }catch(e){errBox(el,e)}
}

/* ---------- 键盘交互 ---------- */
$(function(){
  $("#wlSearch").on("input",wlInput);
  $("#wlSearch").on("keydown",function(e){
    if(e.key==="ArrowDown"){wlSel=Math.min(wlSel+1,wlResults.length-1);markSel();e.preventDefault()}
    else if(e.key==="ArrowUp"){wlSel=Math.max(wlSel-1,0);markSel();e.preventDefault()}
    else if(e.key==="Enter"){
      if(wlSel>=0&&wlResults[wlSel])addWatch(wlResults[wlSel].code,wlResults[wlSel].name);
      else{
        const q=$("#wlSearch").val().trim();
        if(/^\d{6}$/.test(q))addWatch(q,q);
      }
    }
    else if(e.key==="Escape"){$("#wlDrop").removeClass("show")}
  });
  $(document).on("click",function(e){
    if(!$(e.target).closest(".search-wrap").length)$("#wlDrop").removeClass("show");
  });
});

LOADERS.watchlist=loadWatchlist;
