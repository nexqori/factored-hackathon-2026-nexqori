import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
// Local-only developer proxy; production requests keep their original Origin.
const proxy = { '/api': { target: 'http://localhost:5180', changeOrigin: true, headers: { Origin: 'http://localhost:5180' } } };
export default defineConfig({ plugins: [react()], server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy }, preview: { host: '127.0.0.1', port: 4180, strictPort: true, proxy } });
