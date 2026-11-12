// Export Python's Step 2 diagnostics as a readable Excel snapshot.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const work=path.dirname(fileURLToPath(import.meta.url));
const out=path.resolve(work,'../../outputs/routechoice/step2');
const p=JSON.parse(await fs.readFile(path.join(work,'step2_analysis.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('Summary');
const corr=wb.worksheets.add('Correlations');
const vif=wb.worksheets.add('Collinearity');
const quality=wb.worksheets.add('Variable quality');
const dark='#234B5C';
function base(sheet,range) {
  sheet.showGridLines=false;
  sheet.getRange(range).format={font:{name:'Arial',size:10,color:'#24343E'},rowHeight:23,columnWidth:17,verticalAlignment:'center'};
}
function header(sheet,address) {
  sheet.getRange(address).format={fill:dark,font:{name:'Arial',size:10,color:'#FFFFFF',bold:true},
    horizontalAlignment:'center',verticalAlignment:'center',wrapText:true,rowHeight:44};
}
function title(sheet,address,text) {
  sheet.getRange(address).values=[[text]];
  sheet.getRange(address).format.font={name:'Arial',size:15,bold:true,color:dark};
}
function lookup(context,a,b) {
  const m=p.matrices[context];
  return m.pearson[m.variables.indexOf(a)][m.variables.indexOf(b)];
}
base(summary,'A1:E33');
summary.tabColor=dark;
title(summary,'A2','Kannai route choice - Step 2');
summary.getRange('A3').values=[['1,199 streets; 1,280 choices; 64 OD pairs. Pearson correlations below.']];
summary.getRange('A5:E5').values=[['Attribute pair','Physical streets','Pooled routes','Within-OD averages','Within-OD exposures']];
header(summary,'A5:E5');
const pairSpecs=[
 ['Green / sidewalk','vegetation','sidewalk_width','vegetation_pct','sidewalk_m','vegetation_exposure_km','sidewalk_exposure_km_m'],
 ['Green / sky','vegetation','sky','vegetation_pct','sky_pct','vegetation_exposure_km','sky_exposure_km'],
 ['Sidewalk / sky','sidewalk_width','sky','sidewalk_m','sky_pct','sidewalk_exposure_km_m','sky_exposure_km'],
 ['Building / green','building','vegetation','building_pct','vegetation_pct','building_exposure_km','vegetation_exposure_km'],
];
summary.getRange('A6:E9').values=pairSpecs.map(([label,a,b,c,d,e,f])=>[label,
 lookup('physical_links',a,b),lookup('routes_pooled',c,d),lookup('routes_within_od',c,d),lookup('all_additive_within_od',e,f)]);
summary.getRange('B6:E9').setNumberFormat('0.000');
summary.getRange('B6:E9').conditionalFormats.add('colorScale',{colors:['#B86C5D','#FFFFFF','#4C839B'],thresholds:[{type:'num',value:-1},{type:'num',value:0},{type:'num',value:1}]});
summary.getRange('A12').values=[['Core M3 additive attributes: within-OD VIF']];
summary.getRange('A12').format.font={name:'Arial',size:11,bold:true,color:dark};
summary.getRange('A14:C14').values=[['Attribute','All 1,280 choices','677 distinct routes']];
header(summary,'A14:C14');
const core=p.vifs.filter(r=>r.context==='additive_within_od'&&r.specification==='M3');
const unique=p.vifs.filter(r=>r.context==='additive_unique_within_od');
const vifLocations=new Map();
base(vif,`A1:J${p.vifs.length+5}`);
title(vif,'A2','Collinearity diagnostics');
vif.getRange('A3').values=[['OLS design screening; VIF >= 5 is a review flag, not an automatic exclusion rule.']];
vif.getRange('A5:J5').values=[['Context','Specification','Attribute','Rows','Predictors','VIF','Auxiliary R squared','VIF >= 5 (1/0)','Design rank','Condition number']];
header(vif,'A5:J5');
vif.getRange(`A6:J${p.vifs.length+5}`).values=p.vifs.map((r,i)=>{
 vifLocations.set(`${r.context}|${r.specification}|${r.variable}`,i+6);
 return [p.titles[r.context],r.specification,p.labels[r.variable]||r.variable,r.n_rows,r.n_predictors,r.vif,
  r.r_squared_auxiliary,r.screen_vif_ge_5,r.standardized_design_rank,r.standardized_condition_number];
});
vif.getRange(`F6:G${p.vifs.length+5}`).setNumberFormat('0.000');
vif.getRange(`J6:J${p.vifs.length+5}`).setNumberFormat('0.000');
vif.getRange('A5:A80').format.columnWidth=42;
vif.getRange('B5:C80').format.columnWidth=28;
vif.getRange(`F6:F${p.vifs.length+5}`).conditionalFormats.add('cellIs',{operator:'greaterThanOrEqual',formula:5,format:{fill:'#FFF0D7',font:{bold:true,color:'#8E5428'}}});
vif.freezePanes.freezeRows(5);
vif.tables.add(`A5:J${p.vifs.length+5}`,true,'VIFDiagnostics');
for(let i=0;i<core.length;i++) {
 const n=15+i,r=core[i],u=unique.find(x=>x.variable===r.variable);
 summary.getRange(`A${n}`).values=[[p.labels[r.variable]]];
 summary.getRange(`B${n}:C${n}`).formulas=[[
  `='Collinearity'!F${vifLocations.get(`${r.context}|${r.specification}|${r.variable}`)}`,
  `='Collinearity'!F${vifLocations.get(`${u.context}|${u.specification}|${u.variable}`)}`,
 ]];
}
summary.getRange('B15:C19').setNumberFormat('0.000');
const notes=[
 'Keep distance, sidewalk, crosswalks, greenery and sky for the first model sequence.',
 'M0: distance. M1: add sidewalk/crosswalks. M2: add greenery. M3: add sky.',
 'Building visibility overlaps with greenery; test it in a separate sensitivity specification.',
 'Pooled route correlations include differences between OD pairs.',
 'Within-OD values subtract each OD mean; exposures sum length (km) x attribute.',
 'Core within-OD VIFs are low, including the distinct-route sensitivity check.',
 'These chosen-route diagnostics do not establish identification of a future choice model.',
 'Snapshot generated in Python. Rerun the analysis to refresh ranks, exposures and VIFs.',
 'Source details and quality counts are listed on Variable quality. See README.txt for methods.',
];
notes.forEach((t,i)=>summary.getRange(`A${23+i}`).values=[[t]]);
summary.getRange('A23:A31').format.font={name:'Arial',size:10,color:'#52665D'};
summary.getRange('A5:A31').format.columnWidth=29;
summary.getRange('B5:E31').format.columnWidth=23;

const contexts=Object.entries(p.matrices);
const shortTitles={physical_links:'Physical streets',directed_links:'Directed links',routes_pooled:'Routes: pooled',
 routes_within_od:'Routes: within OD',additive_pooled:'Exposures: pooled',additive_within_od:'Exposures: within OD',
 additive_unique_within_od:'Unique exposures: OD',all_additive_within_od:'All exposures: OD'};
base(corr,'A1:U125');
title(corr,'A2','Correlation matrices');
corr.getRange('A3').values=[['Pearson on the left; Spearman on the right. Inputs and transformations are documented in README.txt.']];
corr.getRange('A5:A125').format.columnWidth=25;
corr.getRange('B5:J125').format.columnWidth=14;
corr.getRange('K1:K125').format.columnWidth=3;
corr.getRange('L5:L125').format.columnWidth=25;
corr.getRange('M5:U125').format.columnWidth=14;
contexts.forEach(([name,m],i)=>{
 const start=6+i*15;
 for(const [method,col] of [['pearson',0],['spearman',11]]) {
  const range=corr.getRangeByIndexes(start-1,col,1,3);
  range.values=[[shortTitles[name],`n = ${m.n}`,method==='pearson'?'Pearson':'Spearman']];
  range.format.font={name:'Arial',size:11,bold:true,color:dark};
  const headings=['Attribute',...m.variables.map(v=>p.labels[v]||v)];
  const hr=corr.getRangeByIndexes(start,col,1,headings.length);
  hr.values=[headings];
  hr.format={fill:dark,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:45,horizontalAlignment:'center'};
  corr.getRangeByIndexes(start+1,col,m.variables.length,1).values=m.variables.map(v=>[p.labels[v]||v]);
  const data=corr.getRangeByIndexes(start+1,col+1,m.variables.length,m.variables.length);
  data.values=m[method];
  data.setNumberFormat('0.00');
  data.conditionalFormats.add('colorScale',{colors:['#B86C5D','#FFFFFF','#4C839B'],thresholds:[{type:'num',value:-1},{type:'num',value:0},{type:'num',value:1}]});
 }
});
const end=p.quality.length+5;
base(quality,`A1:J${end}`);
title(quality,'A1','Variable quality and source scope');
quality.getRange('A2').values=[['Sources: datasets/routechoice/link_kannai.csv, node_kannai.csv and path_kannai.csv.']];
quality.getRange('A3').values=[['Route inputs and physical-street inputs are supplied as CSV tables. All correlations use complete numeric data.']];
quality.getRange('A5:J5').values=[['Context','Attribute','Rows','Missing','Zeros','Minimum','Maximum','Mean','Sample SD','Distinct values']];
header(quality,'A5:J5');
quality.getRange(`A6:J${end}`).values=p.quality.map(r=>[p.titles[r.context],p.labels[r.variable],r.n_rows,r.missing_n,r.zero_n,r.min,r.max,r.mean,r.sample_sd,r.n_distinct]);
quality.getRange(`F6:I${end}`).setNumberFormat('0.000');
quality.getRange('A5:A40').format.columnWidth=35;
quality.getRange('B5:B40').format.columnWidth=23;
quality.freezePanes.freezeRows(5);
quality.tables.add(`A5:J${end}`,true,'VariableQuality');

wb.recalculate();
const actual=summary.getRange('B15:C19').values;
core.forEach((r,i)=>{if(Math.abs(actual[i][0]-r.vif)>1e-10||Math.abs(actual[i][1]-unique.find(u=>u.variable===r.variable).vif)>1e-10)
 throw new Error('Summary VIF reference mismatch');});
for(const [name,m] of contexts) {
 const i=contexts.findIndex(([key])=>key===name),start=6+i*15;
 for(const [method,col] of [['pearson',0],['spearman',11]]) {
  const values=corr.getRangeByIndexes(start+1,col+1,m.variables.length,m.variables.length).values;
  values.forEach((row,j)=>row.forEach((v,k)=>{if(Math.abs(v-m[method][j][k])>1e-12) throw new Error('Matrix export mismatch');}));
 }
}
console.log((await wb.inspect({kind:'table',range:'Summary!A5:E19',tableMaxRows:15,tableMaxCols:5,maxChars:2400})).ndjson);
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:10},maxChars:800})).ndjson);
for(const [sheetName,range,name] of [['Summary','A1:E32','summary'],['Correlations','A5:J17','correlations'],
 ['Collinearity','A1:F18','vif'],['Variable quality','A1:J15','quality']]) {
 const blob=await wb.render({sheetName,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(work,`step2_${name}_preview.png`),new Uint8Array(await blob.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'kannai_step2.xlsx'));
try {
 await fs.rename(path.join(out,'kannai_step2.xlsx.inspect.ndjson'),path.join(work,'step2_workbook_inspect.ndjson'));
} catch(error) { if(error.code!=='ENOENT') throw error; }
console.log('Validated and exported kannai_step2.xlsx');
