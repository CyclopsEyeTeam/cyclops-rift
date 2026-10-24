# Mark sheets

A presence never draws another presence. Each sheet here is a presence's own small look, rendered by her own terminal renderer (Cyclops Link V1 §12). Sheets are display data only: never part of a Link record, never read from the Link directory.

| File | Whose | Rendered by |
| --- | --- | --- |
| `rift.json` | Rift | Cyclops Rift `rift/render.py` |
| `spark.json` | Spark | Cyclops Spark `hooks/render-raster.js` |
| `keeper.json` | Keeper | Cyclops Keeper `scripts/terminal_art.py` |
| `prism.json` | Prism | Cyclops Prism `scripts/terminal.py` |

Spark, Keeper, and Prism are unchanged copies of the sheets shipped with Cyclops Keeper. SHA-256 of those three matches Keeper's `link-mark/SOURCE.md`.

SHA-256:

    9708da383f7fc4638d5ac67af7d0632e65cdd7435fbcc35348f0452630940a24  keeper.json
    01ca03d0169c28c0cff40682fdc33ab2a34cf6cd783bb60ea510aceef2377196  prism.json
    95548284fa8c0135cda72878993ae523930d405df0decc1e8994829ce37fe2ed  rift.json
    e9e20e8deae71c269d61fbe133a0ebccc667537f714d22a0922e45b780d263b1  spark.json
