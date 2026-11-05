import { ref } from "vue";

export default function windowResize() {
	const screenRef = ref();
	const timer = ref(0);
	let monitorTimer: number | undefined;
	let lastViewport = {
		width: 0,
		height: 0,
		ratio: 0,
	};
	const scale = {
		width: "1",
		height: "1",
	};
	const baseWidth = 1920;
	const baseHeight = 1080;

	const getViewport = () => ({
		width: window.visualViewport?.width || window.innerWidth,
		height: window.visualViewport?.height || window.innerHeight,
		ratio: window.devicePixelRatio || 1,
	});

	const calcRate = () => {
		const viewport = getViewport();
		if (screenRef.value) {
			scale.width = (viewport.width / baseWidth).toFixed(5);
			scale.height = (viewport.height / baseHeight).toFixed(5);
			screenRef.value.style.transformOrigin = "left top";
			screenRef.value.style.transform = `scale(${scale.width}, ${scale.height})`;
		}
		lastViewport = viewport;
	};

	const resize = () => {
		clearTimeout(timer.value);
		timer.value = window.setTimeout(() => {
			calcRate();
		}, 80);
	};

	const checkViewportChange = () => {
		const viewport = getViewport();
		if (
			viewport.width !== lastViewport.width ||
			viewport.height !== lastViewport.height ||
			viewport.ratio !== lastViewport.ratio
		) {
			calcRate();
		}
	};

	const windowDraw = () => {
		window.addEventListener("resize", resize);
		window.addEventListener("focus", resize);
		document.addEventListener("visibilitychange", resize);
		window.visualViewport?.addEventListener("resize", resize);
		monitorTimer = window.setInterval(checkViewportChange, 500);
	};

	const unWindowDraw = () => {
		window.removeEventListener("resize", resize);
		window.removeEventListener("focus", resize);
		document.removeEventListener("visibilitychange", resize);
		window.visualViewport?.removeEventListener("resize", resize);
		if (monitorTimer !== undefined) {
			clearInterval(monitorTimer);
		}
	};

	return {
		screenRef,
		calcRate,
		windowDraw,
		unWindowDraw,
	};
}
