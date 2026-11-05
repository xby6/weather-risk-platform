// Mercator coordinates shared by region meshes, labels and API point markers.
const radians = Math.PI / 180;
export function polygonRings(geometry) {
  if (geometry?.type === 'Polygon') return [geometry.coordinates];
  if (geometry?.type === 'MultiPolygon') return geometry.coordinates;
  return [];
}
export function mercator(longitude, latitude) {
  const lat = Math.max(-85, Math.min(85, latitude)) * radians;
  return [longitude * radians, Math.log(Math.tan(Math.PI / 4 + lat / 2))];
}
export function projectionFrame(collection) {
  const coordinates = collection.features.flatMap(feature => polygonRings(feature.geometry).flat(2));
  const projected = coordinates.map(pair => mercator(pair[0], pair[1]));
  const xs = projected.map(pair => pair[0]), ys = projected.map(pair => pair[1]);
  const bounds = [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  const scale = 20 / Math.max(bounds[2] - bounds[0], bounds[3] - bounds[1], 0.000001);
  const center = [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
  const project = (longitude, latitude) => {
    const [x, y] = mercator(longitude, latitude);
    return [(x - center[0]) * scale, (y - center[1]) * scale];
  };
  return { project, bounds, center, scale };
}
export function createProjection(collection) {
  return projectionFrame(collection).project;
}
export function reliefUV(x, y, bounds) {
  return [(x - bounds[0]) / (bounds[2] - bounds[0]), (y - bounds[1]) / (bounds[3] - bounds[1])];
}
export function sampleHeight(pixels, width, height, u, v) {
  // Canvas pixel rows start at north; texture UVs start at south.
  const x = Math.max(0, Math.min(width - 1, u * (width - 1)));
  const y = Math.max(0, Math.min(height - 1, (1 - v) * (height - 1)));
  const left = Math.floor(x), top = Math.floor(y);
  const right = Math.min(width - 1, left + 1), bottom = Math.min(height - 1, top + 1);
  const at = (column, row) => pixels[(row * width + column) * 4] / 255;
  const north = at(left, top) * (1 - x + left) + at(right, top) * (x - left);
  const south = at(left, bottom) * (1 - x + left) + at(right, bottom) * (x - left);
  return north * (1 - y + top) + south * (y - top);
}
export function pointInPolygon(x, y, rings) {
  const contains = ring => {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  };
  return Boolean(rings[0] && contains(rings[0]) && !rings.slice(1).some(contains));
}
export function pointCoordinates(point) {
  const lng = point?.value?.[0] ?? point?.longitude ?? point?.lng;
  const lat = point?.value?.[1] ?? point?.latitude ?? point?.lat;
  if (lng === '' || lat === '' || lng == null || lat == null) return null;
  const values = [Number(lng), Number(lat)];
  return values.every(Number.isFinite) && Math.abs(values[0]) <= 180 && Math.abs(values[1]) <= 85 ? values : null;
}
export function pointColor(point) {
  const level = String(point?.risk_level ?? point?.warning_level ?? point?.level ?? '');
  if (/红|^高$|^I$/.test(level)) return '#ff6e6e';
  if (/橙|较高|^II$/.test(level)) return '#ffad66';
  if (/黄|一般|^III$/.test(level)) return '#f4d57b';
  if (/蓝|低|^IV$/.test(level)) return '#68d7f4';
  return '#b8ecdb';
}
