# Action Required — QAI Consultant v2.0 Migration

## Phase 2 complete — what you need to do now

### 1. Get API keys

| Key | Where | Cost |
|-----|-------|------|
| `MISTRAL_API_KEY` | [console.mistral.ai](https://console.mistral.ai/) → API Keys | Free tier available | ✅ set in .env
| `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | Free tier available | ✅ set in .env

### 2. Create your .env file

```bash
cp .env.example .env
# then edit .env and fill in the two keys above
```

### 3. Rebuild chroma_db/ (if not present locally)

ChromaDB is still needed until Phase 3. If `chroma_db/` doesn't exist on your machine:

```bash
python src/ingest.py
```

### 4. Review GitHub security alerts

20 vulnerabilities flagged by Dependabot (2 high, 18 moderate).
→ github.com/gvasile29/qai-consultant/security/dependabot

---

## Before Phase 3 (Pinecone migration)

### 5. Create a Pinecone account and index

1. Sign up at [pinecone.io](https://pinecone.io) (free tier: 1 index, sufficient)
2. Create a new index with these exact settings:
   - **Name:** `qai-consultant`
   - **Dimensions:** `384`
   - **Metric:** `cosine`
3. Copy your API key from the Pinecone console

### 6. Add Pinecone keys to .env

```
PINECONE_API_KEY=your_pinecone_api_key_here
PINECONE_INDEX_NAME=qai-consultant
```

---

## Before Phase 4 (Streamlit Cloud deploy)

### 7. Push knowledge base to Pinecone (one-time)

```bash
python src/ingest.py   # will push to Pinecone once Phase 3 is done
```

### 8. Deploy on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. New app → repo: `gvasile29/qai-consultant`, branch: `master`, file: `src/app.py`
3. Settings → Secrets → paste all 4 keys:
   ```toml
   MISTRAL_API_KEY = "..."
   OPENROUTER_API_KEY = "..."
   PINECONE_API_KEY = "..."
   PINECONE_INDEX_NAME = "qai-consultant"
   ```

---

## Summary

| Step | When | Status |
|------|------|--------|
| Get Mistral + OpenRouter keys | Now | ⬜ |
| Create .env | Now | ⬜ |
| Rebuild chroma_db/ if missing | Now | ⬜ |
| Review Dependabot alerts | Now | ⬜ |
| Create Pinecone index | Before Phase 3 | ⬜ |
| Add Pinecone keys to .env | Before Phase 3 | ⬜ |
| Run ingest.py → Pinecone | After Phase 3 | ⬜ |
| Deploy to Streamlit Cloud | After Phase 4 | ⬜ |
