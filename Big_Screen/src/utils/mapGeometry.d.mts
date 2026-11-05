export function polygonRings(geometry: any): number[][][][];
export function mercator(longitude: number, latitude: number): [number, number];
export function createProjection(collection: any): (longitude: number, latitude: number) => [number, number];
export function projectionFrame(collection: any): {project: (longitude: number, latitude: number) => [number, number]; bounds: number[]; center: number[]; scale: number};
export function reliefUV(x: number, y: number, bounds: number[]): [number, number];
export function sampleHeight(pixels: Uint8ClampedArray, width: number, height: number, u: number, v: number): number;
export function pointInPolygon(x: number, y: number, rings: number[][][]): boolean;
export function pointCoordinates(point: any): [number, number] | null;
export function pointColor(point: any): string;
