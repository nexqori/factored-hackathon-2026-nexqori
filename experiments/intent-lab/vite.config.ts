import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ root: 'experiments/intent-lab', plugins: [react()], server: { host: '127.0.0.1', port: 5191, strictPort: true, proxy: { '/lab-api': 'http://127.0.0.1:5190' } }, build: { outDir: 'dist', emptyOutDir: true } });
