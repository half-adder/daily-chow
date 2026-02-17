import { solveLocal, type LpModelInput } from './solver';

interface WorkerMessage {
	id: number;
	input: LpModelInput;
}

self.onmessage = async (e: MessageEvent<WorkerMessage>) => {
	const { id, input } = e.data;
	try {
		const result = await solveLocal(input);
		self.postMessage({ id, result });
	} catch (error) {
		self.postMessage({ id, error: String(error) });
	}
};
