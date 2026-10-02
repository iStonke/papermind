import test from 'node:test';
import assert from 'node:assert/strict';
import { findFreeThoughtPosition as find } from '../src/utils/thoughtPlacement.js';
const bounds = { x:10,y:10,width:640,height:400 }, size = { width:270,height:100 };
test('uses first free spot and leaves a gap beside occupied notes', () => {
  assert.deepEqual(find(bounds,size,[]),{ x:10,y:10 });
  assert.deepEqual(find(bounds,size,[{ x:10,y:10,...size }]),{ x:344,y:10 });
});
test('moves below a full row and respects varying card heights', () => {
  assert.deepEqual(find(bounds,size,[{ x:10,y:10,width:600,height:180 }]),{ x:10,y:254 });
});
test('returns no position when the available viewport is occupied', () => {
  assert.equal(find(bounds,size,[bounds]),null);
});
