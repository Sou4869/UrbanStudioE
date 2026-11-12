import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const work = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(work, '../..');
const out = path.join(root, 'outputs/routechoice/step1');
const p = JSON.parse(await fs.readFile(path.join(work, 'step1_analysis.json'), 'utf8'));
const wb = Workbook.create();
const summary = wb.worksheets.add('Summary');
const od = wb.worksheets.add('OD comparisons');
const routes = wb.worksheets.add('Routes');
const end = p.routes.length + 5;
const odEnd = p.ods.length + 5;
const dark = '#234B5C';
function style(sh, lastCol, lastRow) {
  sh.showGridLines = false;
  const r = sh.getRange(`A1:${lastCol}${lastRow}`);
  r.format.font = {name:'Arial', size:10, color:'#24343E'};
  r.format.rowHeight = 21;
  r.format.columnWidth = 15;
  r.format.verticalAlignment = 'center';
  sh.getRange(`A5:${lastCol}5`).format = {
    fill:dark, font:{name:'Arial', size:10, bold:true, color:'#FFFFFF'},
    wrapText:true, horizontalAlignment:'center', verticalAlignment:'center', rowHeight:43,
  };
  sh.getRange(`A6:${lastCol}${lastRow}`).setNumberFormat('0.00');
  sh.getRange('A1').format.font = {name:'Arial', size:15, bold:true, color:dark};
  sh.freezePanes.freezeRows(5);
}
const routeHeaders = ['Path ID','OD ID','Origin','Destination','Link count','Chosen length (m)',
  'Shortest length (m)','Chosen green (%)','Shortest green (%)','Chosen sky (%)','Shortest sky (%)',
  'Chosen sidewalk (m)','Shortest sidewalk (m)','Chosen crosswalk links','Shortest crosswalk links',
  'Extra distance (m)','Extra distance (%)','Green difference (pp)','Sky difference (pp)',
  'Sidewalk difference (m)','Crosswalk difference','Minimum distance (1/0)'];
style(routes,'Y',end);
routes.getRange('A1').values = [['Route-level paired comparisons']];
routes.getRange('A2').values = [['Sources: link_kannai.csv, node_kannai.csv, path_kannai.csv (datasets/routechoice).']];
routes.getRange('A3').values = [['Direction-specific links; visibility and sidewalk averages weighted by length; repeated choices retained.']];
routes.getRange('A5:V5').values = [routeHeaders];
const inputKeys = ['path_id','od_id','origin','destination','n_links','length_m','shortest_length_m',
  'green_pct','shortest_green_pct','sky_pct','shortest_sky_pct','sidewalk_m','shortest_sidewalk_m',
  'crosswalk_links','shortest_crosswalk_links'];
routes.getRange(`A6:O${end}`).values = p.routes.map(r=>inputKeys.map(k=>r[k]));
routes.getRange('X5:Y7').values = [['Tolerance','Value'],['Attribute difference',1e-8],['Distance (m)',1e-6]];
routes.getRange('X5:Y5').format.fill = dark;
routes.getRange('X5:Y5').format.font = {color:'#FFFFFF',bold:true};
routes.getRange('X6:X7').format.columnWidth = 24;
routes.getRange('Y6:Y7').setNumberFormat('0.0E+00');
routes.getRange('P6:V6').formulas = [[
  '=IF(ABS(F6-G6)<$Y$7,0,F6-G6)', '=P6/G6', '=H6-I6','=J6-K6','=L6-M6','=N6-O6',
  '=IF(ABS(P6)<$Y$7,1,0)',
]];
routes.getRange(`P6:V${end}`).fillDown();
routes.getRange(`A6:E${end}`).setNumberFormat('0');
routes.getRange(`N6:O${end}`).setNumberFormat('0');
routes.getRange(`U6:V${end}`).setNumberFormat('0');
routes.getRange(`Q6:Q${end}`).setNumberFormat('0.00%');
routes.getRange('F5:V5').format.columnWidth = 17;
routes.freezePanes.freezeColumns(2);
routes.tables.add(`A5:V${end}`,true,'RouteComparisons');

const odHeaders = ['OD ID','Origin','Destination','Choices','Unique routes','Shortest length (m)',
 'Mean chosen length (m)','Mean extra distance (m)','Median extra distance (m)','Mean extra distance (%)',
 'Mean green difference (pp)','Mean sky difference (pp)','Mean sidewalk difference (m)',
 'Mean crosswalk difference','More green (%)','Equal green (%)','Less green (%)',
 'More sky (%)','Wider sidewalk (%)','Fewer crosswalk links (%)','Minimum distance (%)'];
style(od,'U',odEnd);
od.getRange('A1').values = [['Comparison by origin-destination pair']];
od.getRange('A2').values = [['20 choices per OD; all percentage denominators include equal/reference choices.']];
od.getRange('A3').values = [['All differences are chosen minus shortest. Full OD distributions are available in od_summary.csv.']];
od.getRange('A5:U5').values = [odHeaders];
od.getRange(`A6:F${odEnd}`).values = p.ods.map(r=>[r.od_id,r.origin,r.destination,r.n_choices,r.n_unique_routes,r.shortest_length_m]);
od.getRange(`I6:I${odEnd}`).values = p.ods.map(r=>[r.median_detour_m]);
const rr = col=>`'Routes'!$${col}$6:$${col}$${end}`;
for (let n=6;n<=odEnd;n++) {
 const avg=col=>`=AVERAGEIFS(${rr(col)},${rr('B')},$A${n})`;
 for(const [dest,src] of [['G','F'],['H','P'],['J','Q'],['K','R'],['L','S'],['M','T'],['N','U']])
   od.getRange(`${dest}${n}`).formulas=[[avg(src)]];
 for(const [dest,src,op] of [['O','R','>'],['P','R','='],['Q','R','<'],['R','S','>'],['S','T','>'],['T','U','<']]) {
   const criterion=op==='='?`ABS_EQUAL`:op;
   let formula;
   if(criterion==='ABS_EQUAL') formula=`=COUNTIFS(${rr('B')},$A${n},${rr(src)},">="&-'Routes'!$Y$6,${rr(src)},"<="&'Routes'!$Y$6)/D${n}`;
   else formula=`=COUNTIFS(${rr('B')},$A${n},${rr(src)},"${op}"&${op==='<'?'-':''}'Routes'!$Y$6)/D${n}`;
   od.getRange(`${dest}${n}`).formulas=[[formula]];
 }
 od.getRange(`U${n}`).formulas=[[`=SUMIFS(${rr('V')},${rr('B')},$A${n})/D${n}`]];
}
od.getRange(`A6:E${odEnd}`).setNumberFormat('0');
od.getRange(`J6:J${odEnd}`).setNumberFormat('0.00%');
od.getRange(`O6:U${odEnd}`).setNumberFormat('0.0%');
od.getRange('F5:U5').format.columnWidth = 18;
od.getRange('A62:U62').format.fill = '#FFF3DC'; // OD 56
od.freezePanes.freezeColumns(1);
od.tables.add(`A5:U${odEnd}`,true,'ODComparisons');

style(summary,'G',25);
summary.freezePanes.unfreeze();
summary.tabColor = dark;
summary.getRange('A2').values = [['Kannai route choice - Step 1']];
summary.getRange('A2').format.font = {name:'Arial',size:15,bold:true,color:dark};
summary.getRange('A3').values = [['1,280 synthetic choices | 64 OD pairs | 677 distinct routes']];
summary.getRange('A5:G5').values = [['Chosen minus shortest','Mean','Median','90th percentile','Lower (%)','Equal (%)','Higher (%)']];
const labels=['Extra distance (m)','Extra distance (%)','Green view (pp)','Sky view (pp)','Sidewalk width (m)','Crosswalk links'];
const cols=['P','Q','R','S','T','U'];
for(let i=0;i<cols.length;i++) {
 const n=i+6, col=cols[i], tol=i===0?`'Routes'!$Y$7`:`'Routes'!$Y$6`;
 summary.getRange(`A${n}`).values=[[labels[i]]];
 summary.getRange(`B${n}:G${n}`).formulas=[[
  `=AVERAGE(${rr(col)})`,`=MEDIAN(${rr(col)})`,`=PERCENTILE(${rr(col)},0.9)`,
  `=COUNTIFS(${rr(col)},"<"&-${tol})/COUNTA(${rr('A')})`,
  `=COUNTIFS(${rr(col)},">="&-${tol},${rr(col)},"<="&${tol})/COUNTA(${rr('A')})`,
  `=COUNTIFS(${rr(col)},">"&${tol})/COUNTA(${rr('A')})`,
 ]];
}
summary.getRange('A5:A25').format.columnWidth = 31;
summary.getRange('B5:G25').format.columnWidth = 18;
summary.getRange('B7:D7').setNumberFormat('0.00%');
summary.getRange('E6:G11').setNumberFormat('0.0%');
summary.getRange('A14:A16').values=[['Minimum-distance choices'],['OD pairs: mean green higher'],['OD pairs: mean green lower']];
summary.getRange('B14:B16').formulas=[
 [`=SUM(${rr('V')})/COUNTA(${rr('A')})`],
 [`=COUNTIFS('OD comparisons'!K6:K${odEnd},">"&'Routes'!$Y$6)`],
 [`=COUNTIFS('OD comparisons'!K6:K${odEnd},"<"&-'Routes'!$Y$6)`],
];
summary.getRange('B14').setNumberFormat('0.0%');
summary.getRange('B15:B16').setNumberFormat('0');
for(const [cell,text] of [
 ['A19','Green and sky differences are percentage points (pp).'],
 ['A20','Visibility and sidewalk width are length-weighted route averages.'],
 ['A21','Mean extra distance (%) averages individual route ratios.'],
 ['A22','No tied shortest paths were found across the 64 OD pairs.'],
 ['A23','Descriptive results from synthetic choices; preference effects are not estimated.'],
 ['A24','Sources and calculation tolerances are listed on Routes.'],
 ['A25','OD medians and unique-route counts are static outputs of the Python analysis.'],
]) summary.getRange(cell).values=[[text]];
summary.getRange('A19:A25').format.font={name:'Arial',size:10,color:'#52665D',italic:true};

wb.recalculate();
// Compare every Excel paired-difference cell with the independently computed Python value.
const computed=routes.getRange(`P6:V${end}`).values;
for(let i=0;i<p.routes.length;i++) {
 const r=p.routes[i];
 const expected=[r.detour_m,r.detour_pct/100,r.green_diff_pp,r.sky_diff_pp,r.sidewalk_diff_m,r.crosswalk_diff_links,r.is_minimum_distance];
 expected.forEach((v,j)=>{if(typeof computed[i][j]!=='number'||Math.abs(computed[i][j]-v)>1e-8)
   throw new Error(`Route ${i} column ${j}: ${computed[i][j]} != ${v}`);});
}
const odComputed=od.getRange(`G6:U${odEnd}`).values;
const odKeys=['mean_chosen_length_m','mean_detour_m','median_detour_m','mean_detour_pct',
 'mean_green_diff_pp','mean_sky_diff_pp','mean_sidewalk_diff_m','mean_crosswalk_diff_links',
 'green_diff_pp_higher_share_pct','green_diff_pp_equal_share_pct','green_diff_pp_lower_share_pct',
 'sky_diff_pp_higher_share_pct','sidewalk_diff_m_higher_share_pct','crosswalk_diff_links_lower_share_pct','minimum_distance_share_pct'];
for(let i=0;i<p.ods.length;i++) odKeys.forEach((k,j)=>{
 const expected=p.ods[i][k]/(k.endsWith('_pct')?100:1);
 if(typeof odComputed[i][j]!=='number'||Math.abs(odComputed[i][j]-expected)>1e-8)
   throw new Error(`OD ${i} ${k}: ${odComputed[i][j]} != ${expected}`);
});
const overall=summary.getRange('B6:G11').values;
for(let i=0;i<p.summary.length;i++) {
 const r=p.summary[i], scale=r.metric==='detour_pct'?100:1;
 const expected=[r.mean/scale,r.median/scale,r.p90/scale,r.lower_share_pct/100,r.equal_share_pct/100,r.higher_share_pct/100];
 expected.forEach((v,j)=>{if(typeof overall[i][j]!=='number'||Math.abs(overall[i][j]-v)>1e-8)
   throw new Error(`Summary ${i}/${j} does not match Python analysis`);});
}
// Verify that changing a route input updates dependent OD and overall outputs, then restore it.
const originalGreen=routes.getRange('H6').values[0][0];
const originalODGreen=od.getRange('K6').values[0][0];
const originalMoreGreen=od.getRange('O6').values[0][0];
routes.getRange('H6').values=[[originalGreen+5]];
if(Math.abs(od.getRange('K6').values[0][0]-originalODGreen-5/20)>1e-8 ||
   Math.abs(od.getRange('O6').values[0][0]-originalMoreGreen-1/20)>1e-8 ||
   Math.abs(summary.getRange('B8').values[0][0]-p.summary[2].mean-5/1280)>1e-8)
  throw new Error('Dependent formulas did not update after a route input change');
routes.getRange('H6').values=[[originalGreen]];
wb.recalculate();
if(Math.abs(summary.getRange('B8').values[0][0]-p.summary[2].mean)>1e-8)
  throw new Error('Temporary input change was not fully restored');
console.log((await wb.inspect({kind:'table',range:'Summary!A5:G16',include:'values,formulas',tableMaxRows:12,tableMaxCols:7,maxChars:3500})).ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1500});
console.log(errors.ndjson);
for(const [sheetName,range,name] of [['Summary','A1:G25','summary'],['OD comparisons','A1:K12','od'],['Routes','A1:K12','routes']]) {
 const preview=await wb.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(path.join(work,`step1_${name}_preview.png`),new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'kannai_step1.xlsx'));
console.log('Validated and exported kannai_step1.xlsx');
