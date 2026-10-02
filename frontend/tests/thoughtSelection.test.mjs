import test from 'node:test';
import assert from 'node:assert/strict';
import { selectionRect, intersectingThoughtIds } from '../src/utils/thoughtSelection.js';
test('selection rectangle works in every drag direction', () => {
  assert.deepEqual(selectionRect({ x:80,y:60 },{ x:10,y:20 }),{ x:10,y:20,width:70,height:40 });
});
test('selects intersecting notes, excluding notes outside or touching only the edge', () => {
  assert.deepEqual(intersectingThoughtIds({ x:0,y:0,width:100,height:100 },[
    { id:'a',x:10,y:10,width:20,height:20 },
    { id:'b',x:90,y:90,width:20,height:20 },
    { id:'c',x:100,y:10,width:20,height:20 },
  ]),['a','b']);
});
