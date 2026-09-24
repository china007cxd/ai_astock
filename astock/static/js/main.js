/* ============ 主入口: Tab 构建 + 时钟 + 交易状态 + 自动刷新 ============ */
"use strict";

const TABS=[
  ["watchlist","自选","bi-star"],
  ["indices","大盘指数","bi-graph-up-arrow"],
  ["duishu","盯盘","bi-eye"],
  ["limitup","涨停板","bi-arrow-up-circle"],
  ["ztpool","涨停池","bi-fire"],
  ["zbpool","炸板池","bi-slash-circle"],
  ["dtpool","跌停板","bi-arrow-down-circle"],
  ["broken","破板","bi-signpost-split"],
  ["ladder","连板梯队","bi-diagram-3"],
  ["hotplate","热门板块","bi-collection"],
  ["flow","资金流","bi-cash-stack"],
  ["lhb","龙虎榜","bi-trophy"],
  ["bidding","竞价封单","bi-hourglass-split"],
  ["news","快讯","bi-newspaper"],
  ["hotstock","人气榜","bi-fire"],
  ["longyi","今日龙一","bi-trophy-fill"],
  ["fengkou","最强风口","bi-wind"],
  ["ztreason","涨停原因","bi-tag"],
  ["ztreview","涨停复盘","bi-pie-chart"],
  ["dragon","龙头晋级","bi-signpost-2"],
  ["nearzt","即将涨停","bi-lightning-charge"],
  ["topiccycle","题材周期表","bi-arrow-repeat"],
  ["topictl","题材时间线","bi-clock-history"],
  ["panmian","盘面梳理","bi-clipboard-pulse"],
  ["flowcn","板块资金轨迹","bi-signpost-split"],
  ["emxg","东财智能选股","bi-cpu"],
  ["wencai","问财选股","bi-search"],
  ["themeinv","题材投资","bi-lightbulb"],
  ["market","全市场","bi-grid-3x3-gap"],
];

function buildTabs(){
  $("#tabs").html(TABS.map(([k,l,i])=>
    `<button data-k="${k}" class="${k==="watchlist"?"active":""}"><i class="bi ${i}"></i>${l}</button>`).join(""));
  $("#tabs button").on("click",function(){switchTab($(this).data("k"))});
}

/* ---------- 时钟 + 交易状态 ---------- */
function tick(){
  const d=new Date();
  const p=n=>String(n).padStart(2,"0");
  $("#clock").text(`${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())} `+
    `${p(d.getMonth()+1)}-${p(d.getDate())} 周${"日一二三四五六".charAt(d.getDay())}`);
  const wd=d.getDay(),t=d.getHours()*60+d.getMinutes();
  let st="休市",open=false;
  if(wd>0&&wd<6){
    if(t<9*60+15)st="未开盘";
    else if(t<9*60+30){st="集合竞价";open=true}
    else if(t<11*60+30){st="交易中";open=true}
    else if(t<13*60)st="午间休市";
    else if(t<15*60){st="交易中";open=true}
    else st="已收盘";
  }else{st=wd===0?"休市(周日)":"休市(周六)"}
  $("#mktStatus").text(st).toggleClass("open",open);
}

/* ---------- 自动刷新 ---------- */
let timer=null,lastDay="";

function schedule(){
  clearInterval(timer);
  if(!$("#autoRef").is(":checked"))return;
  timer=setInterval(()=>{
    if($("#kMask").hasClass("show"))return;  // K线弹窗打开时不打断
    const now=fmtD(new Date());
    if(now!==lastDay){lastDay=now;setDates()}  // 跨日: 重新校准交易日日期
    if(loaded[curTab])LOADERS[curTab]().catch(()=>{});
  },parseInt($("#refInt").val(),10)*1000);
}

/* ---------- 立即刷新 ---------- */
function refreshAll(){
  if(curTab!=="indices")loadIndices().catch(()=>{});
  if(loaded[curTab])LOADERS[curTab]().catch(()=>{});
}

/* ---------- 启动 ---------- */
$(function(){
  buildTabs();
  setDates();
  buildPeriods();
  $("#autoRef").on("change",schedule);
  $("#refInt").on("change",schedule);
  lastDay=fmtD(new Date());
  tick();
  setInterval(tick,1000);
  schedule();
  switchTab("watchlist");
});
