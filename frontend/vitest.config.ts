import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
	test: {
		include: ['src/**/*.test.ts'],
		passWithNoTests: true,
	},
	resolve: {
		alias: {
			$lib: path.resolve('./src/lib'),
		},
	},
});
