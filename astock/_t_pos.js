const echarts=require('D:/SoftwareInstallaction/v62.1/astock/static/echarts.min.js');
const W=1100,H=620;
const rows=[['平均成本','1309.22','#e8c24a'],['获利比例','52.14%','#e23d3d'],['90%筹码','1188.9~1432.2','#c7cede'],['70%筹码','1212.8~1388.3','#c7cede'],['集中度','9.28%','#c7cede']].map((r,i)=>({type:'text',x:6,y:3+i*11,style:{text:'{lb|'+r[0]+'} {vl|'+r[1]+'}',rich:{lb:{fill:'#8b93a1',fontSize:9},vl:{fill:r[2],fontSize:9,fontWeight:'bold'}}}}));
const opt={animation:false,
 grid:[{left:64,right:124,top:30,height:'46%'},{left:64,right:124,top:'60%',height:'10%'},{left:64,right:124,top:'72%',height:'10%'},{right:14,width:94,top:30,height:'46%'},{right:14,width:94,top:'60%',height:'10%'}],
 xAxis:[{type:'category',gridIndex:0,data:['1','2','3'],axisLabel:{show:false}},{type:'category',gridIndex:1,data:['1','2','3'],axisLabel:{show:false}},{type:'category',gridIndex:2,data:['1','2','3'],axisLabel:{show:false}},{type:'value',gridIndex:3,min:0,axisLabel:{show:false},axisLine:{show:false},axisTick:{show:false},splitLine:{show:false}}],
 yAxis:[{type:'value',gridIndex:0,scale:true,min:10,max:20},{type:'value',gridIndex:1},{type:'value',gridIndex:2},{type:'value',gridIndex:3,min:0,max:1,axisLabel:{show:false},axisLine:{show:false},axisTick:{show:false},splitLine:{show:false}}],
 graphic:[{id:'chipDateTxt',type:'text',right:16,top:33,style:{text:'2026-08-24',fill:'#8b93a1',font:'10px sans-serif'}},{id:'chipInfo',type:'group',right:14,width:94,top:'60%',height:'10%',children:rows}],
 series:[{type:'line',xAxisIndex:0,yAxisIndex:0,data:[11,15,13]},{type:'bar',xAxisIndex:1,yAxisIndex:1,data:[5,3,4]},{type:'line',xAxisIndex:2,yAxisIndex:2,data:[1,2,1]},{type:'custom',xAxisIndex:3,yAxisIndex:3,data:[]}]};
const chart=echarts.init({clientWidth:W,clientHeight:H},null,{renderer:'svg',ssr:true,width:W,height:H});
chart.setOption(opt);
const svg=chart.renderToSVGString();
// 日期文本位置(期望 x≈W-16-文本宽, y=33)
const di=svg.indexOf('2026-08-24');
const ctx=svg.slice(Math.max(0,di-300),di+30);
const dm=ctx.match(/transform="translate\(([\d.]+),([\d.]+)\)"/);
console.log('date txt translate:',dm?dm[1]+','+dm[2]:'NOT FOUND');
// 统计行(平均成本)位置: 期望 group 原点 x=W-108=992, y=60%*H=372, 行1 y=372+3
const ai=svg.indexOf('1309.22');
const ctx2=svg.slice(Math.max(0,ai-400),ai+30);
const am=ctx2.match(/transform="translate\(([\d.]+),([\d.]+)\)"/g);
console.log('stat txt translates:',am?am.join(' | '):'NOT FOUND');
console.log('expected: x≈992, y≈375');
// graphic clipPath (group内文本裁剪区) 数量
console.log('clip paths:',(svg.match(/clipPath/g)||[]).length);
chart.dispose();
