// Cloudflare Pages Functions are bundled by wrangler's esbuild, which loads
// .txt imports as text modules (string default export). This declaration
// teaches TypeScript the same contract.
declare module '*.txt' {
  const text: string;
  export default text;
}
