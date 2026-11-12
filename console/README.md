# Veritas RAG Console

Next.js chat client for the Veritas RAG API. Streaming answers, citations with
page numbers, refusal states, and a live request trace panel.

## Run

```bash
cd console
npm install
cp .env.example .env.local   # point NEXT_PUBLIC_API_URL at the API (default http://localhost:8000)
npm run dev
```

Open http://localhost:3000. The API runs separately with `make api` from the
repository root.
