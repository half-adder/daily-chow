import { solveLocal, type LpModelInput } from './solver';
import type { Food } from './api';

type WorkerMessage =
	| { type: 'init'; foods: Record<number, Food> }
	| { type: 'solve'; id: number; input: Omit<LpModelInput, 'foods'> };

let foods: Record<number, Food> = {};

self.onmessage = async (e: MessageEvent<WorkerMessage>) => {
	const msg = e.data;
	if (msg.type === 'init') {
		foods = msg.foods;
		return;
	}
	const { id, input } = msg;
	try {
		const result = await solveLocal({ ...input, foods });
		self.postMessage({ id, result });
	} catch (error) {
		self.postMessage({ id, error: String(error) });
	}
};
