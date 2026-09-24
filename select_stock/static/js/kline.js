"use strict";

let kState={code:null,name:"",period:"day",chart:null,klines:[],lastDate:null};
let chipState={on:false,curDate:null,cache:{},timer:null,curChips:null};
let mState={chart:null};
const MA_COLORS={5:"#e8c24a",10:"#f584e3",20:"#6ec2ff",60:"#4cd97a"};
const MA_KEYS=[5,10,20,60];

function calcMA(n,closes){
  const out=[];
  let sum=0;
  for(let i=0;i<closes.length;i++){
    sum+=closes[i];
    if(i>=n)sum-=closes[i-n];
    out.push(i>=n-1?(sum/n):null);
  }
  return out;
}

/* MACD: DIF=EMA12-EMA26, DEA=EMA9(DIF), 柱=(DIF-DEA)*2 (通达信算法) */
function calcMACD(closes){
  const dif=[],dea=[],macd=[];
  let e12=null,e26=null,d=0;
  closes.forEach(c=>{
    if(e12==null){e12=c;e26=c;dif.push(0);dea.push(0);macd.push(0);return}
    e12=e12*11/13+c*2/13;
    e26=e26*25/27+c*2/27;
    const v=e12-e26;
    dif.push(v);
    d=d*8/10+v*2/10;
    dea.push(d);
    macd.push((v-d)*2);
  });
  return {dif,dea,macd};
}

/* 筹码峰横向条渲染(custom系列): 数据[筹码量v, 价格下限p, 价格上限p2],
   水平条从grid左缘向右延伸, 条长与v成正比; 纵轴价格与主图价格轴同步 */
function chipRenderItem(params,api){
  const v=api.value(0),p=api.value(1),p2=api.value(2);
  if(v==null||p==null)return null;
  const close=Number((chipState.curChips||{}).close)||0;
  const xL=api.coord([0,0])[0],xR=api.coord([v,0])[0];
  const yA=api.coord([0,p])[1],yB=api.coord([0,p2==null?p:p2])[1];
  const w=Math.abs(xR-xL),h=Math.max(Math.abs(yB-yA),0.8);
  return {type:"rect",
    shape:{x:Math.min(xL,xR),y:Math.min(yA,yB),width:w,height:h},
    style:{fill:p<=close?"rgba(226,61,61,.72)":"rgba(64,147,230,.72)"}};
}

function openKline(code,name){
  code=stockCode(code);
  if(!code)return;
  kState.code=code;
  kState.name=name||code;
  kState.period="day";
  kState.klines=[];
  kState.lastDate=null;
  chipState.curDate=null;
  chipState.curChips=null;
  $("#kChipBtn").show();
  $("#kName").text(kState.name);
  $("#kCode").text(code);
  $("#kPrice").text("--");
  $("#kPct").text("--");
  $("#kQuote").html("");
  $("#kMask").addClass("show");
  $("body").css("overflow","hidden");
  loadQuote();
  loadChart();
}

function closeKline(){
  $("#kMask").removeClass("show");
  if(!$("#mMask").hasClass("show"))$("body").css("overflow","");
  if(kState.chart){kState.chart.dispose();kState.chart=null}
}

async function loadQuote(){
  try{
    const q=await api("quote",{code:kState.code});
    if(q.error)return;
    $("#kName").text(q.name||kState.name);
    const pr=Number(q.price),p=Number(q.pct);
    $("#kPrice").text(pr?pr.toFixed(2):"--");
    $("#kPrice").attr("class","pr "+colorOf(p));
    $("#kPct").text((p>0?"+":"")+p.toFixed(2)+"%");
    $("#kPct").attr("class","pr "+colorOf(p));
    const kv=(l,v,cls)=>`<span>${l}<b class="${cls||""}">${esc(v==null||v===""?"-":v)}</b></span>`;
    $("#kQuote").html(
      kv("今开",q.open)+kv("昨收",q.pre_close)+kv("最高",q.high,"up")+kv("最低",q.low,"down")+
      kv("换手",q.turnover+"%")+kv("量比",q.vol_ratio)+kv("振幅",q.amplitude+"%")+
      kv("成交额",amt(Number(q.amount)*1e4))+kv("市盈率",q.pe)+kv("市净率",q.pb)+
      kv("总市值",amt(Number(q.total_value)*1e8))+kv("流通市值",amt(Number(q.float_value)*1e8))+
      kv("涨停价",q.limit_up,"up")+kv("跌停价",q.limit_down,"down")+kv("更新",q.time));
  }catch(e){}
}

function buildPeriods(){
  const el=$("#kPeriod");
  const ps=[["minute","分时"],["day","日K"],["week","周K"],["month","月K"]];
  el.html(`<span class="lbl">周期:</span>`+ps.map(([k,l])=>
    `<button class="btn mini ${k===kState.period?"on":""}" onclick="setPeriod('${k}')">${l}</button>`).join("")+
    `<span class="lbl" style="margin-left:8px">前复权 · 滚轮缩放 · 十字光标查看详情 · 双击日K看分时</span>`);
}

function setPeriod(p){
  kState.period=p;
  kState.klines=[];
  kState.lastDate=null;
  chipState.curDate=null;
  /* 筹码峰只在日K显示 */
  if(p!=="day")setChipsVisible(false);
  else $("#kChipBtn").show();
  buildPeriods();
  loadChart();
}

function setChipsVisible(on){
  chipState.on=!!on;
  $("#kChipBtn").toggle(on);
  $("#kChipBtn").toggleClass("on",on);
  if(kState.chart)kState.chart.resize();
}

async function loadChart(){
  const box=$("#kChart");
  box.html(LOADING);
  if(kState.chart){kState.chart.dispose();kState.chart=null}
  kState.chart=echarts.init(box[0],null,{renderer:"canvas"});
  try{
    if(kState.period==="minute"){
      const j=await api("minute",{code:kState.code});
      if(j.error){box.html(`<div class="empty">${esc(j.error)}</div>`);return}
      kState.chart.setOption(buildMinuteOption(j),true);
    }else{
      const j=await api("kline",{code:kState.code,period:kState.period});
      if(j.error){box.html(`<div class="empty">${esc(j.error)}</div>`);return}
      if(!j.klines.length){box.html(EMPTY+"暂无K线数据</div>");return}
      kState.klines=j.klines;
      kState.lastDate=j.klines[j.klines.length-1].date;
      /* 日K且筹码开启: 右侧筹码图(共享价格轴, 黄线=平均成本) */
      const chips=(chipState.on&&kState.period==="day")?{bins:[]}:null;
      kState.chart.setOption(buildKlineOption(j.klines,chips),true);
      /* 十字光标移动 -> 筹码峰跟随光标所在K线日期切换(同花顺/通达信/东财标准行为) */
      kState.chart.on("updateAxisPointer",e=>{
        if(!chipState.on||kState.period!=="day")return;
        /* category轴的value是类目索引(数字), 需转成该K线的日期 */
        const info=(e.axesInfo||[]).find(a=>a.axisDim==="x"&&a.axisIndex===0);
        if(!info||info.value==null)return;
        const k=kState.klines[Math.round(info.value)];
        if(!k||k.date===chipState.curDate)return;
        loadChips(k.date);
      });
      /* 鼠标离开图表 -> 筹码峰回到最新交易日 */
      kState.chart.getZr().on("globalout",()=>{
        if(!chipState.on||kState.period!=="day")return;
        if(chipState.curDate!==kState.lastDate)loadChips(kState.lastDate);
      });
      /* 双击日K -> 当日分时 */
      kState.chart.on("dblclick",p=>{
        if(kState.period!=="day"||p.dataIndex==null)return;
        const k=kState.klines[p.dataIndex];
        if(k)openMinute(kState.code,kState.name,k.date);
      });
      /* 缩放时主图价格轴变化 -> 同步筹码价格轴 */
      kState.chart.on("datazoom",()=>{if(chipState.on)syncChipAxis()});
      if(chipState.on&&kState.period==="day")loadChips(kState.lastDate);
    }
  }catch(e){
    box.html(`<div class="error">加载失败: ${esc(e.message)}</div>`);
  }
}

function buildKlineOption(klines,chips){
  const dates=klines.map(k=>k.date);
  const kdata=klines.map(k=>[k.open,k.close,k.low,k.high]);
  const closes=klines.map(k=>k.close);
  const vols=klines.map(k=>k.volume);
  const macd=calcMACD(closes);
  const series=[
    {id:"k",name:"K线",type:"candlestick",data:kdata,
     itemStyle:{color:"#e23d3d",color0:"#0b9d39",borderColor:"#e23d3d",borderColor0:"#0b9d39"},
     emphasis:{itemStyle:{borderWidth:2}},
     markLine:{silent:true,symbol:"none",data:[]}}
  ];
  const legend=["K线"];
  MA_KEYS.forEach(n=>{
    series.push({name:"MA"+n,type:"line",data:calcMA(n,closes),smooth:true,
      symbol:"none",lineStyle:{width:1,color:MA_COLORS[n]},itemStyle:{color:MA_COLORS[n]}});
    legend.push("MA"+n);
  });
  series.push({name:"成交量",type:"bar",xAxisIndex:1,yAxisIndex:1,data:vols.map((v,i)=>(
    {value:v,itemStyle:{color:closes[i]>=klines[i].open?"#e23d3d":"#0b9d39"}}))});
  legend.push("成交量");
  series.push({name:"DIF",type:"line",xAxisIndex:2,yAxisIndex:2,data:macd.dif,symbol:"none",
    lineStyle:{width:1,color:"#e8c24a"},itemStyle:{color:"#e8c24a"}});
  series.push({name:"DEA",type:"line",xAxisIndex:2,yAxisIndex:2,data:macd.dea,symbol:"none",
    lineStyle:{width:1,color:"#6ec2ff"},itemStyle:{color:"#6ec2ff"}});
  series.push({name:"MACD",type:"bar",xAxisIndex:2,yAxisIndex:2,barWidth:"55%",
    data:macd.macd.map(v=>({value:v,itemStyle:{color:v>=0?"#e23d3d":"#0b9d39"}}))});
  legend.push("DIF","DEA","MACD");
  /* 筹码峰(日K右侧, 与主图价格轴像素对齐): 现价以下获利红, 现价以上套牢蓝, 黄线=平均成本 */
  const chipGrids=chips?[{right:14,width:94,top:30,height:"46%"},
    {right:14,width:94,top:"60%",height:"10%"}]:[];
  const chipAxis=chips?[{type:"value",gridIndex:3,min:0,axisLabel:{show:false},
    axisLine:{show:false},axisTick:{show:false},splitLine:{show:false}}]:[];
  /* 筹码价格轴(与主图yAxis0同区同刻度, 由syncChipAxis动态同步min/max) */
  const chipYAxis=chips?[{type:"value",gridIndex:3,min:0,max:1,axisLabel:{show:false},
    axisLine:{show:false},axisTick:{show:false},splitLine:{show:false}}]:[];
  /* 筹码统计信息框(量能柱右侧grid4, graphic文本) + 筹码峰顶部日期 */
  const chipGraphic=chips?[
    {id:"chipDateTxt",type:"text",right:16,top:33,
      style:{text:"",fill:"#8b93a1",font:"10px sans-serif"}},
    {id:"chipInfo",type:"group",right:14,width:94,top:"60%",height:"10%",
      children:[]}
  ]:[];
  if(chips){
    /* 筹码峰横向条: 每个价格bin一条水平条(条长=筹码量, 从grid左缘向右延伸),
       纵轴与主图价格轴同步; 现价以下获利红, 现价以上套牢蓝 */
    series.push({id:"chip",name:"筹码",type:"custom",xAxisIndex:3,yAxisIndex:3,
      clip:true,data:[],renderItem:chipRenderItem,
      markLine:{silent:true,symbol:"none",data:[]}});
    legend.push("筹码");
  }
  return {
    animation:false,
    legend:{data:legend,top:0,left:0,textStyle:{color:"#8b93a1",fontSize:12},inactiveColor:"#4a5260"},
    tooltip:{
      trigger:"axis",axisPointer:{type:"cross",
        label:{backgroundColor:"#3a3f4a",color:"#d8dce3",fontSize:11}},
      backgroundColor:"#1d2129",borderColor:"#2e3440",padding:[8,12],
      textStyle:{color:"#d8dce3",fontSize:12},
      formatter:(ps)=>{
        if(!ps||!ps.length)return"";
        if(ps[0].seriesName==="筹码"){
          const d=ps[0].value||[];
          const cc=chipState.curChips||{};
          const pct=cc.total?((d[0]/cc.total)*100).toFixed(2):"--";
          const win=Number(cc.close)&&Number(d[1])<=Number(cc.close);
          return `<div style="font-weight:700;margin-bottom:4px">筹码分布</div>
            <div>价格区间 <b>${Number(d[1]).toFixed(2)} ~ ${Number(d[2]).toFixed(2)}</b></div>
            <div>筹码占比 <b>${pct}%</b></div>
            <div style="color:${win?"#e23d3d":"#4093e6"}">${win?"获利筹码":"套牢筹码"}</div>`;
        }
        const i=ps[0].dataIndex;
        const k=klines[i];
        if(!k)return"";
        const pre=klines[i-1]?klines[i-1].close:k.open;
        const p=((k.close-pre)/pre*100).toFixed(2);
        const cls=p>=0?"#e23d3d":"#0b9d39";
        let h=`<div style="font-weight:700;margin-bottom:4px">${k.date}</div>`;
        h+=`<div>开盘 <b>${k.open.toFixed(2)}</b>　收盘 <b>${k.close.toFixed(2)}</b></div>`;
        h+=`<div>最高 <b style="color:#e23d3d">${k.high.toFixed(2)}</b>　最低 <b style="color:#0b9d39">${k.low.toFixed(2)}</b></div>`;
        h+=`<div>涨跌幅 <b style="color:${cls}">${p>=0?"+":""}${p}%</b>　成交量 <b>${amt(k.volume*100)}</b></div>`;
        if(k.amplitude!=null)h+=`<div>振幅 <b>${k.amplitude.toFixed(2)}%</b>　换手率 <b>${k.turnover!=null?k.turnover.toFixed(2)+"%":"-"}</b></div>`;
        MA_KEYS.forEach(n=>{
          const ma=calcMA(n,closes)[i];
          if(ma!=null)h+=`<div style="color:${MA_COLORS[n]}">MA${n}: ${ma.toFixed(2)}</div>`;
        });
        h+=`<div>MACD <b style="color:${macd.macd[i]>=0?"#e23d3d":"#0b9d39"}">${macd.macd[i].toFixed(3)}</b>　DIF <b>${macd.dif[i].toFixed(3)}</b>　DEA <b>${macd.dea[i].toFixed(3)}</b></div>`;
        return h;
      }
    },
    axisPointer:{link:[{xAxisIndex:[0,1,2]}],
      label:{backgroundColor:"#3a3f4a",color:"#d8dce3"}},
    grid:[
      {left:64,right:chips?124:16,top:30,height:"46%"},
      {left:64,right:chips?124:16,top:"60%",height:"10%"},
      {left:64,right:chips?124:16,top:"72%",height:"10%"},
      ...chipGrids
    ],
    xAxis:[
      {type:"category",data:dates,gridIndex:0,boundaryGap:true,
       axisLine:{lineStyle:{color:"#2e3440"}},axisLabel:{color:"#8b93a1"},
       axisTick:{show:false},splitLine:{show:false},min:"dataMin",max:"dataMax"},
      {type:"category",data:dates,gridIndex:1,boundaryGap:true,
       axisLine:{lineStyle:{color:"#2e3440"}},axisLabel:{show:false},
       axisTick:{show:false},splitLine:{show:false},min:"dataMin",max:"dataMax"},
      {type:"category",data:dates,gridIndex:2,boundaryGap:true,
       axisLine:{lineStyle:{color:"#2e3440"}},axisLabel:{color:"#8b93a1",fontSize:10},
       axisTick:{show:false},splitLine:{show:false},min:"dataMin",max:"dataMax"},
      ...chipAxis
    ],
    yAxis:[
      {scale:true,gridIndex:0,splitLine:{lineStyle:{color:"#232832"}},
       axisLabel:{color:"#8b93a1"},axisLine:{show:false},axisTick:{show:false}},
      {scale:true,gridIndex:1,splitLine:{show:false},axisLabel:{show:false},
       axisLine:{show:false},axisTick:{show:false}},
      {scale:true,gridIndex:2,splitLine:{show:false},axisLabel:{color:"#8b93a1",fontSize:10},
       axisLine:{show:false},axisTick:{show:false}},
      ...chipYAxis
    ],
    dataZoom:[
      {type:"inside",xAxisIndex:[0,1,2],start:60,end:100,zoomOnMouseWheel:true,moveOnMouseMove:true},
      {type:"slider",xAxisIndex:[0,1,2],top:"88%",height:16,start:60,end:100,
       left:64,right:chips?124:16,
       borderColor:"#2e3440",backgroundColor:"#16181f",fillerColor:"rgba(64,147,230,.12)",
       handleStyle:{color:"#4093e6"},moveHandleStyle:{color:"#4093e6"},
       textStyle:{color:"#8b93a1",fontSize:10},dataBackground:{lineStyle:{color:"#2e3440"},areaStyle:{color:"#1d2129"}}}
    ],
    graphic:chipGraphic,
    series
  };
}

/* ============ 筹码分布联动(日K右侧, 共享价格轴, 黄线=平均成本) ============ */
function toggleChips(){
  if(kState.period!=="day")return;
  setChipsVisible(!chipState.on);
  chipState.curChips=null;
  chipState.curDate=null;
  clearTimeout(chipState.timer); /* 取消未完成的筹码请求 */
  loadChart(); /* 重绘主图: 带/不带右侧筹码网格 */
}

/* 筹码价格轴与主图价格轴(yAxis0)同步min/max, 保证筹码峰与日K价格像素级对齐 */
function syncChipAxis(){
  if(!kState.chart||!chipState.on||kState.period!=="day")return;
  try{
    const m=kState.chart.getModel();
    const ex=m.getComponent("yAxis",0).axis.scale.getExtent();
    kState.chart.setOption({yAxis:[{},{},{},{min:ex[0],max:ex[1]}]});
  }catch(e){}
}

function loadChips(date){
  if(!chipState.on||!date)return;
  chipState.curDate=date;
  const ck=kState.code+"|"+date;
  if(chipState.cache[ck]){renderChips(chipState.cache[ck]);return}
  clearTimeout(chipState.timer);
  chipState.timer=setTimeout(async()=>{
    const d=chipState.curDate;
    const k2=kState.code+"|"+d;
    if(!d||chipState.cache[k2])return;
    try{
      const j=await api("chips",{code:kState.code,date:d});
      if(j.error){
        if(kState.chart)kState.chart.setOption({graphic:[{id:"chipInfo",children:[
          {type:"text",x:6,y:3,style:{text:j.error,fill:"#8b93a1",fontSize:9}}]}]});
        return;
      }
      chipState.cache[k2]=j;
      if(chipState.curDate===d)renderChips(j);
    }catch(e){
      if(kState.chart)kState.chart.setOption({graphic:[{id:"chipInfo",children:[
        {type:"text",x:6,y:3,style:{text:"加载失败",fill:"#e23d3d",fontSize:9}}]}]});
    }
  },200);
}

/* 筹码统计信息行(量能柱右侧框内, rich文本: 标签灰+数值彩) */
function chipInfoRows(j){
  const c90=j.c90||[0,0],c70=j.c70||[0,0];
  const profit=j.profit_ratio,pc=profit>=50?"#e23d3d":"#0b9d39";
  const rows=[
    ["平均成本",Number(j.avg_cost).toFixed(2),"#e8c24a"],
    ["获利比例",profit+"%",pc],
    ["90%筹码",c90[0].toFixed(1)+"~"+c90[1].toFixed(1),"#c7cede"],
    ["70%筹码",c70[0].toFixed(1)+"~"+c70[1].toFixed(1),"#c7cede"],
    ["集中度",j.c90_conc+"%","#c7cede"]
  ];
  return rows.map((r,i)=>({
    type:"text",x:6,y:3+i*11,
    style:{text:"{lb|"+r[0]+"} {vl|"+r[1]+"}",
      rich:{lb:{fill:"#8b93a1",fontSize:9},vl:{fill:r[2],fontSize:9,fontWeight:"bold"}}}
  }));
}

/* 筹码数据 -> 主图右侧筹码峰(与价格轴像素对齐) + 量能柱右侧统计框 */
function renderChips(j){
  if(!chipState.on)return; /* 异步返回时筹码可能已关闭 */
  chipState.curChips=j;
  const bins=j.bins||[];
  const close=Number(j.close)||0;
  const total=bins.reduce((a,b)=>a+b[1],0)||1;
  chipState.curChips.total=total;
  chipState.curChips.close=close;
  if(kState.chart){
    const binH=bins.length>1?bins[1][0]-bins[0][0]:0.01;
    const maxV=bins.length?Math.max(...bins.map(b=>b[1])):0;
    syncChipAxis(); /* 筹码价格轴与主图对齐, 黄线=平均成本 */
    kState.chart.setOption({
      xAxis:[{},{},{},{max:maxV*1.25||100}],
      series:[
        {id:"k",markLine:{silent:true,symbol:"none",data:[
          j.avg_cost!=null?{yAxis:Number(j.avg_cost),
            lineStyle:{color:"rgba(232,194,74,.55)",width:1,type:"dashed"},
            label:{show:false}}:null
        ].filter(Boolean)}},
        {id:"chip",
          data:bins.map(([p,v])=>[v,p,p+binH]),
          markLine:{silent:true,symbol:"none",data:[
            j.avg_cost!=null?{yAxis:Number(j.avg_cost),
              lineStyle:{color:"#e8c24a",width:1.6},
              label:{formatter:"平均成本 "+Number(j.avg_cost).toFixed(2),color:"#e8c24a",
                fontSize:10,fontWeight:"bold",position:"insideEndTop"}}:null,
            close?{yAxis:close,
              lineStyle:{color:"#8b93a1",width:1,type:"dashed"},
              label:{formatter:"现价 "+close.toFixed(2),color:"#8b93a1",fontSize:9,
                position:"insideEndBottom"}}:null
          ].filter(Boolean)}
        }
      ],
      graphic:[
        {id:"chipDateTxt",style:{text:j.date}},
        {id:"chipInfo",children:chipInfoRows(j)}
      ]
    });
  }
}

/* ============ 分时图弹窗(双击日K) ============ */
async function openMinute(code,name,date){
  $("#mName").text(name||code);
  $("#mDate").text((date||"")+" 分时走势");
  $("#mMask").addClass("show");
  const box=$("#mChart");
  box.html(LOADING);
  if(mState.chart){mState.chart.dispose();mState.chart=null}
  mState.chart=echarts.init(box[0],null,{renderer:"canvas"});
  try{
    const j=await api("minute",{code:code,date:date||""});
    if(j.error){box.html(`<div class="empty">${esc(j.error)}</div>`);return}
    mState.chart.setOption(buildMinuteOption(j),true);
  }catch(e){
    box.html(`<div class="error">加载失败: ${esc(e.message)}</div>`);
  }
}

function closeMinute(){
  $("#mMask").removeClass("show");
  if(!$("#kMask").hasClass("show"))$("body").css("overflow","");
  if(mState.chart){mState.chart.dispose();mState.chart=null}
}

function buildMinuteOption(j){
  const pts=j.points||[];
  const times=pts.map(p=>p.t.slice(0,2)+":"+p.t.slice(2));
  const prices=pts.map(p=>p.price);
  const vols=pts.map(p=>p.volume);
  const pre=j.pre_close||(prices.length?prices[0]:0);
  /* 均价: 优先后端计算(累计额/累计量), 否则按增量加权估算 */
  let avgs=j.avgs||null;
  if(!avgs||avgs.length!==pts.length){
    avgs=[];let sv=0,spv=0,prev=0;
    pts.forEach(p=>{const dv=Math.max(0,p.volume-prev);prev=p.volume;sv+=dv;spv+=p.price*dv;avgs.push(sv?spv/sv:null)});
  }
  const volColors=pts.map((p,i)=>i>0&&p.price<prices[i-1]?"#0b9d39":"#e23d3d");
  return {
    animation:false,
    legend:{data:["价格","均价"],top:0,left:0,textStyle:{color:"#8b93a1",fontSize:12}},
    tooltip:{
      trigger:"axis",axisPointer:{type:"cross",label:{backgroundColor:"#3a3f4a",color:"#d8dce3",fontSize:11}},
      backgroundColor:"#1d2129",borderColor:"#2e3440",textStyle:{color:"#d8dce3",fontSize:12},
      formatter:(ps)=>{
        if(!ps||!ps.length)return"";
        const i=ps[0].dataIndex,p=pts[i];
        if(!p)return"";
        const pc=((p.price-pre)/pre*100).toFixed(2);
        const cls=pc>=0?"#e23d3d":"#0b9d39";
        return `<div style="font-weight:700">${times[i]}</div>
          <div>价格 <b style="color:${cls}">${p.price.toFixed(2)}</b>　涨跌幅 <b style="color:${cls}">${pc>=0?"+":""}${pc}%</b></div>
          <div>均价 <b>${avgs[i]!=null?avgs[i].toFixed(2):"--"}</b>　成交量 <b>${amt(p.volume*100)}</b></div>`;
      }
    },
    grid:[{left:64,right:16,top:30,height:"56%"},{left:64,right:16,top:"76%",height:"14%"}],
    xAxis:[
      {type:"category",data:times,gridIndex:0,boundaryGap:false,
       axisLine:{lineStyle:{color:"#2e3440"}},axisLabel:{color:"#8b93a1",interval:29},axisTick:{show:false}},
      {type:"category",data:times,gridIndex:1,boundaryGap:false,
       axisLine:{lineStyle:{color:"#2e3440"}},axisLabel:{show:false},axisTick:{show:false}}
    ],
    yAxis:[
      {scale:true,gridIndex:0,splitLine:{lineStyle:{color:"#232832"}},
       axisLabel:{color:"#8b93a1"},axisLine:{show:false},axisTick:{show:false}},
      {scale:true,gridIndex:1,splitLine:{show:false},axisLabel:{show:false},
       axisLine:{show:false},axisTick:{show:false}}
    ],
    series:[
      {name:"价格",type:"line",data:prices,symbol:"none",
       lineStyle:{width:1.2,color:"#4093e6"},areaStyle:{color:{type:"linear",x:0,y:0,x2:0,y2:1,
         colorStops:[{offset:0,color:"rgba(64,147,230,.22)"},{offset:1,color:"rgba(64,147,230,.02)"}]}},
       markLine:{silent:true,symbol:"none",label:{formatter:"昨收 "+Number(pre).toFixed(2),color:"#8b93a1",fontSize:10},
         lineStyle:{color:"#e8c24a",type:"dashed",width:1},data:[{yAxis:pre}]}},
      {name:"均价",type:"line",data:avgs,symbol:"none",lineStyle:{width:1,color:"#e8c24a"}},
      {name:"成交量",type:"bar",xAxisIndex:1,yAxisIndex:1,data:vols.map((v,i)=>({value:v,itemStyle:{color:volColors[i]}}))}
    ]
  };
}

/* 窗口缩放自适应 */
$(window).on("resize",()=>{
  if(kState.chart)kState.chart.resize();
  if(mState.chart)mState.chart.resize();
});
