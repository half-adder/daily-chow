import adapter from '@sveltejs/adapter-node';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter()
	},
	onwarn: (warning, handler) => {
		if (warning.code.startsWith('a11y_')) return;
		handler(warning);
	}
};

export default config;
