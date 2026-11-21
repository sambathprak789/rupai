# RupAI

Personal text-to-image app. The Qwen-Image 2.1 model (GGUF) runs in ComfyUI on a free Google Colab T4.
A FastAPI backend serves the React UI and the API, and a Cloudflare quick tunnel gives it a public URL.

Model license: Qwen Research License (non-commercial research and evaluation only).

Free Colab note: Colab's FAQ lists "bypassing the notebook UI to interact primarily via a web UI" as not allowed on free
runtimes, so a session can be stopped without warning. Keep the Colab tab open; if the app goes offline, Run all again.

## Features

- Fast (8 steps, Turbo LoRA, 1–4 images, ~3–4 min each on T4) and Quality (10–60 steps, 1 image) modes
- Live preview after every step, per-image and whole-job countdown, Cancel
- Seed, steps and CFG settings; sizes 1:1, 16:9, 9:16
- Session gallery with lightbox, Reuse and Render in Quality
- Background warm-up so the first image does not wait for the model load

```
rupai/
├── .github/workflows/ci.yml   lint + tests; on main: build the frontend and publish release build-N with dist.zip
├── backend/                   FastAPI (see backend/README.md)
├── frontend/                  React + Vite (see frontend/README.md)
├── comfy/t2i_workflow.json    ComfyUI workflow template
├── scripts/release.ps1        publish a release from your PC (same checks as CI)
└── notebook/
    ├── rupai.ipynb            run the app on Colab
    └── m1_spike.ipynb         M1 benchmark (speed, VRAM, RAM)
```

## One-time setup

1. **Create the repository** on GitHub: `sambathprak789/rupai`, **private**, no README.
2. **Push the code** (PowerShell, in the `rupai` folder):
   ```powershell
   git init -b main
   git add .
   git commit -m "RupAI M1-M4"
   git remote add origin https://github.com/sambathprak789/rupai.git
   git push -u origin main
   ```
3. **Publish a release** (the notebook needs one):
   - With GitHub Actions: Actions → "CI" must be green; it then creates release `build-N` with `dist.zip`.
   - Without Actions (for example while the account has a billing lock): run the same checks and publish from your PC.
     Needs the GitHub CLI once: `winget install GitHub.cli`, then `gh auth login`.
     ```powershell
     .\scripts\release.ps1
     ```
4. **Create a token for Colab**: GitHub → Settings → Developer settings → Fine-grained tokens → Generate.
   Repository access: *Only select repositories* → `rupai`. Permissions: *Contents: Read-only*. Nothing else.
5. **Colab secrets** (open `notebook/rupai.ipynb` in Colab, key icon on the left):
   - `GITHUB_TOKEN` = the token from step 4 (turn on *Notebook access*)
   - `RUPAI_KEY` = optional fixed access key (a long random string)
   - `HF_TOKEN` = optional

## Every session

Colab → upload or open `notebook/rupai.ipynb` → Runtime → Change runtime type → **T4 GPU** → **Run all** →
click **Open RupAI** in step 10.

Every push to `main` that passes CI (or every `scripts/release.ps1` run) makes a new release; the notebook uses the newest one
(`RELEASE_TAG = "latest"`) or a fixed tag such as `build-12` or `build-20261121-0636`.
