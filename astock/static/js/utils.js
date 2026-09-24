/* ============ 工具函数 ============ */
"use strict";

const LOADING='<div class="loading"><span class="spinner-border spinner-border-sm"></span>加载中...</div>';
const EMPTY='<div class="empty"><i class="bi bi-inbox"></i>暂无数据';

function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function tsToTime(ts){if(!ts)return"-";if(String(ts).length===13)ts=Math.floor(ts/1000);const d=new Date(Number(ts)*1000);if(isNaN(d))return String(ts);return d.toTimeString().slice(0,5)}
function tsToDate(ts){if(!ts)return"-";const d=new Date(Number(ts)*1000);if(isNaN(d))return String(ts);return d.toLocaleDateString("zh-CN")}
function colorOf(v){
  if(typeof v==="string"){v=v.replace(/[%,]/g,"");if(!/^-?[\d.]+$/.test(v))return"flat"}
  if(v==null||isNaN(v))return"flat";
  if(v>0)return"up";if(v<0)return"down";return"flat";
}
function pct(v){if(v==null||v===""||v==="-")return"-";v=Number(v);if(isNaN(v))return String(v);
  return (v>0?"+":"")+v.toFixed(2)+"%"}
function num(v,d=2){if(v==null||v===""||v==="-")return"-";v=Number(v);if(isNaN(v))return String(v);
  return v.toLocaleString("zh-CN",{maximumFractionDigits:d})}
function amt(v){if(v==null||v===""||v==="-")return"-";v=Number(v);if(isNaN(v))return String(v);
  if(Math.abs(v)>=1e8)return (v/1e8).toFixed(2)+"亿";if(Math.abs(v)>=1e4)return (v/1e4).toFixed(0)+"万";
  return v.toFixed(0)}
function emPrice(v){if(v==null)return"-";v=Number(v);if(isNaN(v))return String(v);return v>100?v/1000:v}  // 东财千倍价

async function api(name,params={}){
  const qs=new URLSearchParams(params).toString();
  const r=await fetch("/api/"+name+(qs?"?"+qs:""));
  const j=await r.json();
  if(!r.ok||j.error)throw new Error(j.error||("HTTP "+r.status));
  return j;
}
function show(el,html){el.html(html)}
function errBox(el,e){el.html(`<div class="error"><i class="bi bi-exclamation-triangle"></i> 加载失败: ${esc(e.message)}<br><button class="btn mini" onclick="refreshAll()">重试</button></div>`)}

/* 从各种格式的代码中提取6位股票代码 */
function stockCode(c){
  if(c==null)return null;
  c=String(c).toLowerCase();
  const m=c.match(/(\d{6})/);
  return m?m[1]:null;
}

/* ---------- 通用表格渲染 ---------- */
function renderTable(el,cols,rows,opts={}){
  if(!rows||!rows.length){show(el,EMPTY+(opts.empty||"")+"</div>");return}
  let html=`<table><thead><tr><th style="text-align:left">#</th>`;
  for(const c of cols){html+=`<th data-k="${esc(c.k)}">${esc(c.label)}</th>`}
  html+=`</tr></thead><tbody>`;
  rows.forEach((r,i)=>{
    const code=opts.getCode?opts.getCode(r):stockCode(r.code);
    html+=`<tr data-code="${esc(code||"")}"><td class="dim">${i+1}</td>`;
    for(const c of cols){
      let v=r[c.k];
      let cls=opts.cls?opts.cls(r,c):(c.cls?c.cls(r,c):"");
      let htmlV;
      if(c.fmt)htmlV=c.fmt(v,r);else htmlV=esc(v==null?"-":v);
      if(!cls&&c.color&&v!=null&&v!=="")cls=colorOf(v);
      if(c.color==="pct"&&v!=null){htmlV=pct(v);cls=cls||colorOf(v)}
      html+=`<td class="${cls}">${htmlV}</td>`;
    }
    html+=`</tr>`;
  });
  html+=`</tbody></table>`;
  show(el,html);
  if(opts.rowClick!==false){
    el.find("tbody tr").on("click",function(){
      const code=$(this).data("code");
      if(!code)return;
      const name=$(this).find("td").eq(1).text().trim();
      openKline(code,name);
    });
  }
  if(opts.sortable!==false){
    el.find("th[data-k]").on("click",function(){
      const th=$(this),k=th.data("k"),col=cols.find(c=>c.k===k);
      const key=col&&col.sortKey?col.sortKey:k;
      const raw=rows.slice();
      const dir=th.hasClass("sorted")&&th.data("dir")==="d"?"a":"d";
      el.find("th").removeClass("sorted").removeData("dir");
      th.addClass("sorted").data("dir",dir);
      raw.sort((a,b)=>{
        let x=a[key],y=b[key];
        if(typeof x==="string")x=parseFloat(x.replace(/[%,亿万]/g,""));
        if(typeof y==="string")y=parseFloat(y.replace(/[%,亿万]/g,""));
        if(isNaN(x))x=a[key];if(isNaN(y))y=b[key];
        if(x<y)return dir==="a"?-1:1;
        if(x>y)return dir==="a"?1:-1;
        return 0;
      });
      renderTable(el,cols,raw,Object.assign({},opts,{sortable:false,rowClick:opts.rowClick}));
      const t2=el.find(`th[data-k="${esc(k)}"]`);
      if(t2.length){t2.addClass("sorted").data("dir",dir)}
    });
  }
}
