import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			fallback: 'index.html'
		})
	},
	onwarn: (warning, handler) => {
		if (warning.code.startsWith('a11y_')) return;
		handler(warning);
	}
};

export default config;
