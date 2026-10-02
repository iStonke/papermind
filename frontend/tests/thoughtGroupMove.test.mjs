import test from 'node:test';
import assert from 'node:assert/strict';
import { shiftedThoughtPositions as shift } from '../src/utils/thoughtGroupMove.js';
const group = [{ pin:{ id:'a' },position:{ x:20,y:50 } },{ pin:{ id:'b' },position:{ x:320,y:100 } }];
test('moves the entire group by the same delta without changing original positions', () => {
  assert.deepEqual(shift(group,12.4,30.6),[{ id:'a',x:32,y:81 },{ id:'b',x:332,y:131 }]);
  assert.equal(group[0].position.x,20);
});
test('clamps the group at canvas boundaries while preserving spacing', () => {
  assert.deepEqual(shift(group,-100,-200),[{ id:'a',x:0,y:0 },{ id:'b',x:300,y:50 }]);
  const right = shift(group,100000,100000);
  assert.equal(right[1].x,100000);
  assert.equal(right[1].x-right[0].x,300);
  assert.equal(right[1].y-right[0].y,50);
});
