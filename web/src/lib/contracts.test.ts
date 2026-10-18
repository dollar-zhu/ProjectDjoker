import test from 'node:test';
import assert from 'node:assert/strict';
import { parseOptions, parseRange, validId } from './contracts';

test('accepts a normalized player rectangle and explicit capture context', () => {
  assert.deepEqual(parseOptions({crop:[.2,.1,.8,.95],view:'rear',handedness:'right'}),
    {crop:[.2,.1,.8,.95],view:'rear',handedness:'right'});
});
test('rejects inverted, outside, tiny and nonfinite crops', () => {
  for (const crop of [[.8,.1,.2,.9],[-.1,0,1,1],[0,0,.01,.02],[0,0,NaN,1]])
    assert.throws(() => parseOptions({crop,view:'rear',handedness:'right'}));
  assert.throws(() => parseOptions({crop:[0,0,1,1],view:'guess',handedness:'right'}));
});
test('media seeking supports bounded, open and suffix byte ranges', () => {
  assert.deepEqual(parseRange('bytes=10-19',100),[10,19]);
  assert.deepEqual(parseRange('bytes=90-',100),[90,99]);
  assert.deepEqual(parseRange('bytes=-20',100),[80,99]);
  assert.deepEqual(parseRange('bytes=90-200',100),[90,99]);
  assert.throws(() => parseRange('bytes=100-',100));
  assert.throws(() => parseRange('bytes=0-2,5-8',100));
});
test('job ids cannot address paths outside the job store', () => {
  assert.equal(validId('bd60abfa-af23-4e39-94c2-d162d6cdf7b6'),true);
  for(const id of ['../private','abc','%2e%2e','']) assert.equal(validId(id),false);
});
