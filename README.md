# RupAI

Personal text-to-image app. The Qwen-Image 2.1 model (GGUF) runs in ComfyUI on a free Google Colab T4.
A FastAPI backend serves the React UI and the API, and a Cloudflare quick tunnel gives it a public URL.

Model license: Qwen Research License (non-commercial research and evaluation only).

```
rupai/
├── .github/workflows/ci.yml   lint + tests; on main: build the frontend and publish release build-N with dist.zip
├── backend/                   FastAPI (see backend/README.md)
├── frontend/                  React + Vite (see frontend/README.md)
├── comfy/t2i_workflow.json    ComfyUI workflow template
└── notebook/
    ├── rupai.ipynb            run the app on Colab
    └── m1_spike.ipynb         M1 benchmark (speed, VRAM, RAM)
```

## One-time setup

1. **Create the repository** on GitHub: `praksambaths/rupai`, **private**, no README.
2. **Push the code** (PowerShell, in the `rupai` folder):
   ```powershell
   git init -b main
   git add .
   git commit -m "RupAI M1-M4"
   git remote add origin https://github.com/praksambaths/rupai.git
   git push -u origin main
   ```
3. **Check CI**: GitHub → Actions → "CI" must be green. It then creates a release named `build-1` with `dist.zip`.
4. **Create a token for Colab**: GitHub → Settings → Developer settings → Fine-grained tokens → Generate.
   Repository access: *Only select repositories* → `rupai`. Permissions: *Contents: Read-only*. Nothing else.
5. **Colab secrets** (open `notebook/rupai.ipynb` in Colab, key icon on the left):
   - `GITHUB_TOKEN` = the token from step 4 (turn on *Notebook access*)
   - `RUPAI_KEY` = optional fixed access key (a long random string)
   - `HF_TOKEN` = optional

## Every session

Colab → upload or open `notebook/rupai.ipynb` → Runtime → Change runtime type → **T4 GPU** → **Run all** →
click **Open RupAI** in step 10.

Every push to `main` that passes CI makes a new release; the notebook uses the newest one
(`RELEASE_TAG = "latest"`) or a fixed tag such as `build-12`.
