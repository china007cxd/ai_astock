/* ============ 面板加载器(13个) ============ */
"use strict";

let curTab="indices";
let dsState={type:1,page:1,size:60,date:""};
let mkState={sort:"f3",page:1,size:50,pages:1};
let loaded={};

const LOADERS={indices:loadIndices,duishu:loadDuishu,limitup:loadLimitUp,ztpool:loadZtPool,
  zbpool:loadZbPool,dtpool:loadDtPool,broken:loadBroken,ladder:loadLadder,hotplate:loadHotPlate,
  flow:loadFlow,lhb:loadLhb,bidding:loadBidding,news:loadNews,
  hotstock:loadHotStock,longyi:loadLongYi,fengkou:loadFengKou,
  ztreason:loadZtReason,ztreview:loadZtReview,dragon:loadDragon,
  nearzt:loadNearZt,topiccycle:loadTopicCycle,topictl:loadTopicTl,
  panmian:loadPanMian,flowcn:loadFlowCn,
  emxg:loadEmXuangu,wencai:loadWenCai,themeinv:loadThemeInv,
  market:loadMarket};

function switchTab(k){
  curTab=k;
  $("#tabs button").removeClass("active").filter(`[data-k="${k}"]`).addClass("active");
  $(".panel").removeClass("active");
  $("#pn-"+k).addClass("active");
  if(!loaded[k]){loaded[k]=1;LOADERS[k]().catch(e=>{})}
}

/* ---------- 大盘指数 ---------- */
async function loadIndices(){
  const el=$("#idxCards");
  try{
    const j=await api("indices");
    show(el,j.items.map(it=>{
      const cls=colorOf(it.pct);
      return `<div class="card"><div class="nm">${esc(it.name)}</div>
        <div class="pr ${cls}">${esc(it.price)}</div>
        <div class="ch ${cls}">${esc(it.change)}  ${esc(it.pct)}%</div></div>`;
    }).join(""));
    show($("#idxUpDown"),`<div class="item">上涨家数 <b class="up">${esc(j.up)}</b></div>
      <div class="item">下跌家数 <b class="down">${esc(j.down)}</b></div>
      <div class="item">平盘家数 <b class="flat">${esc(j.flat)}</b></div>
      <div class="item">更新时间 <b>${esc(j.time)}</b></div>`);
    loadLadderInner();
  }catch(e){errBox(el,e)}
}

/* ---------- 连板梯队 ---------- */
async function loadLadder(){
  try{
    const j=await api("ladder");
    fillLadder(j,"#ldStats","#ldLadder","#ldPlates","#ldPlateTitle");
  }catch(e){errBox($("#ldLadder"),e)}
}
async function loadLadderInner(){
  try{
    const j=await api("ladder");
    fillLadder(j,null,"#idxLadder","#idxPlates","#plateTitle");
  }catch(e){}
}
function fillLadder(j,sId,lId,pId,tId){
  if(sId){
    show($(sId),`<div class="item">连板涨停 <b class="up">${esc(j.limit_up)}</b></div>
      <div class="item">更新时间 <b>${esc(j.time)}</b></div>`);
  }
  if(j.ladder&&j.ladder.length){
    show($(lId),j.ladder.map(g=>{
      const hd=g.height>=4?`<span class="tag hot">高标</span>`:"";
      return `<div class="col"><div class="hd">${g.height}板${hd}</div>
        ${g.stocks.map(s=>`<div class="s" data-code="${esc(s.code)}">${esc(s.name)}<br><span class="dim" style="font-size:11px">${esc(s.code)}</span></div>`).join("")}
      </div>`;
    }).join(""));
    $(lId).find(".s").on("click",function(){
      const d=$(this);
      const nm=d.text().split("\n")[0].trim();
      openKline(stockCode(d.data("code")),nm);
    });
  }else{show($(lId),EMPTY+"暂无连板梯队数据</div>")}
  if(j.plates&&j.plates.length){
    $(tId).text(`板块涨停 (${j.plates.length} 个板块)`);
    renderTable($(pId),[
      {k:"name",label:"板块"},
      {k:"up_num",label:"涨停数",cls:r=>"up"},
      {k:"change",label:"板块涨幅",color:"pct"},
      {k:"reason",label:"上涨原因"},
      {k:"stocks",label:"涨停个股",fmt:(v)=> (v||[]).map(s=>`<span class="tag hot" data-code="${esc(s.code)}">${esc(s.name)}</span>`).join(" "),rowClick:false},
    ],j.plates,{rowClick:false});
    $(pId).find("td .tag").on("click",function(e){
      e.stopPropagation();
      const t=$(this);
      openKline(stockCode(t.data("code")),t.text().trim());
    });
  }else{show($(pId),EMPTY+"暂无板块涨停数据</div>")}
}

/* ---------- 盯盘 ---------- */
async function loadDuishu(){
  return dsLoad();
}
function dsSetType(t){dsState.type=t;dsState.page=1;dsLoad()}
function dsPage(d){dsState.page=Math.max(1,dsState.page+d);dsLoad()}
async function dsLoad(){
  const el=$("#dsTblWrap");
  $("#dsPrev").prop("disabled",true);$("#dsNext").prop("disabled",true);
  show(el,LOADING);
  try{
    const j=await api("duishu",{type:dsState.type,page:dsState.page,size:dsState.size,date:dsState.date});
    $("#dsHint").text(`${j.title} · 数据日期 ${j.date||"-"}`);
    show($("#dsStats"),(j.sum_list||[]).map(s=>`<div class="item">${esc(s.t)}<br><b>${esc(s.n1)}</b>
      <span class="dim">/昨 ${esc(s.n2)}</span>
      ${s.p!=null?`<span class="${String(s.p).startsWith("-")?"down":"up"}">${esc(s.p)}</span>`:""}</div>`).join(""));
    show($("#dsFeed"),(j.baopan||[]).map(b=>`<div class="f"><b>${esc((b.title||"").split("】")[0])}】</b>${esc((b.title||"").split("】")[1]||"")}</div>`).join(""));
    const tabs=j.tab_list||[];
    $("#dsSubTabs").html(tabs.map(t=>`<button class="btn mini ${t.type==dsState.type?"on":""}" onclick="dsSetType(${t.type})">${esc(t.t)}</button>`).join(""));
    renderDuishu(j.stock_list||{});
    $("#dsPageInfo").text(`第 ${dsState.page} 页`);
    $("#dsPrev").prop("disabled",dsState.page<=1);
    $("#dsNext").prop("disabled",(j.stock_list.list||[]).length<dsState.size);
  }catch(e){
    errBox(el,e);
    $("#dsPrev").prop("disabled",false);$("#dsNext").prop("disabled",false);
  }
}
function renderDuishu(sl){
  const el=$("#dsTblWrap");
  const heads=sl.head_info||[];
  const rows=sl.list||[];
  if(!rows.length){show(el,EMPTY+"</div>");return}
  let html=`<table><thead><tr><th style="text-align:left">#</th>`;
  heads.forEach(h=>{html+=`<th>${esc(h.text)}</th>`});
  html+=`</tr></thead><tbody>`;
  rows.forEach((row,i)=>{
    html+=`<tr><td class="dim">${i+1}</td>`;
    row.forEach(cell=>{
      const cls=cell.color===1?"up":cell.color===2?"down":"";
      const bold=cell.bold?' style="font-weight:700"':"";
      const remark=cell.remark?` title="${esc(cell.remark.replace(/<[^>]*>/g,""))}"`:"";
      const code=stockCode(cell.text)||stockCode(cell.rank);
      html+=`<td class="${cls}"${bold}${remark} data-code="${esc(code||"")}">${esc(cell.text)}</td>`;
    });
    html+=`</tr>`;
  });
  html+=`</tbody></table>`;
  show(el,html);
  el.find("tbody tr").on("click",function(){
    const td=$(this).find("td[data-code]");
    if(!td.length||!td.data("code"))return;
    openKline(td.data("code"),td.text().split("#")[0]);
  });
}

/* ---------- 涨停板(同花顺) ---------- */
async function loadLimitUp(){
  const el=$("#luTblWrap"),d=$("#luDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("limit_up",{date:d});
    $("#luHint").text(`数据日期 ${j.date} · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"high_days",label:"连板"},
      {k:"ltype",label:"涨停类型"},
      {k:"first_time",label:"首次涨停",fmt:tsToTime},
      {k:"last_time",label:"最后封板",fmt:tsToTime},
      {k:"amount",label:"封单额",sortKey:"order_amount",fmt:amt,cls:r=>"up"},
      {k:"reason",label:"涨停原因"},
      {k:"pct",label:"涨幅",color:"pct",sortKey:"pct"},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%",sortKey:"turnover"},
      {k:"value",label:"流通值",sortKey:"currency_value",fmt:(v)=>esc(v)},
      {k:"suc_rate",label:"涨停成功率",fmt:(v)=>v==null?"-":(v*100).toFixed(0)+"%",sortKey:"suc_rate"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 涨停池(东财) ---------- */
async function loadZtPool(){
  const el=$("#ztTblWrap"),d=$("#ztDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("zt_pool",{date:d});
    $("#ztHint").text(`数据日期 ${j.date} · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价",fmt:emPrice},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"lianban",label:"连板",cls:r=>r.lianban>1?"up":""},
      {k:"first_time",label:"首次封板",fmt:tsToTime},
      {k:"last_time",label:"最后封板",fmt:tsToTime},
      {k:"fund",label:"封单资金",cls:r=>"up"},
      {k:"zhaban",label:"炸板次数"},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%"},
      {k:"amount",label:"成交额"},
      {k:"float_value",label:"流通市值"},
      {k:"industry",label:"所属行业"},
      {k:"days",label:"N天M板",fmt:(v,r)=>r.days&&r.count?`${r.days}天${r.count}板`:"-"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 炸板池(东财) ---------- */
async function loadZbPool(){
  const el=$("#zbTblWrap"),d=$("#zbDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("zb_pool",{date:d});
    $("#zbHint").text(`数据日期 ${j.date} · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价",fmt:emPrice},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"limit_price",label:"涨停价",fmt:emPrice},
      {k:"first_time",label:"首次涨停",fmt:tsToTime},
      {k:"last_time",label:"最后涨停",fmt:tsToTime},
      {k:"break_time",label:"首次炸板",fmt:tsToTime},
      {k:"break_count",label:"炸板次数",cls:r=>"down"},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%"},
      {k:"amount",label:"成交额"},
      {k:"float_value",label:"流通市值"},
      {k:"industry",label:"所属行业"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 跌停板(东财) ---------- */
async function loadDtPool(){
  const el=$("#dtTblWrap"),d=$("#dtDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("dt_pool",{date:d});
    $("#dtHint").text(`数据日期 ${j.date} · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价",fmt:emPrice},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"lianban",label:"连板"},
      {k:"first_time",label:"首次跌停",fmt:tsToTime},
      {k:"last_time",label:"最后封死",fmt:tsToTime},
      {k:"fund",label:"封单资金"},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%"},
      {k:"amount",label:"成交额"},
      {k:"float_value",label:"流通市值"},
      {k:"industry",label:"所属行业"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 破板(选股宝: 昨日涨停今日破板) ---------- */
async function loadBroken(){
  const el=$("#bkTblWrap"),d=$("#bkDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("xgb_broken",{date:d});
    $("#bkHint").text(`数据日期 ${j.date} · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"high_days",label:"连板"},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"break_times",label:"炸板次数",cls:r=>"down"},
      {k:"break_time",label:"炸板时间",fmt:tsToTime},
      {k:"first_time",label:"首次涨停",fmt:tsToTime},
      {k:"last_time",label:"最后涨停",fmt:tsToTime},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%"},
      {k:"reason",label:"上涨原因"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 热门板块 ---------- */
async function loadHotPlate(){
  const el=$("#hpTblWrap");
  try{
    const j=await api("hot_plate");
    renderTable(el,[
      {k:"order",label:"排名",sortKey:"order"},
      {k:"name",label:"板块"},
      {k:"code",label:"代码"},
      {k:"rate",label:"热度",fmt:amt,cls:r=>"up"},
      {k:"tag",label:"涨停家数",cls:r=>"up"},
      {k:"hot_tag",label:"上榜"},
      {k:"etf",label:"相关ETF"},
    ],j.rows,{rowClick:false});
  }catch(e){errBox(el,e)}
}

/* ---------- 资金流 ---------- */
async function loadFlow(){
  const el=$("#flTblWrap");
  try{
    const j=await api("plate_flow");
    $("#flHint").text(`行业板块主力资金流 · 更新 ${j.time}`);
    renderTable(el,[
      {k:"name",label:"板块"},
      {k:"code",label:"代码"},
      {k:"price",label:"点位"},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"main_net",label:"主力净流入",fmt:amt,cls:r=>colorOf(r.main_net),sortKey:"main_net"},
      {k:"main_pct",label:"主力净占比",fmt:pct,color:"pct"},
      {k:"xl_net",label:"超大单净额",fmt:amt,cls:r=>colorOf(r.xl_net),sortKey:"xl_net"},
      {k:"xl_pct",label:"超大单占比",fmt:pct,color:"pct"},
      {k:"big_net",label:"大单净额",fmt:amt,cls:r=>colorOf(r.big_net),sortKey:"big_net"},
      {k:"big_pct",label:"大单占比",fmt:pct,color:"pct"},
      {k:"mid_net",label:"中单净额",fmt:amt,cls:r=>colorOf(r.mid_net),sortKey:"mid_net"},
      {k:"small_net",label:"小单净额",fmt:amt,cls:r=>colorOf(r.small_net),sortKey:"small_net"},
    ],j.rows,{rowClick:false});
  }catch(e){errBox(el,e)}
}

/* ---------- 龙虎榜 ---------- */
async function loadLhb(){
  const el=$("#lhbTblWrap"),d=$("#lhbDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("lhb",{date:d});
    $("#lhbHint").text(`数据日期 ${j.date} · 共 ${j.rows.length} 只`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"pct",label:"涨幅",color:"pct"},
      {k:"buy_in",label:"净买额",cls:r=>"up"},
      {k:"join_num",label:"上榜席位"},
      {k:"turnover",label:"成交额"},
      {k:"circ_value",label:"流通市值"},
      {k:"amplitude",label:"振幅",fmt:(v)=>v==null?"-":v+"%"},
      {k:"turnover_ratio",label:"换手率",fmt:(v)=>v==null?"-":v+"%"},
      {k:"reason",label:"原因"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 竞价封单 ---------- */
async function loadBidding(){
  const el=$("#bdTblWrap");
  try{
    const j=await api("bidding");
    show($("#bdStats"),`<div class="item">数据日期 <b>${esc(j.date)}</b></div>
      <div class="item">9:15总封单 <b class="up">${esc(j.t15)}</b></div>
      <div class="item">9:20总封单 <b class="up">${esc(j.t20)}</b></div>
      <div class="item">9:25总封单 <b class="up">${esc(j.t25)}</b></div>`);
    let html=`<table><thead><tr><th style="text-align:left">#</th><th style="text-align:left">股票</th>
      <th style="text-align:left">题材</th><th>9:15封单</th><th>9:20封单</th><th>9:25封单</th></tr></thead><tbody>`;
    j.rows.forEach((r,i)=>{
      html+=`<tr data-code="${esc(stockCode(r.code))}"><td class="dim">${i+1}</td>
        <td><b>${esc(r.name)}</b> <span class="dim">${esc(r.code)}</span></td>
        <td style="text-align:left">${(r.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join(" ")}</td>
        <td class="up">${esc(r.amounts[0]||"-")}</td>
        <td class="up">${esc(r.amounts[1]||"-")}</td>
        <td class="up">${esc(r.amounts[2]||"-")}</td></tr>`;
    });
    html+=`</tbody></table>`;
    show(el,j.rows.length?html:`<div class="empty"><i class="bi bi-hourglass"></i>暂无数据(收盘后发布次日竞价封单)</div>`);
    el.find("tbody tr").on("click",function(){
      const tr=$(this);
      const code=tr.data("code");
      if(!code)return;
      openKline(code,tr.find("td b").text());
    });
  }catch(e){errBox(el,e)}
}

/* ---------- 快讯 ---------- */
async function loadNews(){
  const el=$("#nwTblWrap");
  try{
    const j=await api("news");
    let html=`<table><thead><tr><th style="text-align:left">时间</th><th style="text-align:left">内容</th></tr></thead><tbody>`;
    j.rows.forEach((n,i)=>{
      html+=`<tr class="nw-row" data-idx="${i}"><td class="dim" style="vertical-align:top">${esc(n.time)}</td>
        <td style="white-space:normal;text-align:left">${esc(n.title||n.summary)}</td></tr>`;
    });
    html+=`</tbody></table>`;
    show(el,html);
  }catch(e){errBox(el,e)}
}

/* ---------- 人气榜(同花顺热榜) ---------- */
async function loadHotStock(){
  const el=$("#hsTblWrap");
  show(el,LOADING);
  try{
    const j=await api("hot_stock");
    $("#hsHint").text(`同花顺热门个股人气榜 · 共 ${j.total} 只`);
    renderTable(el,[
      {k:"order",label:"排名"},
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价",fmt:(v)=>v==null?"-":num(v)},
      {k:"pct",label:"涨幅",color:"pct"},
      {k:"rate",label:"热度",cls:r=>"up",
        fmt:(v,r)=>{const n=Number(v);const t=isNaN(n)?"-":(n>=1e4?(n/1e4).toFixed(1)+"万":n.toFixed(0));
          return t+(r.rank_chg>0?`<span class="up"> ↑${esc(r.rank_chg)}</span>`:(r.rank_chg<0?`<span class="down"> ↓${esc(-r.rank_chg)}</span>`:""))}},
      {k:"tags",label:"概念标签",fmt:(v)=> (v||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join(" "),rowClick:false},
      {k:"pop",label:"人气",fmt:(v)=> v?`<span class="tag hot">${esc(v)}</span>`:"",rowClick:false},
      {k:"analyse",label:"上榜原因",fmt:(v)=> {const s=String(v||"");return `<span title="${esc(s)}">${esc(s.length>22?s.slice(0,22)+"…":s)}</span>`}},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 今日龙一 ---------- */
async function loadLongYi(){
  const d=$("#lyDate").val()||"";
  show($("#lyCards"),LOADING);
  try{
    const j=await api("longyi",{date:d});
    const ly=j.longyi;
    $("#lyHint").text(`数据日期 ${j.date}`);
    if(ly){
      show($("#lyCards"),`<div class="card hero" data-code="${esc(stockCode(ly.code))}">
        <div class="nm"><i class="bi bi-trophy-fill" style="color:var(--yellow)"></i>今日龙一 · 最早封板</div>
        <div class="pr up">${esc(ly.name)}</div>
        <div class="ch">${esc(ly.code)} · ${esc(ly.high_days||"首板")} · 首封 ${esc(tsToTime(ly.first_time))}
          ${ly.pct!=null?` · 涨幅 <span class="up">${esc(ly.pct)}%</span>`:""}</div>
        <div class="ch">${esc(ly.reason||"")}</div>
      </div>`);
      $("#lyCards .hero").on("click",function(){
        openKline(stockCode($(this).data("code")),$("#lyCards .pr").text());
      });
    }else{show($("#lyCards"),EMPTY+"暂无涨停数据</div>")}
    renderTable($("#lyFirst"),[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"high_days",label:"连板",cls:r=>(r.high_days&&r.high_days!=="首板")?"up":""},
      {k:"first_time",label:"首封时间",fmt:tsToTime},
      {k:"reason",label:"涨停原因"},
    ],j.first_10);
    renderTable($("#lyTop"),[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"high_days",label:"连板",cls:r=>"up"},
      {k:"first_time",label:"首封时间",fmt:tsToTime},
      {k:"reason",label:"涨停原因"},
    ],j.top_boards);
  }catch(e){errBox($("#lyCards"),e)}
}

/* ---------- 最强风口 ---------- */
async function loadFengKou(){
  const el=$("#fkCards");
  show(el,LOADING);
  try{
    const j=await api("fengkou");
    $("#fkHint").text(`同花顺热门概念板块热度榜 · 共 ${j.total} 个`);
    if(!j.rows||!j.rows.length){show(el,EMPTY+"暂无风口数据</div>");return}
    show(el,j.rows.map(r=>{
      const chg=r.hot_rank_chg;
      let chgHtml="";
      if(chg>0)chgHtml=`<span class="up">▲${esc(chg)}</span>`;
      else if(chg<0)chgHtml=`<span class="down">▼${esc(-chg)}</span>`;
      else chgHtml=`<span class="dim">—</span>`;
      return `<div class="card"><div class="nm">#${esc(r.order)} ${chgHtml}</div>
        <div class="pr up" style="font-size:17px">${esc(r.name)}</div>
        <div class="ch">热度 ${esc(amt(r.rate))} <span class="tag hot">${esc(r.tag||"")}</span></div></div>`;
    }).join(""));
  }catch(e){errBox(el,e)}
}

/* ---------- 涨停原因 ---------- */
async function loadZtReason(){
  const el=$("#zrGroups"),d=$("#zrDate").val()||"";
  show(el,LOADING);
  try{
    const j=await api("zt_reason",{date:d});
    $("#zrHint").text(`数据日期 ${j.date} · 涨停 ${j.total} 只 · ${j.rows.length} 个原因方向`);
    if(!j.rows||!j.rows.length){show(el,EMPTY+"暂无数据</div>");return}
    show(el,j.rows.map(g=>{
      const stocks=(g.stocks||[]).map(s=>{
        const lb=s.days&&s.days!=="首板"&&s.days!=="1板"&&String(s.days).indexOf("板")>-1
          ?`<b class="lb">${esc(s.days)}</b>`:"";
        return `<span class="tagchip" data-code="${esc(s.code)}" data-name="${esc(s.name)}"
          title="${esc(s.code)} 首封 ${esc(tsToTime(s.time))}">${esc(s.name)}${lb}</span>`;
      }).join("");
      return `<div class="zr-group">
        <div class="zr-hd"><span class="zr-name">${esc(g.reason)}</span>
          <span class="tag hot">${esc(g.count)}只</span>
          ${g.max_days>1?`<span class="tag">最高${esc(g.max_days)}板</span>`:""}</div>
        <div class="zr-stocks">${stocks}</div>
      </div>`;
    }).join(""));
    el.find(".tagchip").on("click",function(){
      const t=$(this);
      openKline(stockCode(t.data("code")),t.data("name"));
    });
  }catch(e){errBox(el,e)}
}

/* ---------- 涨停复盘图 ---------- */
async function loadZtReview(){
  const d=$("#rvDate").val()||"";
  show($("#rvStats"),LOADING);
  try{
    const j=await api("zt_review",{date:d});
    const pyr=j.pyramid||[];
    const maxDays=pyr.length?pyr[0].days:1;
    const seal=j.total?Math.round((j.total-j.broken)/j.total*100):0;
    $("#rvHint").text(`数据日期 ${j.date}`);
    show($("#rvStats"),[
      `<div class="item">涨停总数<br><b class="up">${esc(j.total)}</b></div>`,
      `<div class="item">炸板数<br><b class="down">${esc(j.broken)}</b></div>`,
      `<div class="item">封板率<br><b>${esc(seal)}%</b></div>`,
      `<div class="item">最高连板<br><b class="up">${esc(maxDays)}板</b></div>`,
      `<div class="item">梯队分布<br><b>${esc(pyr.map(p=>p.days+"板×"+p.count).join(" "))}</b></div>`,
    ].join(""));
    drawZtTimeline(j.timeline||[]);
    drawZtPyramid(j.pyramid||[]);
  }catch(e){errBox($("#rvStats"),e)}
}
function ztChartInit(id){
  const el=document.getElementById(id);
  if(!el)return null;
  let ch=echarts.getInstanceByDom(el);
  if(ch)ch.dispose();
  return echarts.init(el);
}
function drawZtTimeline(tl){
  const ch=ztChartInit("rvTimeline");
  if(!ch)return;
  if(!tl.length){ch.clear();return}
  ch.setOption({
    backgroundColor:"transparent",
    grid:{left:44,right:14,top:26,bottom:46},
    tooltip:{trigger:"axis",formatter:p=>`${p[0].axisValue}<br/><b>${p[0].value}</b> 只涨停`},
    xAxis:{type:"category",data:tl.map(t=>t.time),axisLabel:{color:"#8b93a1",fontSize:10,rotate:45},
      axisLine:{lineStyle:{color:"#2e3440"}},axisTick:{show:false}},
    yAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"#22262e"}},axisLabel:{color:"#8b93a1"}},
    series:[{name:"涨停家数",type:"bar",data:tl.map(t=>t.count),barMaxWidth:22,
      itemStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[
        {offset:0,color:"#e23d3d"},{offset:1,color:"#6b1f1f"}]),borderRadius:[3,3,0,0]}}],
  });
}
function drawZtPyramid(py){
  const ch=ztChartInit("rvPyramid");
  if(!ch)return;
  if(!py.length){ch.clear();return}
  const data=py.slice().reverse();           // 1板在底部
  const colors=["#5a6270","#5a6270","#8a7a3a","#e8c24a","#e07030","#e23d3d"];  // 低→高
  ch.setOption({
    backgroundColor:"transparent",
    grid:{left:64,right:46,top:14,bottom:24},
    tooltip:{trigger:"axis",axisPointer:{type:"shadow"},formatter:p=>`${p[0].name}<br/><b>${p[0].value}</b> 只`},
    xAxis:{type:"value",minInterval:1,splitLine:{lineStyle:{color:"#22262e"}},axisLabel:{color:"#8b93a1"}},
    yAxis:{type:"category",data:data.map(t=>t.days+"板"),axisLabel:{color:"#d8dce3",fontSize:11},
      axisLine:{lineStyle:{color:"#2e3440"}},axisTick:{show:false}},
    series:[{type:"bar",data:data.map(t=>t.count),barMaxWidth:26,
      label:{show:true,position:"right",color:"#e8c24a",fontSize:11},
      itemStyle:{color:p=>colors[Math.min(p.dataIndex,colors.length-1)],borderRadius:[0,3,3,0]}}],
  });
}

/* ---------- 龙头晋级 ---------- */
async function loadDragon(){
  const d=$("#drDate").val()||"";
  show($("#drStats"),LOADING);
  try{
    const j=await api("dragon",{date:d});
    const rate=j.y_total?Math.round(j.promote_total/j.y_total*100):0;
    $("#drHint").text(`${j.yesterday} 涨停 ${j.y_total} 只 → ${j.date} 表现`);
    show($("#drStats"),[
      `<div class="item">昨日涨停<br><b>${esc(j.y_total)}</b></div>`,
      `<div class="item">晋级<br><b class="up">${esc(j.promote_total)}</b></div>`,
      `<div class="item">晋级率<br><b class="${rate>=50?"up":rate>=25?"flat":"down"}">${esc(rate)}%</b></div>`,
      `<div class="item">断板<br><b class="down">${esc(j.broken.length)}</b></div>`,
      `<div class="item">新晋涨停<br><b class="up">${esc(j.new_boards.length)}</b></div>`,
    ].join(""));
    renderTable($("#drPromote"),[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"ydays",label:"昨日连板"},
      {k:"tdays",label:"今日连板",cls:r=>"up"},
      {k:"reason",label:"涨停原因"},
    ],j.promoted);
    renderTable($("#drBroken"),[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"ydays",label:"昨日连板"},
      {k:"pct",label:"今日涨幅",color:"pct"},
      {k:"reason",label:"原因"},
    ],j.broken);
    renderTable($("#drNew"),[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"days",label:"连板",cls:r=>(r.days&&r.days!=="首板")?"up":""},
      {k:"reason",label:"涨停原因"},
    ],j.new_boards);
  }catch(e){errBox($("#drStats"),e)}
}

/* ---------- 即将涨停 ---------- */
async function loadNearZt(){
  const el=$("#nzTblWrap");
  show(el,LOADING);
  try{
    const j=await api("near_zt");
    $("#nzHint").text(`涨幅7%以上逼近涨停个股 · 共 ${j.total} 只 · 更新 ${j.time}`);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价"},
      {k:"pct",label:"涨幅",color:"pct"},
      {k:"turnover",label:"换手",fmt:(v)=>v==null?"-":Number(v).toFixed(2)+"%"},
      {k:"vol_ratio",label:"量比"},
      {k:"main_net",label:"主力净流入",cls:r=>r.main_net&&String(r.main_net).indexOf("-")>-1?"down":"up"},
      {k:"amount",label:"成交额"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 题材周期表/时间线 ---------- */
const TOPIC_STAGE={0:"观察期",1:"启动期",2:"发酵期",3:"高潮期"};
function topicItemHtml(it){
  const hot=Number(it.hot)||0;
  const hotTxt=hot>=10000?(hot/10000).toFixed(1)+"万":hot;
  return `<div class="t-item" data-id="${esc(it.id)}" title="点击查看题材详情">
    <span class="t-title">${esc(it.title)}</span>
    <span class="t-hot" title="热度">${esc(hotTxt)}</span>
    ${it.new?`<span class="tag hot">新</span>`:""}
  </div>`;
}
async function loadTopicCycle(){
  const el=$("#tcCols");
  show(el,LOADING);
  try{
    const j=await api("topic_list");
    if(!j.days||!j.days.length){show(el,EMPTY+"暂无题材数据</div>");return}
    const latest=j.days[0];
    $("#tcHint").text(`龙虎VIP 题材热度周期表 · ${esc(latest.day)} · 共 ${latest.items.length} 个题材`);
    const cols={0:[],1:[],2:[],3:[]};
    latest.items.forEach(it=>{
      const t=Math.max(0,Math.min(3,Number(it.hot_tag)||0));
      cols[t].push(it);
    });
    show(el,[0,1,2,3].map(t=>{
      const items=cols[t].sort((a,b)=>(Number(b.hot)||0)-(Number(a.hot)||0));
      return `<div class="tc-col st${t}"><div class="tc-hd">${TOPIC_STAGE[t]}<span class="tc-n">${items.length}</span></div>
        <div class="tc-list">${items.length?items.map(topicItemHtml).join(""):`<div class="dim" style="padding:10px;text-align:center">暂无</div>`}</div>
      </div>`;
    }).join(""));
    el.find(".t-item").on("click",function(){openTopic($(this).data("id"))});
  }catch(e){errBox(el,e)}
}
async function loadTopicTl(){
  const el=$("#ttWrap");
  show(el,LOADING);
  try{
    const j=await api("topic_list");
    if(!j.days||!j.days.length){show(el,EMPTY+"暂无题材数据</div>");return}
    $("#ttHint").text(`龙虎VIP 热门题材时间线 · 近 ${j.days.length} 天 · 点击题材查看详情`);
    show(el,j.days.map((dg,i)=>`<div class="tl-day">
      <div class="tl-dot${i===0?" now":""}"></div>
      <div class="tl-date">${esc(dg.day)}</div>
      <div class="tl-items">${dg.items.map(topicItemHtml).join("")}</div>
    </div>`).join(""));
    el.find(".t-item").on("click",function(){openTopic($(this).data("id"))});
  }catch(e){errBox(el,e)}
}
async function openTopic(id){
  $("#tpMask").addClass("show");
  $("#tpTitle").text("--");
  show($("#tpBody"),LOADING);
  try{
    const j=await api("topic_detail",{id:id});
    $("#tpTitle").text(j.title||"题材详情");
    const html=String(j.content||"").replace(/\r?\n/g,"<br>").replace(/\r/g,"");
    show($("#tpBody"),html||"暂无内容");
  }catch(e){errBox($("#tpBody"),e)}
}
function closeTopic(){$("#tpMask").removeClass("show")}

/* ---------- 盘面梳理(原版: 盘面亮点) ---------- */
const PM_LEVEL_CLS={高潮:"pm-lv0",回暖:"pm-lv1",修复:"pm-lv2",低迷:"pm-lv3",冰点:"pm-lv4"};
function pmAmt(v){ /* 元 -> 万/亿/万亿(与原版单位一致) */
  if(v==null||isNaN(v))return "-";
  if(v>=1e12)return (v/1e12).toFixed(2)+"万亿";
  if(v>=1e8)return (v/1e8).toFixed(0)+"亿";
  return (v/1e4).toFixed(0)+"万";
}
async function loadPanMian(){
  const d=$("#pmDate").val()||"";
  show($("#pmIdx"),LOADING);
  try{
    const j=await api("panmian",{date:d});
    $("#pmHint").text(`数据日期 ${j.date}`);
    /* 三大指数 */
    show($("#pmIdx"),(j.indices||[]).map(it=>{
      const cls=colorOf(it.pct);
      return `<div class="pm-idx-card" data-code="${esc(stockCode(it.code))}">
        <div class="nm">${esc(it.name)}</div>
        <div class="pr ${cls}">${esc(it.price)}</div>
        <div class="ch ${cls}">${esc(it.change)}  ${esc(it.pct)}%</div></div>`;
    }).join("")||EMPTY+"暂无指数数据</div>");
    $("#pmIdx .pm-idx-card").on("click",function(){
      openKline(stockCode($(this).data("code")),$(this).find(".nm").text());
    });
    /* 今日/昨日两市成交 */
    show($("#pmAmt"),`<span class="pm-k">今日成交:</span><b class="pm-v up">${pmAmt(j.cur_amt)}</b>
      <span class="pm-k" style="margin-left:26px">昨日成交:</span><b class="pm-v">${pmAmt(j.pre_amt)}</b>`);
    /* 上涨/下跌/涨停/跌停家数 */
    show($("#pmUpDown"),`<span class="pm-k">上涨</span><b class="pm-v up">${esc(j.up==null?"-":j.up)}</b>
      <span class="pm-k">下跌</span><b class="pm-v down">${esc(j.down==null?"-":j.down)}</b>
      <span class="pm-k">涨停</span><b class="pm-v up">${esc(j.zt)}</b>
      <span class="pm-k">跌停</span><b class="pm-v down">${esc(j.dt)}</b>`);
    /* 情绪温度 */
    const lvCls=PM_LEVEL_CLS[j.level]||"pm-lv2";
    show($("#pmHero"),`<div class="pm-score ${lvCls}">
      <div class="pm-num">${esc(j.score)}</div>
      <div class="pm-info">
        <div class="pm-level">${esc(j.level)} <span class="dim" style="font-size:12px">情绪温度</span></div>
        <div class="pm-advice">${esc(j.advice)}</div>
      </div>
      <div class="pm-longyi">龙一: <b>${j.longyi?esc(j.longyi.name):"-"}</b>
        ${j.longyi?`<span class="dim">首封 ${esc(tsToTime(j.longyi.first_time))} ${esc(j.longyi.high_days||"")}</span>`:""}</div>
    </div>`);
    show($("#pmStats"),[
      `<div class="item">炸板<br><b class="down">${esc(j.zb)}</b></div>`,
      `<div class="item">炸板率<br><b>${esc(j.zb_rate)}%</b></div>`,
      `<div class="item">晋级率<br><b class="${j.jj_rate==null?"flat":j.jj_rate>=40?"up":"down"}">${j.jj_rate==null?"-":j.jj_rate+"%"}</b></div>`,
      `<div class="item">最高连板<br><b class="up">${esc(j.max_days)}板</b></div>`,
      `<div class="item">平盘家数<br><b class="flat">${esc(j.flat==null?"-":j.flat)}</b></div>`,
    ].join(""));
    show($("#pmReasons"),(j.top_reasons||[]).length?
      (j.top_reasons||[]).map((g,i)=>`<div class="pm-reason"><span class="rk rk${i+1}">${i+1}</span>
        <span class="rn">${esc(g.reason)}</span><span class="rc tag hot">${esc(g.count)}只</span></div>`).join(""):
      EMPTY+"暂无题材数据</div>");
    show($("#pmBoards"),(j.top_boards||[]).length?
      (j.top_boards||[]).map(b=>`<span class="tagchip" data-code="${esc(stockCode(b.code))}" data-name="${esc(b.name)}"
        title="${esc(b.code)}">${esc(b.name)}<b class="lb">${esc(b.days)}</b></span>`).join(""):
      EMPTY+"暂无数据</div>");
    $("#pmBoards .tagchip").on("click",function(){
      const t=$(this);
      openKline(stockCode(t.data("code")),t.data("name"));
    });
  }catch(e){errBox($("#pmIdx"),e)}
}

/* ---------- 板块资金轨迹 ---------- */
async function loadFlowCn(){
  const el=$("#fcTblWrap");
  show(el,LOADING);
  try{
    const j=await api("plate_flow_cn");
    $("#fcHint").text(`概念板块主力资金流 · 更新 ${j.time} · 按主力净流入排序`);
    renderTable(el,[
      {k:"name",label:"板块"},
      {k:"code",label:"代码"},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"main_net",label:"主力净流入",cls:r=>r.main_net&&String(r.main_net).indexOf("-")>-1?"down":"up",sortKey:"main_net_raw"},
      {k:"main_pct",label:"主力净占比",fmt:pct,color:"pct"},
      {k:"xl_net",label:"超大单净额",cls:r=>r.xl_net&&String(r.xl_net).indexOf("-")>-1?"down":"up"},
      {k:"big_net",label:"大单净额",cls:r=>r.big_net&&String(r.big_net).indexOf("-")>-1?"down":"up"},
      {k:"mid_net",label:"中单净额",cls:r=>r.mid_net&&String(r.mid_net).indexOf("-")>-1?"down":"up"},
      {k:"small_net",label:"小单净额",cls:r=>r.small_net&&String(r.small_net).indexOf("-")>-1?"down":"up"},
    ],j.rows,{rowClick:false});
  }catch(e){errBox(el,e)}
}

/* ---------- 东财智能选股(输入框自然语言条件) ---------- */
const EX_TPL=["涨停 半导体","连续涨停","主力净流入最多","市盈率低于20","市值大于1000亿",
  "MACD金叉","近期新高","高股息 破净","放量上涨","涨停 军工"];
function exBuildTpl(){
  if($("#exTpl .wc-t").length)return; /* 只构建一次 */
  $("#exTpl").html(EX_TPL.map(t=>`<span class="tagchip wc-t" data-q="${esc(t)}">${esc(t)}</span>`).join(""));
  $("#exTpl .wc-t").on("click",function(){
    $("#exInput").val($(this).data("q"));
    loadEmXuangu();
  });
}
async function loadEmXuangu(){
  exBuildTpl();
  const el=$("#exTblWrap"),q=($("#exInput").val()||"").trim();
  if(!q){show(el,`<div class="empty"><i class="bi bi-cpu"></i>输入选股条件, 如: 涨停 半导体 / 市盈率低于20 / MACD金叉</div>`);return}
  show(el,LOADING);
  try{
    const j=await api("em_xuangu",{q:q,size:60});
    $("#exHint").text(j.msg||"");
    if(!j.rows||!j.rows.length){show(el,`<div class="empty"><i class="bi bi-inbox"></i>未匹配到股票, 换个条件试试</div>`);return}
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"最新价",fmt:(v)=>v==null?"-":esc(v)},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"turnover",label:"换手率",fmt:(v)=>v==null?"-":esc(v)},
      {k:"qrr",label:"量比"},
      {k:"lianban",label:"连板",cls:r=>(r.lianban&&r.lianban!=="首板")?"up":""},
      {k:"first_time",label:"封板时间",fmt:(v)=>v==null?"-":esc(v)},
      {k:"reason",label:"涨停原因"},
      {k:"amount",label:"成交额"},
      {k:"pe",label:"市盈率"},
      {k:"total_value",label:"总市值"},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 问财选股 ---------- */
const WC_TPL=["今日涨停","连续涨停","主力净流入","光伏","机器人","创新药","AI 算力",
  "半导体","涨停 军工","中字头","涨停 并购重组","次新股"];
function wcBuildTpl(){
  if($("#wcTpl .wc-t").length)return; /* 只构建一次, 避免重复渲染 */
  $("#wcTpl").html(WC_TPL.map(t=>`<span class="tagchip wc-t" data-q="${esc(t)}">${esc(t)}</span>`).join(""));
  $("#wcTpl .wc-t").on("click",function(){
    $("#wcInput").val($(this).data("q"));
    loadWenCai();
  });
}
async function loadWenCai(){
  wcBuildTpl();
  const el=$("#wcTblWrap"),q=($("#wcInput").val()||"").trim();
  if(!q){show(el,`<div class="empty"><i class="bi bi-search"></i>请输入选股条件(如: 涨停 光伏 / 创新药 / 中国平安)</div>`);return}
  show(el,LOADING);
  try{
    const j=await api("wencai",{q:q,size:60});
    $("#wcHint").text(`${j.msg} · 数据日期 ${j.date}`);
    if(!j.rows||!j.rows.length){show(el,`<div class="empty"><i class="bi bi-inbox"></i>未匹配到股票, 换个关键词试试</div>`);return}
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"source",label:"来源"},
      {k:"days",label:"连板",cls:r=>(r.days&&r.days!=="首板")?"up":""},
      {k:"pct",label:"涨幅",color:"pct"},
      {k:"price",label:"现价",fmt:(v)=>v==null?"-":num(v)},
      {k:"first_time",label:"首封时间",fmt:tsToTime},
      {k:"reason",label:"涨停原因/题材",fmt:(v)=>v==null?"-":esc(v)},
    ],j.rows);
  }catch(e){errBox(el,e)}
}

/* ---------- 题材投资系统 ---------- */
async function loadThemeInv(){
  try{
    const j=await api("theme_invest");
    $("#tiHint").text(`题材机会聚合 · 数据日期 ${j.date} · 热门题材+概念资金+板块涨停`);
    show($("#tiTopics"),(j.topics||[]).map(t=>{
      const hot=Number(t.hot)||0;
      const hotTxt=hot>=10000?(hot/10000).toFixed(1)+"万":hot;
      return `<span class="tagchip" data-id="${esc(t.id)}" title="点击查看题材详情">${esc(t.title)}<b class="lb">${esc(hotTxt)}</b></span>`;
    }).join("")||EMPTY+"暂无题材</div>");
    $("#tiTopics .tagchip").on("click",function(){openTopic($(this).data("id"))});
    renderTable($("#tiTblWrap"),[
      {k:"name",label:"概念板块"},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"main_net",label:"主力净流入",cls:r=>r.main_net&&String(r.main_net).indexOf("-")>-1?"down":"up",sortKey:"main_net_raw"},
      {k:"main_pct",label:"主力净占比",fmt:pct,color:"pct"},
      {k:"up_num",label:"涨停家数",cls:r=>r.up_num>0?"up":""},
      {k:"leaders",label:"龙头股",fmt:(v)=> (v||[]).map(s=>`<span class="tag hot">${esc(s)}</span>`).join(" "),rowClick:false},
      {k:"reason",label:"上涨原因"},
    ],j.rows,{rowClick:false});
  }catch(e){errBox($("#tiTopics"),e)}
}

/* ---------- 全市场 ---------- */
async function loadMarket(){mkPage(0)}
async function mkPage(delta){
  const el=$("#mkTblWrap");
  if(delta){mkState.page=Math.max(1,mkState.page+delta)}
  if(mkState.pages&&mkState.page>mkState.pages)mkState.page=mkState.pages;
  mkState.sort=$("#mkSort").val();
  $("#mkPrev").prop("disabled",true);$("#mkNext").prop("disabled",true);
  show(el,LOADING);
  try{
    const j=await api("market",{sort:mkState.sort,page:mkState.page,size:mkState.size});
    mkState.pages=j.pages||1;
    $("#mkHint").text(`共 ${j.total} 只`);
    $("#mkPageInfo").text(`第 ${j.page} 页 / 共 ${j.pages} 页`);
    $("#mkPrev").prop("disabled",j.page<=1);
    $("#mkNext").prop("disabled",j.page>=j.pages);
    renderTable(el,[
      {k:"code",label:"代码"},{k:"name",label:"名称"},
      {k:"price",label:"现价"},
      {k:"pct",label:"涨跌幅",color:"pct"},
      {k:"volume",label:"成交量",fmt:(v)=>amt(v*100)},
      {k:"amount",label:"成交额",fmt:amt},
      {k:"turnover",label:"换手率",fmt:(v)=>v==null?"-":v+"%"},
      {k:"vol_ratio",label:"量比"},
      {k:"main_net",label:"主力净流入",fmt:amt,cls:r=>colorOf(r.main_net),sortKey:"main_net"},
      {k:"main_pct",label:"主力净占比",fmt:pct,color:"pct"},
      {k:"total_value",label:"总市值",fmt:amt},
    ],j.rows);
  }catch(e){
    errBox(el,e);
    $("#mkPrev").prop("disabled",false);$("#mkNext").prop("disabled",false);
  }
}
function mkJump(){
  const v=parseInt($("#mkJump").val());
  if(v&&v>=1&&v<=mkState.pages){mkState.page=v;mkPage(0)}
}

/* ---------- 复盘图窗口自适应 ---------- */
$(window).on("resize",()=>{
  ["rvTimeline","rvPyramid"].forEach(id=>{
    const el=document.getElementById(id);
    const ch=el&&echarts.getInstanceByDom(el);
    if(ch)ch.resize();
  });
});
