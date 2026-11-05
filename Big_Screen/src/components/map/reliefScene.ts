import * as THREE from 'three';
import { mercator, polygonRings, projectionFrame, reliefUV, sampleHeight, pointInPolygon } from '@/utils/mapGeometry.mjs';
import { reliefMetadata, type ReliefAssets } from '@/utils/terrainAssets';

export function buildReliefScene(group: THREE.Group, geoJson: any, terrain: boolean,
  assets: ReliefAssets, anisotropy: number) {
  const { project, bounds, center, scale } = projectionFrame(geoJson);
  // A thin geographic relief sheet and a floating command plate are different spatial models.
  const depth = terrain ? 0.045 : 1.5;
  const amplitude = terrain ? 1.0 : .30;
  const pickable: THREE.Object3D[] = [];
  const regions: {name: string; polygons: number[][][][]}[] = [];
  const labels: { name: string; position: THREE.Vector3 }[] = [];
  const animated: THREE.ShaderMaterial[] = [];
  const width = (bounds[2] - bounds[0]) * scale;
  const height = (bounds[3] - bounds[1]) * scale;
  const texture = (image: HTMLImageElement, color = false) => {
    const result = new THREE.Texture(image);
    if (color) result.colorSpace = THREE.SRGBColorSpace;
    result.anisotropy = anisotropy;
    result.needsUpdate = true;
    return result;
  };
  const albedo = texture(terrain ? assets.terrain : assets.slate, true);
  const elevationTexture = texture(assets.height);
  const uvAt = (x: number, y: number) => reliefUV(x / scale + center[0], y / scale + center[1], reliefMetadata.mercatorBounds);
  const surfaceZ = (lng: number, lat: number) => {
    const [x, y] = mercator(lng, lat);
    const [u, v] = reliefUV(x, y, reliefMetadata.mercatorBounds);
    return depth + 0.035 + amplitude * sampleHeight(assets.pixels, assets.width, assets.heightPixels, u, v);
  };
  const uvGeometry = (geometry: THREE.BufferGeometry) => {
    const positions = geometry.getAttribute('position');
    const uv = geometry.getAttribute('uv');
    for (let i = 0; i < positions.count; i++) {
      const [u, v] = uvAt(positions.getX(i), positions.getY(i));
      uv.setXY(i, u, v);
    }
  };

  // The same geographic UVs feed the raster, height sampler and polygon alpha mask.
  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = maskCanvas.height = 2048;
  const maskContext = maskCanvas.getContext('2d')!;
  maskContext.fillStyle = '#000';
  maskContext.fillRect(0, 0, 2048, 2048);
  maskContext.fillStyle = '#fff';
  for (const feature of geoJson.features) {
    for (const polygon of polygonRings(feature.geometry)) {
      maskContext.beginPath();
      for (const ring of polygon) {
        ring.forEach((pair, index) => {
          const [mx, my] = mercator(pair[0], pair[1]);
          const [u, v] = reliefUV(mx, my, reliefMetadata.mercatorBounds);
          if (index === 0) maskContext.moveTo(u * 2048, (1 - v) * 2048);
          else maskContext.lineTo(u * 2048, (1 - v) * 2048);
        });
        maskContext.closePath();
      }
      maskContext.fill('evenodd');
    }
  }
  const mask = new THREE.CanvasTexture(maskCanvas);
  const cap = new THREE.MeshStandardMaterial({ map: albedo, color: '#9caaa9', roughness: 1 });
  const side = terrain ? new THREE.MeshStandardMaterial({color: '#273c33', roughness: 0.9}) : new THREE.ShaderMaterial({
    uniforms: { time: {value: 0}, depth: {value: depth} },
    vertexShader: `varying float h; varying vec2 xy; void main(){ h=position.z; xy=position.xy; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
    fragmentShader: `uniform float time; uniform float depth; varying float h; varying vec2 xy;
      void main(){float t=clamp(h/depth,0.,1.);vec3 c=mix(vec3(.006,.022,.065),vec3(.035,.23,.66),pow(t,.5));
      c+=vec3(.025,.22,.9)*exp(-pow((t-.20)*10.,2.));
      c+=vec3(.10,.4,.95)*pow(t,14.);
      float scan=pow(max(0.,sin(xy.x*.8+xy.y*.7-time*.65)),24.); c+=vec3(.025,.10,.23)*scan;
      gl_FragColor=vec4(c,1.);}`
  });
  if (side instanceof THREE.ShaderMaterial) animated.push(side);
  const borders = new THREE.LineBasicMaterial({color: terrain ? '#cfccb1' : '#b1d3e5', transparent: true, opacity: terrain ? 0.20 : 0.32});
  const lowerBorder = new THREE.LineBasicMaterial({color: '#398bff', transparent: true, opacity: 0.65});
  const supportMaterial = new THREE.MeshBasicMaterial({color: '#092c67'});
  const tracerPositions: number[] = [];
  const tracerPhases: number[] = [];
  for (const feature of geoJson.features) {
    const name = feature.properties.name;
    regions.push({name, polygons: polygonRings(feature.geometry).map(polygon => polygon.map(ring => ring.map(pair => project(pair[0], pair[1]))))});
    for (const polygon of polygonRings(feature.geometry)) {
      if (!polygon[0]?.length) continue;
      const vectors = (ring: number[][]) => ring.map(pair => new THREE.Vector2(...project(pair[0], pair[1])));
      const shape = new THREE.Shape(vectors(polygon[0]));
      for (const hole of polygon.slice(1)) shape.holes.push(new THREE.Path(vectors(hole)));
      const smallIsland = !terrain && Math.abs(THREE.ShapeUtils.area(shape.getPoints())) < .045;
      const geometry = smallIsland ? new THREE.ShapeGeometry(shape) : new THREE.ExtrudeGeometry(shape, {depth, bevelEnabled: false, steps: 1});
      uvGeometry(geometry);
      const mesh = new THREE.Mesh(geometry, smallIsland ? cap : [cap, side]);
      if (smallIsland) mesh.position.z = depth;
      mesh.userData = {kind: 'region', name};
      group.add(mesh);
      pickable.push(mesh);
      if (!terrain && !smallIsland) {
        const support = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, {depth:.28, bevelEnabled:false}), supportMaterial);
        support.position.z = -.62;
        group.add(support);
      }
      for (const ring of polygon) {
        const topEdge = ring.map(pair => {const [x, y] = project(pair[0], pair[1]); return new THREE.Vector3(x, y, surfaceZ(pair[0], pair[1]) + .02);});
        group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(topEdge), borders));
        if (!terrain && !smallIsland) {
          const bottomEdge = topEdge.map(point => new THREE.Vector3(point.x, point.y, .025));
          group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(bottomEdge), lowerBorder));
          const rail = topEdge.map(point => new THREE.Vector3(point.x, point.y, -.34));
          group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(rail), lowerBorder));
          // Decorative scanning along administrative edges; these are not power connections.
          const curve = new THREE.CurvePath<THREE.Vector3>();
          for (let i = 1; i < topEdge.length; i++) curve.add(new THREE.LineCurve3(topEdge[i - 1], topEdge[i]));
          if (curve.getLength() > 1) {
            const samples = curve.getSpacedPoints(Math.min(240, Math.ceil(curve.getLength() * 14)));
            samples.forEach((point, i) => {tracerPositions.push(point.x, point.y, point.z + .025); tracerPhases.push(i / samples.length + labels.length * .13);});
          }
        }
      }
    }
    const anchor = feature.properties.centroid || feature.properties.center;
    if (anchor) {
      const [x, y] = project(anchor[0], anchor[1]);
      labels.push({name, position: new THREE.Vector3(x, y, surfaceZ(anchor[0], anchor[1]) + .16)});
    }
  }

  const surface = new THREE.PlaneGeometry(width, height, Math.max(32, Math.round(width * 13)), Math.max(32, Math.round(height * 13)));
  const positions = surface.getAttribute('position');
  for (let i = 0; i < positions.count; i++) {
    const [u, v] = uvAt(positions.getX(i), positions.getY(i));
    positions.setZ(i, depth + .035 + amplitude * sampleHeight(assets.pixels, assets.width, assets.heightPixels, u, v));
  }
  uvGeometry(surface);
  surface.computeVertexNormals();
  surface.computeBoundingSphere();
  const surfaceMesh = new THREE.Mesh(surface, new THREE.MeshStandardMaterial({
    map: albedo, alphaMap: mask, alphaTest: .5, bumpMap: elevationTexture, bumpScale: terrain ? .13 : .22,
    roughness: .98, metalness: .025, color: terrain ? '#dce6c7' : '#c0d5df'
  }));
  surfaceMesh.userData.kind = 'surface';
  group.add(surfaceMesh);
  pickable.push(surfaceMesh);

  if (!terrain) {
    const haloGeometry = new THREE.PlaneGeometry(width, height);
    uvGeometry(haloGeometry);
    const halo = new THREE.Mesh(haloGeometry, new THREE.MeshBasicMaterial({alphaMap: mask, color: '#0b69f3',
      transparent: true, opacity: .24, blending: THREE.AdditiveBlending, depthWrite: false}));
    halo.position.z = -.65;
    halo.scale.set(1.026, 1.026, 1);
    group.add(halo);
  }
  if (!terrain && tracerPositions.length) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(tracerPositions, 3));
    geometry.setAttribute('phase', new THREE.Float32BufferAttribute(tracerPhases, 1));
    const material = new THREE.ShaderMaterial({
      uniforms:{time:{value:0}}, transparent:true, depthWrite:false, blending:THREE.AdditiveBlending,
      vertexShader:`attribute float phase; uniform float time; varying float intensity;
        void main(){ float t=fract(phase-time*.065); intensity=t>.84?pow((t-.84)/.16,2.):0.;
        gl_PointSize=2.+intensity*3.; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.); }`,
      fragmentShader:`varying float intensity; void main(){float r=length(gl_PointCoord-.5)*2.;
        gl_FragColor=vec4(vec3(.45,.75,1.),intensity*(1.-smoothstep(.2,1.,r))*.85);}`
    });
    group.add(new THREE.Points(geometry,material));
    animated.push(material);
  }
  const grid = new THREE.GridHelper(terrain ? 64 : 44, terrain ? 42 : 28, terrain ? '#7c897a' : '#23465f', terrain ? '#536450' : '#142a3d');
  grid.rotation.x = Math.PI / 2;
  grid.position.z = terrain ? -.10 : -.75;
  (grid.material as THREE.Material).transparent = true;
  (grid.material as THREE.Material).opacity = terrain ? .20 : .10;
  group.add(grid);
  if (!terrain) for (const [radius, opacity] of [[12.5, .4], [13.2, .18], [13.7, .08]]) {
    const positions = Array.from({length: 241}, (_, i) => new THREE.Vector3(Math.cos(i / 240 * Math.PI * 2) * radius, Math.sin(i / 240 * Math.PI * 2) * radius, -.72));
    const ring = new THREE.Line(new THREE.BufferGeometry().setFromPoints(positions), new THREE.LineDashedMaterial({color:'#6baddf', transparent:true, opacity, dashSize:.10, gapSize:.12}));
    ring.computeLineDistances();
    group.add(ring);
  }
  const stars = new Float32Array(120 * 3);
  for (let i = 0; i < 120; i++) {stars[i * 3] = Math.sin(i * 71.17) * 25; stars[i * 3 + 1] = Math.cos(i * 13.71) * 25; stars[i * 3 + 2] = terrain ? -.09 : -.70;}
  const starGeometry = new THREE.BufferGeometry();
  starGeometry.setAttribute('position', new THREE.BufferAttribute(stars, 3));
  group.add(new THREE.Points(starGeometry, new THREE.PointsMaterial({color: terrain ? '#b7c3b1' : '#8ebbdc', size:.027, transparent:true, opacity:.35})));
  return {project, surfaceZ, pickable, labels,
    regionAt: (x: number, y: number) => regions.find(region => region.polygons.some(polygon => pointInPolygon(x, y, polygon)))?.name,
    update: (time: number) => animated.forEach(material => {material.uniforms.time.value = time;})};
}

export function glowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const context = canvas.getContext('2d')!;
  const glow = context.createRadialGradient(32, 32, 1, 32, 32, 31);
  glow.addColorStop(0, '#fff');
  glow.addColorStop(.12, '#ffffffcc');
  glow.addColorStop(.4, '#ffffff30');
  glow.addColorStop(1, '#ffffff00');
  context.fillStyle = glow;
  context.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(canvas);
}

export function beamMaterial(color: string) {
  return new THREE.ShaderMaterial({
    uniforms: {color: {value: new THREE.Color(color)}}, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `varying vec2 t; void main(){t=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
    fragmentShader: `uniform vec3 color; varying vec2 t; void main(){float a=pow(1.-abs(t.x*2.-1.),2.)*pow(1.-t.y,1.8);gl_FragColor=vec4(color,a*.65);}`
  });
}
