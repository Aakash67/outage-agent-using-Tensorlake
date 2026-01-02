# Outage Agent - Workflow Options

## Two Paths to Test

### Path 1: Local Testing (No Deployment Needed) ✅

**Use this to test the agent logic locally first**

1. Set environment variables:
   ```powershell
   $env:GROQ_API_KEY = "your_key"
   $env:EXA_API_KEY = "your_key"
   ```

2. Test agent directly:
   ```bash
   python outage_agent.py
   ```

3. **OR** Use Streamlit UI in **Local Mode**:
   ```bash
   streamlit run streamlit_app.py
   ```
   - In the sidebar, select: **"💻 Local Testing"**
   - This runs `run_local_application()` - no endpoint needed
   - No deployment required

### Path 2: Remote/Cloud Testing (Deployment Required) 🌐

**Use this to test the deployed endpoint on Tensorlake Cloud**

1. Set Tensorlake API key:
   ```powershell
   $env:TENSORLAKE_API_KEY = "your_key"
   ```

2. **Deploy to Tensorlake Cloud** (creates the endpoint):
   ```bash
   tensorlake deploy outage_agent.py
   ```
   This creates: `https://api.tensorlake.ai/applications/outage_agent`

3. Test the remote endpoint:
   ```bash
   python test_remote_outage_agent.py
   ```

4. **OR** Use Streamlit UI in **Remote Mode**:
   ```bash
   streamlit run streamlit_app.py
   ```
   - In the sidebar, select: **"☁️ Tensorlake Cloud (Remote)"**
   - This calls `run_remote_application("outage_agent", alert)` - uses the deployed endpoint

## Recommended Sequence

### Option A: Local First (Faster Development)
1. ✅ Test locally: `python outage_agent.py` (we just did this!)
2. Test Streamlit UI in Local mode
3. When ready, deploy: `tensorlake deploy outage_agent.py`
4. Test remote endpoint: `python test_remote_outage_agent.py`
5. Test Streamlit UI in Remote mode

### Option B: Deploy First (Production Workflow)
1. Deploy: `tensorlake deploy outage_agent.py` (creates endpoint)
2. Test remote endpoint: `python test_remote_outage_agent.py`
3. Use Streamlit UI in Remote mode

## Summary

- **Local mode**: No deployment needed, runs on your machine
- **Remote mode**: Requires deployment first, runs on Tensorlake Cloud
- You can test the Streamlit UI in **either mode** without deployment (just use Local mode)

