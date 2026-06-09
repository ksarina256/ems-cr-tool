# EMS CR Validation Tool

Internal tool for comparing the EMS ClearCase codebase against a Gitea base
refresh and validating that custom Change Requests (CRs) are preserved.

---

## Folder Structure

```
ems-cr-tool/
  START_TOOL.bat          ← double-click this to run the tool
  backend/
    app.py                ← Flask web server
    compare_engine.py     ← diff engine (no dependencies beyond Python stdlib)
    requirements.txt      ← only needs Flask
  frontend/
    index.html            ← the web UI (served by Flask automatically)
  input/
    clearcase/            ← extracted ClearCase snapshot goes here
    gitea/                ← extracted Gitea clone snapshot goes here
  last_results.json       ← auto-generated after each run
  cr_mappings.json        ← saved CR-to-file mappings
```

---

## First-Time Setup (one time only)

1. Make sure Python 3.8+ is installed on your Windows machine.
   Check: open Command Prompt and run `python --version`

2. Install Flask:
   ```
   pip install flask
   ```

That's it. No other installs needed.

---

## How to Use the Tool

### Step 1 — Export snapshots from Citrix

**ClearCase snapshot** (on alhxpdvemcc01):
```bash
cd /view/your_view_name/vobs/ems
zip -r ems_clearcase_snapshot.zip .
```
Then copy the zip file from Citrix to your local Windows machine.

**Gitea snapshot** (on alhxvdvemscc01):
```bash
cd /path/to/gitea/clone
zip -r ems_gitea_snapshot.zip .
```
Then copy the zip file from Citrix to your local Windows machine.

### Step 2 — Start the tool

Double-click `START_TOOL.bat`

The browser opens automatically to http://localhost:5000

### Step 3 — Upload snapshots

In the browser:
- Upload `ems_clearcase_snapshot.zip` to the ClearCase zone
- Upload `ems_gitea_snapshot.zip` to the Gitea zone

### Step 4 — Configure CR Mappings (optional)

Add CR-to-file mappings if you want explicit tracking.
The tool also auto-detects CRs from code comments like `# CR-1042: ...`

### Step 5 — Run Comparison

Click "Run Comparison" and wait for results.

---

## CR Auto-Detection

The engine automatically scans all text files for CR references in this format:
```
# CR-1042: description of change
// CR-1042: description
/* CR-1042 */
```

Any file containing a CR tag is automatically associated with that CR in the
results, even without an explicit mapping.

---

## Supported File Types

The diff engine compares these file types as text:
`.py .js .ts .jsx .tsx .java .c .cpp .h .sh .bash .yaml .yml .json .xml`
`.html .css .sql .pl .rb .go .properties .cfg .conf .ini .md .txt .bat .ps1`

Binary files are detected and flagged as "not compared" — they show up in the
file list with a note but no line-level diff.

---

## Exporting Reports

From the Report tab, you can export:
- **JSON** — full structured results including all diffs
- **CSV** — summary table of all changed files and their CR tags

---

## Troubleshooting

**"ClearCase input folder is empty" error**
→ Make sure you uploaded the zip and it extracted correctly.
   Check the `input/clearcase/` folder has files in it.

**No CRs showing up in CR Status tab**
→ Either add explicit CR mappings, or make sure your code files contain
   comments like `# CR-1042: ...`

**Comparison is slow**
→ Normal for large codebases. The engine hashes files first so identical
   files are skipped instantly. Only changed files get full line diffs.

**Port 5000 already in use**
→ Edit `backend/app.py` last line: change `port=5000` to `port=5001`
   then open http://localhost:5001

---

## Architecture Notes

- The backend (Flask + Python) runs entirely on your local Windows machine
- No data is sent anywhere — all processing is local
- The tool is strictly read-only — it never writes to ClearCase or Gitea
- Results are saved to `last_results.json` so you can reload them without re-running
- CR mappings are saved to `cr_mappings.json` and persist between runs
