import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createProjection, polygonRings, mercator, pointCoordinates, pointColor, projectionFrame, reliefUV, sampleHeight, pointInPolygon } from '../src/utils/mapGeometry.mjs';

test('projection shares one coordinate space for region rings, holes and geographic markers', () => {
  const ring = [[120, 40], [124, 40], [124, 44], [120, 44], [120, 40]];
  const hole = [[121, 41], [122, 41], [122, 42], [121, 41]];
  const geometry = {type: 'Polygon', coordinates: [ring, hole]};
  assert.equal(polygonRings(geometry)[0].length, 2);
  assert.equal(polygonRings({type: 'MultiPolygon', coordinates: [[ring], [hole]]}).length, 2);
  const project = createProjection({features: [{geometry}]});
  assert.ok(Math.abs(project(122, 40)[0]) < 1e-10);
  assert.ok(project(120, 40)[0] < project(124, 40)[0]);
  assert.ok(project(120, 40)[1] < project(120, 44)[1]);
  assert.ok(Math.abs(project(120, 44)[1] - project(120, 40)[1] - 20) < 1e-9);
  assert.ok(mercator(120, 90).every(Number.isFinite));
});

test('invalid coordinates are excluded while valid zeroes and API formats are preserved', () => {
  assert.deepEqual(pointCoordinates({value: [0, 0, 20]}), [0, 0]);
  assert.deepEqual(pointCoordinates({longitude: '123.4', latitude: '41.8'}), [123.4, 41.8]);
  for (const item of [{value: ['', 40]}, {longitude: NaN, latitude: 40}, {value: [181, 40]}, {}]) {
    assert.equal(pointCoordinates(item), null);
  }
});

test('risk color uses reported levels and does not invent thresholds from marker height', () => {
  assert.equal(pointColor({level: '高'}), '#ff6e6e');
  assert.equal(pointColor({risk_level: '较高'}), '#ffad66');
  assert.equal(pointColor({warning_level: '黄色'}), '#f4d57b');
  assert.equal(pointColor({level: '低'}), '#68d7f4');
  assert.equal(pointColor({value: [123, 41, 99]}), '#b8ecdb');
});

test('DEM UVs remain geographic when changing from province to city scale', () => {
  const rectangle = (west, south, east, north) => ({features:[{geometry:{type:'Polygon',coordinates:[[[west,south],[east,south],[east,north],[west,north],[west,south]]]}}]});
  const demBounds = [2, .7, 2.3, .9];
  const geographic = mercator(123.4, 41.8);
  const expected = reliefUV(...geographic, demBounds);
  for (const collection of [rectangle(118, 38, 126, 44), rectangle(123, 41, 124, 43)]) {
    const frame = projectionFrame(collection);
    const [x, y] = frame.project(123.4, 41.8);
    const uv = reliefUV(x / frame.scale + frame.center[0], y / frame.scale + frame.center[1], demBounds);
    assert.ok(Math.abs(uv[0] - expected[0]) < 1e-10);
    assert.ok(Math.abs(uv[1] - expected[1]) < 1e-10);
  }
});

test('height sampling flips north-to-south pixel rows and interpolates point heights', () => {
  const pixels = new Uint8ClampedArray([255,0,0,255, 128,0,0,255, 64,0,0,255, 0,0,0,255]);
  assert.equal(sampleHeight(pixels, 2, 2, 0, 1), 1);
  assert.equal(sampleHeight(pixels, 2, 2, 1, 0), 0);
  assert.ok(Math.abs(sampleHeight(pixels, 2, 2, .5, .5) - 447 / (4 * 255)) < 1e-10);
  assert.equal(sampleHeight(pixels, 2, 2, -5, 3), 1);
});

test('offline DEM image dimensions match metadata and cover the province bounds', () => {
  const metadata = JSON.parse(readFileSync(new URL('../src/assets/terrain/metadata.json', import.meta.url)));
  const png = readFileSync(new URL('../src/assets/terrain/liaoning-height.png', import.meta.url));
  assert.equal(png.readUInt32BE(16), metadata.width);
  assert.equal(png.readUInt32BE(20), metadata.height);
  assert.equal(png[24], 8);
  const province = JSON.parse(readFileSync(new URL('../src/common/echart/map/liaoning.json', import.meta.url)));
  for (const feature of province.features) for (const polygon of polygonRings(feature.geometry)) {
    for (const ring of polygon) for (const [lng, lat] of ring) {
      assert.ok(lng >= metadata.bounds[0] && lng <= metadata.bounds[2]);
      assert.ok(lat >= metadata.bounds[1] && lat <= metadata.bounds[3]);
    }
  }
});

test('surface hit testing rejects alpha-masked areas and polygon holes', () => {
  const rings = [[[0,0],[10,0],[10,10],[0,10],[0,0]], [[4,4],[6,4],[6,6],[4,6],[4,4]]];
  assert.equal(pointInPolygon(2,2,rings), true);
  assert.equal(pointInPolygon(5,5,rings), false);
  assert.equal(pointInPolygon(11,2,rings), false);
});
