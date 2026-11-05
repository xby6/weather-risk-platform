import terrainUrl from '@/assets/terrain/liaoning-relief.webp';
import slateUrl from '@/assets/terrain/liaoning-slate.webp';
import heightUrl from '@/assets/terrain/liaoning-height.png';
import metadata from '@/assets/terrain/metadata.json';

export { metadata as reliefMetadata };
export interface ReliefAssets {
  terrain: HTMLImageElement;
  slate: HTMLImageElement;
  height: HTMLImageElement;
  pixels: Uint8ClampedArray;
  width: number;
  heightPixels: number;
}
let pending: Promise<ReliefAssets> | undefined;
export function loadReliefAssets() {
  if (!pending) {
    const load = (url: string) => new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Relief texture could not be loaded'));
      image.src = url;
    });
    pending = Promise.all([load(terrainUrl), load(slateUrl), load(heightUrl)]).then(([terrain, slate, height]) => {
      const canvas = document.createElement('canvas');
      canvas.width = height.width;
      canvas.height = height.height;
      const context = canvas.getContext('2d', { willReadFrequently: true })!;
      context.drawImage(height, 0, 0);
      return { terrain, slate, height, width: canvas.width, heightPixels: canvas.height,
        pixels: context.getImageData(0, 0, canvas.width, canvas.height).data };
    }).catch(error => { pending = undefined; throw error; });
  }
  return pending;
}
