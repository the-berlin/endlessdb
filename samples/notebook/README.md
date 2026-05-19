# Notebook Sample App

This folder contains a Jupyter notebook sample that treats EndlessDB as an interactive notebook storage layer.

The notebook demonstrates configuration, dynamic writes, query helpers, serialization, and cleanup in a workflow that mirrors exploratory analysis or fixture preparation.

Open `endlessdb_notebook_app.ipynb` in VS Code after starting MongoDB:

```powershell
docker compose -f samples/docker-compose.yml up -d
```

Run the cells from top to bottom. The final cleanup cell is optional if you want to inspect the generated collection after the notebook finishes.