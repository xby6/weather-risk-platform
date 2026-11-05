import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "path";
import net from "node:net";
import compress from "vite-plugin-compression";
import { visualizer } from "rollup-plugin-visualizer";
// import viteImagemin from 'vite-plugin-imagemin';

const backendHost = "127.0.0.1";
const backendPort = 9099;

function backendAvailabilityGuard() {
	return {
		name: "backend-availability-guard",
		configureServer(server) {
			server.middlewares.use("/api", (_req, res, next) => {
				let settled = false;
				const socket = net.connect({ host: backendHost, port: backendPort });

				const finish = (isAvailable: boolean) => {
					if (settled) return;
					settled = true;
					socket.destroy();

					if (isAvailable) {
						next();
						return;
					}

					res.statusCode = 502;
					res.setHeader("Content-Type", "application/json; charset=utf-8");
					res.end(JSON.stringify({
						code: 502,
						msg: `RuoYi 后端未启动，请先启动 ${backendHost}:${backendPort}`
					}));
				};

				socket.setTimeout(500);
				socket.once("connect", () => finish(true));
				socket.once("timeout", () => finish(false));
				socket.once("error", () => finish(false));
			});
		}
	};
}

// https://vitejs.dev/config/
export default defineConfig({
	resolve: {
		extensions: [".js", ".vue", ".json", "scss", ".ts"],
		alias: [
			{
				find: "@",
				replacement: resolve(__dirname, "src"),
			},
			{
				find: "components",
				replacement: resolve(__dirname, "src/components"),
			},
			{
				find: "utils",
				replacement: resolve(__dirname, "src/utils"),
			},
		],
	},
	server: {
		open: true,
		port: 6688,
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:9099', // 后端真实地址
				changeOrigin: true,
				rewrite: (path) => path.replace(/^\/api/, '')
			}
		}
	},
	esbuild: {
		drop: ["console", "debugger"],
	},
	build: {
		assetsDir: "./static",
		chunkSizeWarningLimit: 500,
		minify: "esbuild",
		cssCodeSplit: true, // 如果设置为false，整个项目中的所有 CSS 将被提取到一个 CSS 文件中
		rollupOptions: {
			output: {
				// manualChunks: {
				// 	// 拆分代码，这个就是分包，配置完后自动按需加载，现在还比不上webpack的splitchunk，不过也能用了。
				// 	vue: ["vue", "vue-router", "vuex"],
				// 	echarts: ["echarts"],
				// },
				manualChunks(id) {
					if (id.includes("node_modules")) {
						return id
							.toString()
							.split("node_modules/")[1]
							.split("/")[0]
							.toString();
					}
				},
			},
		},
		// brotliSize: false,
	},
	plugins: [
		backendAvailabilityGuard(),
		vue(),
		compress(),
		// viteImagemin({
		// 	gifsicle: {
		// 		optimizationLevel: 7,
		// 		interlaced: false,
		// 	},
		// 	optipng: {
		// 		optimizationLevel: 7,
		// 	},
		// 	mozjpeg: {
		// 		quality: 20,
		// 	},
		// 	pngquant: {
		// 		quality: [0.8, 0.9],
		// 		speed: 4,
		// 	},
		// 	svgo: {
		// 		plugins: [
		// 			{
		// 				name: "removeViewBox",
		// 			},
		// 			{
		// 				name: "removeEmptyAttrs",
		// 				active: false,
		// 			},
		// 		],
		// 	},
		// }),
        visualizer(),
	],
});
