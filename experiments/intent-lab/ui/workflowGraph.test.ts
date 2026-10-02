import {describe,it,expect} from 'vitest';
import {insertBlock,connectGraph,arrangeGraph,type Graph} from './workflowGraph';

const text={es:'Verificación',en:'Verification',pt:'Verificação'};
function fixture():Graph{return {schema_version:1,name:text,nodes:[
 {id:'start',kind:'start',label:text,position:{x:0,y:0},config:{}},
 {id:'branch',kind:'condition',label:text,position:{x:260,y:0},config:{predicate:'diagnostic_failed',value:''}},
 {id:'yes',kind:'response',label:text,position:{x:520,y:0},config:{outcome:'information',text}},
 {id:'no',kind:'response',label:text,position:{x:520,y:200},config:{outcome:'information',text}},
],edges:[{id:'a',source:'start',port:'next',target:'branch'},
 {id:'b',source:'branch',port:'yes',target:'yes'},{id:'c',source:'branch',port:'no',target:'no'}]};}

describe('visual graph edits preserve the intended route',()=>{
 it('inserts on No without changing Yes or losing the continuation',()=>{
  const original=fixture(),before=structuredClone(original);
  const value=insertBlock(original,'notify',{x:520,y:200},{source:'branch',port:'no'})!;
  expect(value.graph.edges.find(e=>e.source==='branch'&&e.port==='yes')?.target).toBe('yes');
  expect(value.graph.edges.find(e=>e.source==='branch'&&e.port==='no')?.target).toBe(value.id);
  expect(value.graph.edges.find(e=>e.source===value.id)?.target).toBe('no');
  expect(value.graph.nodes.find(n=>n.id==='no')!.position.x).toBeGreaterThan(520);
  expect(original).toEqual(before);
 });
 it('does not silently cut a path by inserting a terminal inside an edge',()=>{
  expect(insertBlock(fixture(),'response',{x:130,y:0},{source:'start',port:'next'})).toBeNull();
 });
 it('reconnecting replaces both the old edge and the occupied output without duplicates',()=>{
  const graph=connectGraph(fixture(),'branch','no','yes','b');
  expect(graph.edges.filter(e=>e.source==='branch')).toHaveLength(1);
  expect(graph.edges.find(e=>e.source==='branch')).toMatchObject({port:'no',target:'yes'});
 });
 it('ordering changes positions but preserves labels, configuration and topology',()=>{
  const graph=fixture(),ordered=arrangeGraph(graph);
  expect(ordered.edges).toEqual(graph.edges);
  expect(ordered.nodes.map(({position,...rest})=>rest)).toEqual(graph.nodes.map(({position,...rest})=>rest));
  expect(new Set(ordered.nodes.map(n=>JSON.stringify(n.position))).size).toBe(4);
 });
 it('lays out the reply loop without treating it as an automatic cycle or inserting into it',()=>{
  const graph:Graph={schema_version:1,name:text,nodes:[
   {id:'start',kind:'start',label:text,position:{x:0,y:0},config:{}},
   {id:'context',kind:'context',label:text,position:{x:0,y:0},config:{}},
   {id:'ask',kind:'question',label:text,position:{x:0,y:0},config:{}},
  ],edges:[{id:'a',source:'start',target:'context',port:'next'},{id:'b',source:'context',target:'ask',port:'next'},{id:'c',source:'ask',target:'context',port:'reply'}]};
  const arranged=arrangeGraph(graph);
  expect(arranged.nodes.map(n=>n.position.x)).toEqual([0,260,520]);
  expect(arranged.edges).toEqual(graph.edges);
  expect(insertBlock(graph,'notify',{x:0,y:0},{source:'ask',port:'reply'})).toBeNull();
 });
});
